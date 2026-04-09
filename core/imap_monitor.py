"""IMAP email monitor for OTP codes and order confirmations.

Connects to Gmail (or other IMAP servers) to:
- Extract OTP/verification codes from retailer emails
- Parse order confirmation details
- Forward relevant emails to Discord
"""

import asyncio
import email
import imaplib
import re
import time
from dataclasses import dataclass
from email.header import decode_header

from utils.logger import get_logger

log = get_logger("imap")


@dataclass
class EmailMessage:
    """Parsed email message."""
    subject: str
    sender: str
    body: str
    timestamp: float
    otp_code: str = ""


# Patterns for extracting OTP codes from various retailers
OTP_PATTERNS = [
    r"(?:verification|confirm|code|OTP|pin)[:\s]*(\d{4,8})",
    r"(?:Your code is|Enter code|Use code)[:\s]*(\d{4,8})",
    r"\b(\d{6})\b(?=.*(?:verify|confirm|code))",
    r"(?:one[- ]time)[:\s]*(\d{4,8})",
]

# Sender patterns for retailer emails
RETAILER_SENDERS = {
    "pokemon_center": ["pokemoncenter.com", "pokemon.com"],
    "target": ["target.com"],
    "walmart": ["walmart.com"],
    "amazon": ["amazon.com"],
    "bestbuy": ["bestbuy.com"],
    "tcgplayer": ["tcgplayer.com"],
    "ebay": ["ebay.com"],
}


class ImapMonitor:
    """Monitors email inbox for OTPs and order confirmations."""

    def __init__(self, config: dict):
        imap_config = config.get("imap", {})
        self.email_addr = imap_config.get("email", "")
        self.app_password = imap_config.get("app_password", "")
        self.server = imap_config.get("server", "imap.gmail.com")
        self.port = imap_config.get("port", 993)
        self._connection: imaplib.IMAP4_SSL = None
        self._running = False

    def connect(self):
        """Establish IMAP connection."""
        if not self.email_addr or not self.app_password:
            log.warning("IMAP not configured - OTP extraction disabled")
            return False

        try:
            self._connection = imaplib.IMAP4_SSL(self.server, self.port)
            self._connection.login(self.email_addr, self.app_password)
            self._connection.select("INBOX")
            log.info(f"IMAP connected: {self.email_addr}")
            return True
        except Exception as e:
            log.error(f"IMAP connection failed: {e}")
            return False

    def disconnect(self):
        """Close IMAP connection."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    async def wait_for_otp(
        self, retailer: str, timeout: int = 120, poll_interval: float = 2.0
    ) -> str:
        """Wait for an OTP code from a specific retailer.

        Args:
            retailer: Retailer name (matches RETAILER_SENDERS keys)
            timeout: Max seconds to wait
            poll_interval: Seconds between inbox checks

        Returns:
            OTP code string, or empty string on timeout
        """
        if not self._connection:
            if not self.connect():
                return ""

        sender_domains = RETAILER_SENDERS.get(retailer, [])
        if not sender_domains:
            log.warning(f"No sender patterns for retailer: {retailer}")
            return ""

        start = time.time()
        seen_ids = set()

        # Get current message IDs to ignore old emails
        _, data = self._connection.search(None, "ALL")
        if data[0]:
            seen_ids = set(data[0].split())

        log.info(f"Waiting for OTP from {retailer} (timeout: {timeout}s)...")

        while time.time() - start < timeout:
            await asyncio.sleep(poll_interval)

            try:
                self._connection.noop()  # Keep alive
                _, data = self._connection.search(None, "UNSEEN")

                if not data[0]:
                    continue

                msg_ids = data[0].split()
                new_ids = [mid for mid in msg_ids if mid not in seen_ids]

                for msg_id in new_ids:
                    seen_ids.add(msg_id)
                    msg = self._fetch_message(msg_id)
                    if not msg:
                        continue

                    # Check if from the right retailer
                    if not any(d in msg.sender.lower() for d in sender_domains):
                        continue

                    # Extract OTP
                    otp = self._extract_otp(msg.body)
                    if not otp:
                        otp = self._extract_otp(msg.subject)

                    if otp:
                        log.info(f"OTP found from {retailer}: {otp}")
                        return otp

            except Exception as e:
                log.error(f"IMAP poll error: {e}")
                self.connect()  # Reconnect

        log.warning(f"OTP timeout for {retailer}")
        return ""

    async def get_order_confirmations(self, since_minutes: int = 60) -> list[EmailMessage]:
        """Get recent order confirmation emails.

        Args:
            since_minutes: Look back this many minutes

        Returns:
            List of EmailMessage objects that look like order confirmations
        """
        if not self._connection:
            if not self.connect():
                return []

        confirmations = []
        confirmation_keywords = [
            "order confirm", "order placed", "order received",
            "thank you for your order", "purchase confirm",
            "order #", "order number",
        ]

        try:
            # Search recent emails
            _, data = self._connection.search(None, "ALL")
            if not data[0]:
                return []

            msg_ids = data[0].split()
            # Check last 50 emails
            for msg_id in msg_ids[-50:]:
                msg = self._fetch_message(msg_id)
                if not msg:
                    continue

                # Check age
                if time.time() - msg.timestamp > since_minutes * 60:
                    continue

                # Check if it looks like an order confirmation
                combined = f"{msg.subject} {msg.body}".lower()
                if any(kw in combined for kw in confirmation_keywords):
                    confirmations.append(msg)

        except Exception as e:
            log.error(f"Error fetching confirmations: {e}")

        return confirmations

    def _fetch_message(self, msg_id: bytes) -> EmailMessage:
        """Fetch and parse a single email message."""
        try:
            _, msg_data = self._connection.fetch(msg_id, "(RFC822)")
            raw = email.message_from_bytes(msg_data[0][1])

            # Decode subject
            subject_parts = decode_header(raw["Subject"] or "")
            subject = ""
            for part, encoding in subject_parts:
                if isinstance(part, bytes):
                    subject += part.decode(encoding or "utf-8", errors="replace")
                else:
                    subject += part

            # Get sender
            sender = raw["From"] or ""

            # Get body
            body = ""
            if raw.is_multipart():
                for part in raw.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode("utf-8", errors="replace")
            else:
                payload = raw.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            # Parse timestamp
            date_str = raw["Date"] or ""
            try:
                timestamp = email.utils.parsedate_to_datetime(date_str).timestamp()
            except Exception:
                timestamp = time.time()

            return EmailMessage(
                subject=subject,
                sender=sender,
                body=body,
                timestamp=timestamp,
            )

        except Exception as e:
            log.error(f"Error parsing email {msg_id}: {e}")
            return None

    def _extract_otp(self, text: str) -> str:
        """Extract OTP code from text using regex patterns."""
        for pattern in OTP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""
