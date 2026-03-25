import pytest
import base64
from unittest.mock import MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sender import send_email, get_gmail_service

def _make_msg():
    msg = MIMEMultipart("related")
    msg["Subject"] = "Test"
    msg["To"] = "me@example.com"
    msg.attach(MIMEText("<p>Hello</p>", "html"))
    return msg

def test_send_email_calls_gmail_api(mocker):
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.return_value = {"id": "abc123"}
    mocker.patch("sender.get_gmail_service", return_value=mock_service)

    result = send_email(_make_msg(), "~/.niederdaily/client_secret.json", "~/.niederdaily/token.json")
    assert result is True
    mock_service.users().messages().send.assert_called()

def test_send_email_returns_false_on_error(mocker):
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.side_effect = Exception("API error")
    mocker.patch("sender.get_gmail_service", return_value=mock_service)

    result = send_email(_make_msg(), "~/.niederdaily/client_secret.json", "~/.niederdaily/token.json")
    assert result is False
