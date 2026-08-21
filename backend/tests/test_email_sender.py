"""Unit tests for the SMTP email sender. smtplib is mocked throughout —
these tests never touch the network."""
from unittest.mock import MagicMock, patch

import pytest

from app.core.email import ConsoleEmailSender, EmailDeliveryError, SMTPEmailSender


def test_console_sender_never_raises(caplog):
    # The dev-mode fallback just logs; it should never raise regardless of input.
    ConsoleEmailSender().send("student@example.com", "Subject", "Body")


@patch("app.core.email.smtplib.SMTP")
def test_smtp_sender_starttls_and_login(mock_smtp_cls):
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    sender = SMTPEmailSender(
        host="smtp.example.com",
        port=587,
        username="apikey",
        password="secret",
        from_email="noreply@example.com",
        use_tls=True,
    )
    sender.send("student@example.com", "Verify your account", "Click here: https://example.com/verify")

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("apikey", "secret")
    assert mock_server.sendmail.call_count == 1
    from_addr, to_addrs, _raw_message = mock_server.sendmail.call_args[0]
    assert from_addr == "noreply@example.com"
    assert to_addrs == ["student@example.com"]


@patch("app.core.email.smtplib.SMTP_SSL")
def test_smtp_sender_implicit_tls_on_port_465(mock_smtp_ssl_cls):
    mock_server = MagicMock()
    mock_smtp_ssl_cls.return_value.__enter__.return_value = mock_server

    sender = SMTPEmailSender(
        host="smtp.example.com",
        port=465,
        username=None,
        password=None,
        from_email="noreply@example.com",
        use_tls=True,
    )
    sender.send("student@example.com", "Subject", "Body")

    mock_smtp_ssl_cls.assert_called_once()
    mock_server.login.assert_not_called()  # no credentials configured
    mock_server.sendmail.assert_called_once()


@patch("app.core.email.smtplib.SMTP")
def test_smtp_sender_raises_email_delivery_error_on_failure(mock_smtp_cls):
    mock_smtp_cls.side_effect = OSError("connection refused")

    sender = SMTPEmailSender(
        host="smtp.example.com",
        port=587,
        username=None,
        password=None,
        from_email="noreply@example.com",
        use_tls=True,
    )
    with pytest.raises(EmailDeliveryError):
        sender.send("student@example.com", "Subject", "Body")


def test_send_verification_email_swallows_delivery_errors(monkeypatch):
    """A transient SMTP outage must not turn into a 500 on /auth/register —
    it should be logged and swallowed, same as the rest of the module does."""
    import app.core.email as email_module

    class FailingSender:
        def send(self, to, subject, body):
            raise EmailDeliveryError("boom")

    monkeypatch.setattr(email_module, "_sender", FailingSender())
    email_module.send_verification_email("student@example.com", "https://example.com/verify?token=abc")
    email_module.send_password_reset_email("student@example.com", "https://example.com/reset?token=abc")
