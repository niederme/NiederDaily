import base64
import logging
from email.mime.multipart import MIMEMultipart
from pathlib import Path

log = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service(client_secret_path: str, token_path: str):
    creds = None
    token_p = Path(token_path).expanduser()
    secret_p = Path(client_secret_path).expanduser()

    if token_p.exists():
        creds = Credentials.from_authorized_user_file(str(token_p), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_p), SCOPES)
            creds = flow.run_local_server(port=0)
        token_p.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(msg: MIMEMultipart, client_secret_path: str, token_path: str) -> bool:
    try:
        service = get_gmail_service(client_secret_path, token_path)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception:
        log.exception("Gmail send failed")
        return False
