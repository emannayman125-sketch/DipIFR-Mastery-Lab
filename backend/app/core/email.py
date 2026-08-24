"""
Minimal, swappable email sending abstraction.

Three senders are provided behind the same `EmailSender.send()` interface:

- ConsoleEmailSender: logs the email instead of delivering it. Used
  automatically whenever SMTP isn't configured (e.g. local dev), so
  verification/reset flows stay testable without a real mailbox.
- SendGridHTTPSender: sends via SendGrid's HTTPS API (port 443) instead of
  raw SMTP. Used automatically when the configured SMTP host is SendGrid's,
  since many PaaS hosts (Railway included) restrict outbound traffic on
  SMTP ports (25/465/587) for anti-spam reasons but never restrict plain
  HTTPS — this sidesteps that class of failure entirely, and is SendGrid's
  own recommended integration method.
- SMTPEmailSender: sends real email over SMTP (TLS/STARTTLS), using the
  Python standard library only. Used for any other SMTP provider (SES,
  Postmark, Mailgun, Gmail/Workspace, etc.) where the HTTPS shortcut above
  doesn't apply.

Which sender is active is decided once at import time from `settings`
(see `core/config.py`): if SMTP_HOST and SMTP_FROM_EMAIL are both set, real
email is sent (via SendGrid's HTTP API if SMTP_HOST is SendGrid's, else
plain SMTP); otherwise the app falls back to the console stub instead of
failing, so it stays usable without secrets configured.
"""
import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.text import MIMEText

import httpx

from .config import settings

logger = logging.getLogger("dipifr.email")

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailSender(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        ...


class ConsoleEmailSender(EmailSender):
    def send(self, to: str, subject: str, body: str) -> None:
        logger.info("---- EMAIL (dev mode, not actually sent) ----")
        logger.info("To: %s", to)
        logger.info("Subject: %s", subject)
        logger.info("%s", body)
        logger.info("-----------------------------------------------")


class EmailDeliveryError(Exception):
    """Raised when a real email provider fails to accept/send a message."""


class SendGridHTTPSender(EmailSender):
    """Sends email via SendGrid's HTTPS API (not SMTP).

    For SendGrid's SMTP relay, the "username" is always the literal string
    "apikey" and the "password" is the real API key — so the existing
    SMTP_PASSWORD variable already holds exactly what this needs; no new
    environment variable is required to switch a SendGrid setup from SMTP
    to this HTTP-based sender.
    """

    def __init__(self, api_key: str, from_email: str) -> None:
        self.api_key = api_key
        self.from_email = from_email

    def send(self, to: str, subject: str, body: str) -> None:
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(SENDGRID_API_URL, json=payload, headers=headers, timeout=10)
        except httpx.HTTPError as exc:
            logger.error("Failed to send email to %s via SendGrid API: %s", to, exc)
            raise EmailDeliveryError(f"Could not send email to {to}") from exc

        # SendGrid returns 202 Accepted on success with an empty body.
        if response.status_code != 202:
            logger.error(
                "SendGrid API rejected email to %s: status=%d body=%s",
                to, response.status_code, response.text[:500],
            )
            raise EmailDeliveryError(f"SendGrid API returned status {response.status_code}")


class SMTPEmailSender(EmailSender):
    """Sends real email over SMTP using only the standard library.

    Failures are logged and re-raised as `EmailDeliveryError` rather than
    silently swallowed, so callers can decide how to handle a delivery
    failure — but note that callers in backend/app/api/auth.py already
    return the same generic response whether or not an account exists, so a
    delivery failure there is caught and logged without changing the
    response shape (see the try/except around each send call).
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        use_tls: bool,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def send(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to

        try:
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=10, context=context) as server:
                    self._authenticate_and_send(server, to, message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                    if self.use_tls:
                        server.starttls(context=ssl.create_default_context())
                    self._authenticate_and_send(server, to, message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Failed to send email to %s via SMTP: %s", to, exc)
            raise EmailDeliveryError(f"Could not send email to {to}") from exc

    def _authenticate_and_send(self, server: smtplib.SMTP, to: str, message: MIMEText) -> None:
        if self.username and self.password:
            server.login(self.username, self.password)
        server.sendmail(self.from_email, [to], message.as_string())


def _build_sender() -> EmailSender:
    if settings.smtp_host and settings.smtp_from_email:
        if "sendgrid" in settings.smtp_host.lower() and settings.smtp_password:
            logger.info("Email delivery: using SendGrid HTTP API (bypasses SMTP ports entirely)")
            return SendGridHTTPSender(api_key=settings.smtp_password, from_email=settings.smtp_from_email)
        logger.info("Email delivery: using SMTP provider at %s:%d", settings.smtp_host, settings.smtp_port)
        return SMTPEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            use_tls=settings.smtp_use_tls,
        )
    logger.warning(
        "Email delivery: SMTP_HOST/SMTP_FROM_EMAIL not set - falling back to console logging. "
        "Verification and password-reset emails will NOT reach real users until SMTP is configured."
    )
    return ConsoleEmailSender()


_sender: EmailSender = _build_sender()


def send_verification_email(to: str, verify_url: str) -> None:
    try:
        _sender.send(
            to=to,
            subject="Verify your DipIFR Mastery Lab account",
            body=f"Welcome! Confirm your email address by visiting:\n{verify_url}\n\nThis link expires soon.",
        )
    except EmailDeliveryError:
        pass


def send_password_reset_email(to: str, reset_url: str) -> None:
    try:
        _sender.send(
            to=to,
            subject="Reset your DipIFR Mastery Lab password",
            body=(
                f"We received a request to reset your password. Visit:\n{reset_url}\n\n"
                "If you didn't request this, you can safely ignore this email."
            ),
        )
    except EmailDeliveryError:
        pass
