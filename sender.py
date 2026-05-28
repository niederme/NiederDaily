import base64
import logging
import socket
import time
from email.mime.multipart import MIMEMultipart
from pathlib import Path

log = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TRANSIENT_NETWORK_MARKERS = (
    "failed to resolve",
    "name or service not known",
    "name resolution",
    "network is unreachable",
    "nodename nor servname provided",
    "temporary failure in name resolution",
    "timed out",
)


def get_gmail_service(client_secret_path: str, token_path: str, interactive: bool = True):
    creds = None
    token_p = Path(token_path).expanduser()
    secret_p = Path(client_secret_path).expanduser()

    if token_p.exists():
        creds = Credentials.from_authorized_user_file(str(token_p), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif interactive:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_p), SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            raise RuntimeError(
                "Gmail token missing or revoked. Run 'python niederdaily.py --preflight' to re-authorize."
            )
        token_p.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _exception_chain(exc: Exception):
    seen = set()
    current = exc
    while current and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_transient_network_error(exc: Exception) -> bool:
    for err in _exception_chain(exc):
        if isinstance(err, (ConnectionError, TimeoutError, socket.gaierror)):
            return True
        if isinstance(err, OSError) and getattr(err, "errno", None) in {8, 50, 51, 60, 61, 64, 65}:
            return True
        text = str(err).lower()
        if any(marker in text for marker in TRANSIENT_NETWORK_MARKERS):
            return True
    return False


def send_email(
    msg: MIMEMultipart,
    client_secret_path: str,
    token_path: str,
    *,
    max_attempts: int = 6,
    retry_delay_seconds: float = 10.0,
) -> bool:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    for attempt in range(1, max_attempts + 1):
        try:
            service = get_gmail_service(client_secret_path, token_path, interactive=False)
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return True
        except Exception as exc:
            should_retry = attempt < max_attempts and _is_transient_network_error(exc)
            if should_retry:
                delay = retry_delay_seconds * attempt
                log.warning(
                    "Gmail send hit a transient network error on attempt %s/%s; retrying in %.1f seconds.",
                    attempt,
                    max_attempts,
                    delay,
                    exc_info=True,
                )
                time.sleep(delay)
                continue
            log.exception("Gmail send failed")
            return False
