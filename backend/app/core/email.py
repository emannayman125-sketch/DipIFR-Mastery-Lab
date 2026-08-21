"""
Minimal, swappable email sending abstraction.

In development this simply logs the email (so verification/reset flows are
testable without a real mailbox). To go live, replace ConsoleEmailSender's
internals with a real provider call (SES, Postmark, SendGrid, etc.) behind
the same `send()` interface — nothing else in the app needs to change.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("dipifr.email")


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


_sender: EmailSender = ConsoleEmailSender()


def send_verification_email(to: str, verify_url: str) -> None:
    _sender.send(
        to=to,
        subject="Verify your DipIFR Mastery Lab account",
        body=f"Welcome! Confirm your email address by visiting:\n{verify_url}\n\nThis link expires soon.",
    )


def send_password_reset_email(to: str, reset_url: str) -> None:
    _sender.send(
        to=to,
        subject="Reset your DipIFR Mastery Lab password",
        body=(
            f"We received a request to reset your password. Visit:\n{reset_url}\n\n"
            "If you didn't request this, you can safely ignore this email."
        ),
    )
