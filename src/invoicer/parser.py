"""Email parsing utilities for RFC822 format emails."""

import email
from email.message import Message
from typing import Optional


class EmailParser:
    """Parse RFC822 email messages and extract components."""

    @staticmethod
    def parse(email_bytes: bytes) -> dict:
        """Parse email bytes and extract key components.

        Args:
            email_bytes: Email in RFC822 format (bytes)

        Returns:
            Dictionary containing email metadata and content
        """
        # Parse email from bytes
        msg = email.message_from_bytes(email_bytes)

        # Extract attachments metadata (but don't save yet)
        attachments_info = EmailParser._extract_attachment_info(msg)

        return {
            'subject': msg.get('Subject', ''),
            'from': msg.get('From', ''),
            'to': msg.get('To', ''),
            'date': msg.get('Date', ''),
            'body': EmailParser._extract_body(msg),
            'attachments_raw': attachments_info,  # Raw attachment data
        }

    @staticmethod
    def _extract_attachment_info(msg: Message) -> list[dict]:
        """Extract attachment information from email message.

        Args:
            msg: Email message object

        Returns:
            List of dictionaries with attachment data and metadata
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

                attachments.append({
                    'filename': filename,
                    'content_type': content_type,
                    'data': payload,  # Raw bytes
                    'size_bytes': len(payload),
                })

            except Exception:
                continue

        return attachments

    @staticmethod
    def _extract_body(msg: Message) -> str:
        """Extract the text body from an email message.

        Prefers plain text, falls back to HTML if needed.

        Args:
            msg: Email message object

        Returns:
            Email body as string
        """
        body = ""

        if msg.is_multipart():
            # Look for text/plain first, then text/html
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body = part.get_payload(decode=True).decode(charset, errors='ignore')
                        break  # Prefer plain text
                    except Exception:
                        continue

            # If no plain text found, try HTML
            if not body:
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    if "attachment" in content_disposition:
                        continue

                    if content_type == "text/html":
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            break
                        except Exception:
                            continue
        else:
            # Not multipart
            charset = msg.get_content_charset() or 'utf-8'
            try:
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
            except Exception:
                body = str(msg.get_payload())

        return body.strip()
