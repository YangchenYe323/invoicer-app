"""Email parsing utilities for RFC822 format emails."""

import email
from email.message import Message

from ..models import ParsedEmail, EmailAttachment


class EmailParser:
    """Parse RFC822 email messages and extract components."""

    @staticmethod
    def parse(email_bytes: bytes) -> ParsedEmail:
        """Parse email bytes and extract key components.

        Args:
            email_bytes: Email in RFC822 format (bytes)

        Returns:
            ParsedEmail: Parsed email object with all components
        """
        # Parse email from bytes
        msg = email.message_from_bytes(email_bytes)

        # Extract attachments
        attachments = EmailParser._extract_attachments(msg)

        # Extract body (prefer text, fallback to HTML)
        body_text, body_html = EmailParser._extract_body(msg)

        return ParsedEmail(
            subject=msg.get('Subject', ''),
            from_address=msg.get('From', ''),
            to_address=msg.get('To', ''),
            date=msg.get('Date', ''),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            message_id=msg.get('Message-ID', None),
        )

    @staticmethod
    def _extract_attachments(msg: Message) -> list[EmailAttachment]:
        """Extract attachments from email message.

        Args:
            msg: Email message object

        Returns:
            list[EmailAttachment]: List of email attachments
        """
        attachments = []

        for part in msg.walk():
            # Get filename
            filename = part.get_filename()

            # Skip if no filename (not an attachment)
            if not filename:
                continue

            # Get content type
            content_type = part.get_content_type()

            # Get the attachment payload
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                attachments.append(EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    data=payload,
                    size_bytes=len(payload),
                ))

            except Exception:
                # Skip malformed attachments
                continue

        return attachments

    @staticmethod
    def _extract_body(msg: Message) -> tuple[str | None, str | None]:
        """Extract both text and HTML bodies from an email message.

        Args:
            msg: Email message object

        Returns:
            tuple[str | None, str | None]: (body_text, body_html)
        """
        body_text = None
        body_html = None

        if msg.is_multipart():
            # Extract both text/plain and text/html
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                charset = part.get_content_charset() or 'utf-8'

                try:
                    if content_type == "text/plain" and body_text is None:
                        body_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                    elif content_type == "text/html" and body_html is None:
                        body_html = part.get_payload(decode=True).decode(charset, errors='ignore')
                except Exception:
                    continue

        else:
            # Not multipart
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or 'utf-8'

            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode(charset, errors='ignore')
                    if content_type == "text/plain":
                        body_text = decoded
                    elif content_type == "text/html":
                        body_html = decoded
                    else:
                        # Default to text
                        body_text = decoded
            except Exception:
                body_text = str(msg.get_payload())

        # Strip whitespace
        if body_text:
            body_text = body_text.strip()
        if body_html:
            body_html = body_html.strip()

        return body_text, body_html
