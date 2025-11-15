"""IMAP email fetcher for Gmail using OAuth2.

This script connects to Gmail via IMAP and fetches email metadata.
Assumes OAuth token is provided externally.

Environment variables:
    GMAIL_ACCESS_TOKEN: OAuth2 access token for Gmail API
    GMAIL_EMAIL: Email address to authenticate as
"""

import imaplib
import base64
import email
import email.message
import os
import sys
from email.header import decode_header
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import ssl

@dataclass
class EmailMetadata:
    """Metadata for a single email."""
    uid: str
    subject: str
    from_address: str
    date: str
    size_bytes: int
    has_attachments: bool
    message_id: str


def generate_oauth2_string(username: str, access_token: str, base64_encode: bool = False) -> str:
  """Generates an IMAP OAuth2 authentication string.

  See https://developers.google.com/google-apps/gmail/oauth2_overview

  Args:
    username: the username (email address) of the account to authenticate
    access_token: An OAuth2 access token.
    base64_encode: Whether to base64-encode the output.

  Returns:
    The SASL argument for the OAuth2 mechanism.
  """
  auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
  if base64_encode:
    auth_string = base64.b64encode(auth_string.encode('utf-8'))
  return auth_string


def connect_to_gmail(email_address: str, access_token: str) -> imaplib.IMAP4_SSL:
    """Connect to Gmail using OAuth2.

    Args:
        email_address: Gmail address
        access_token: OAuth2 access token

    Returns:
        Connected IMAP client
    """
    print(f"Connecting to Gmail IMAP as {email_address}...")

    # Connect to Gmail IMAP
    imap = imaplib.IMAP4_SSL("imap.gmail.com", ssl_context=ssl.create_default_context())

    # Authenticate using OAuth2
    auth_string = generate_oauth2_string(email_address, access_token)
    imap.authenticate("XOAUTH2", lambda x: auth_string)

    print("Successfully authenticated!")
    return imap


def decode_email_header(header: Optional[str]) -> str:
    """Decode email header handling various encodings.

    Args:
        header: Raw email header

    Returns:
        Decoded string
    """
    if not header:
        return ""

    decoded_parts = decode_header(header)
    result = []

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or 'utf-8', errors='ignore'))
            except Exception:
                result.append(part.decode('utf-8', errors='ignore'))
        else:
            result.append(str(part))

    return " ".join(result)


def has_attachments(msg: email.message.Message) -> bool:
    """Check if email has attachments.

    Args:
        msg: Email message

    Returns:
        True if message has attachments
    """
    if not msg.is_multipart():
        return False

    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            return True
        # Some attachments don't have explicit disposition
        if part.get_filename():
            return True

    return False


def fetch_email_metadata(
    imap: imaplib.IMAP4_SSL,
    mailbox: str = "INBOX",
    limit: int = 1000
) -> list[EmailMetadata]:
    """Fetch metadata for recent emails.

    Args:
        imap: Connected IMAP client
        mailbox: Mailbox to fetch from (default: INBOX)
        limit: Maximum number of emails to fetch

    Returns:
        List of email metadata
    """
    print(f"\nSelecting mailbox: {mailbox}")
    status, messages = imap.select(mailbox, readonly=True)

    if status != "OK":
        raise Exception(f"Failed to select mailbox: {status}")

    total_messages = int(messages[0])
    print(f"Total messages in {mailbox}: {total_messages}")

    # Search for all messages
    status, message_ids = imap.search(None, "ALL")
    if status != "OK":
        raise Exception(f"Failed to search: {status}")

    # Get list of message UIDs
    uid_list = message_ids[0].split()

    # Take last N messages (most recent)
    uids_to_fetch = uid_list[-limit:] if len(uid_list) > limit else uid_list
    print(f"Fetching metadata for {len(uids_to_fetch)} messages...")

    metadata_list = []

    for i, uid in enumerate(uids_to_fetch, 1):
        try:
            # Fetch message headers and size
            status, msg_data = imap.fetch(uid, "(RFC822.HEADER RFC822.SIZE)")

            if status != "OK" or not msg_data or msg_data[0] is None:
                print(f"  Warning: Failed to fetch UID {uid.decode()}")
                continue

            # Parse headers
            header_data = msg_data[0][1]
            msg = email.message_from_bytes(header_data)

            # Extract size
            size_bytes = 0
            for item in msg_data:
                if isinstance(item, bytes) and b"RFC822.SIZE" in item:
                    size_str = item.decode().split("RFC822.SIZE")[1].strip().split(")")[0]
                    size_bytes = int(size_str)
                    break

            # Check for attachments (need full message for this)
            has_attach = False
            if size_bytes > 10000:  # Only check if message is reasonably sized
                status, full_msg_data = imap.fetch(uid, "(BODYSTRUCTURE)")
                if status == "OK" and full_msg_data:
                    # Simple heuristic: check if BODYSTRUCTURE mentions "attachment"
                    bodystructure = str(full_msg_data[0])
                    has_attach = "attachment" in bodystructure.lower()

            metadata = EmailMetadata(
                uid=uid.decode(),
                subject=decode_email_header(msg.get("Subject", "")),
                from_address=decode_email_header(msg.get("From", "")),
                date=msg.get("Date", ""),
                size_bytes=size_bytes,
                has_attachments=has_attach,
                message_id=msg.get("Message-ID", ""),
            )

            metadata_list.append(metadata)

            # Progress indicator
            if i % 100 == 0:
                print(f"  Processed {i}/{len(uids_to_fetch)} messages...")

        except Exception as e:
            print(f"  Error processing UID {uid.decode()}: {e}")
            continue

    return metadata_list


def display_metadata_summary(metadata_list: list[EmailMetadata]) -> None:
    """Display summary statistics and sample emails.

    Args:
        metadata_list: List of email metadata
    """
    print("\n" + "=" * 80)
    print("EMAIL METADATA SUMMARY")
    print("=" * 80)

    total = len(metadata_list)
    total_size = sum(m.size_bytes for m in metadata_list)
    with_attachments = sum(1 for m in metadata_list if m.has_attachments)

    print(f"Total emails fetched: {total}")
    print(f"Total size: {total_size / 1024 / 1024:.2f} MB")
    print(f"Average size: {total_size / total / 1024:.2f} KB")
    print(f"Emails with attachments: {with_attachments} ({with_attachments/total*100:.1f}%)")

    # Size distribution
    sizes = [m.size_bytes for m in metadata_list]
    sizes.sort()
    print(f"\nSize distribution:")
    print(f"  Min: {sizes[0] / 1024:.2f} KB")
    print(f"  P50: {sizes[len(sizes)//2] / 1024:.2f} KB")
    print(f"  P90: {sizes[int(len(sizes)*0.9)] / 1024:.2f} KB")
    print(f"  Max: {sizes[-1] / 1024:.2f} KB")

    # Show recent emails
    print("\n" + "=" * 80)
    print("RECENT EMAILS (Last 20)")
    print("=" * 80)

    for metadata in metadata_list[-20:]:
        size_kb = metadata.size_bytes / 1024
        attach_marker = "📎" if metadata.has_attachments else "  "
        print(f"\n{attach_marker} UID: {metadata.uid}")
        print(f"   From: {metadata.from_address[:70]}")
        print(f"   Subject: {metadata.subject[:70]}")
        print(f"   Date: {metadata.date}")
        print(f"   Size: {size_kb:.1f} KB")


def main():
    import dotenv  
    dotenv.load_dotenv()
    """Main entry point."""
    # Get credentials from environment
    access_token = os.getenv("GMAIL_OAUTH2_ACCESS_TOKEN")
    email_address = os.getenv("GMAIL_EMAIL")

    if not access_token:
        print("Error: GMAIL_OAUTH2_ACCESS_TOKEN environment variable not set")
        print("\nUsage:")
        print("  export GMAIL_OAUTH2_ACCESS_TOKEN='your-oauth2-access-token'")
        print("  export GMAIL_EMAIL='your-email@gmail.com'")
        print("  python imap_main.py")
        sys.exit(1)

    if not email_address:
        print("Error: GMAIL_EMAIL environment variable not set")
        sys.exit(1)

    try:
        # Connect to Gmail
        imap = connect_to_gmail(email_address, access_token)

        # Fetch metadata for last 1000 emails
        metadata_list = fetch_email_metadata(imap, mailbox="INBOX", limit=1000)

        # Display summary
        display_metadata_summary(metadata_list)

        # Close connection
        print("\nClosing connection...")
        imap.close()
        imap.logout()

        print("Done!")

    except imaplib.IMAP4.error as e:
        print(f"\nIMAP Error: {e}")
        print("\nThis might be an authentication issue. Make sure:")
        print("  1. GMAIL_OAUTH2_ACCESS_TOKEN is a valid OAuth2 access token")
        print("  2. The token has gmail.readonly or gmail.modify scope")
        print("  3. The token hasn't expired")
        sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
