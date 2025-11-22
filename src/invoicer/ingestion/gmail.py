"""Gmail IMAP ingestion with OAuth2."""

import imaplib
import logging
import ssl
import requests
from typing import Optional

from .base import EmailSource, FolderInfo, EmailMessage

logger = logging.getLogger(__name__)


class GmailSource(EmailSource):
    """Gmail email source using IMAP with OAuth2."""

    def __init__(self, email_address: str, access_token: str, client_id: str = None, client_secret: str = None, refresh_token: str = None):
        """Initialize Gmail source.

        Args:
            email_address: Gmail email address
            access_token: OAuth2 access token
            client_id: OAuth2 client ID (for token refresh)
            client_secret: OAuth2 client secret (for token refresh)
            refresh_token: OAuth2 refresh token (for token refresh)
        """
        self.email_address = email_address
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self):
        """Connect to Gmail IMAP if not already connected."""
        if self._imap is not None:
            return

        # Create IMAP connection
        self._imap = imaplib.IMAP4_SSL("imap.gmail.com", ssl_context=ssl.create_default_context())

        # Authenticate using OAuth2
        auth_string = f"user={self.email_address}\x01auth=Bearer {self.access_token}\x01\x01"
        self._imap.authenticate("XOAUTH2", lambda x: auth_string)

    def list_folders(self) -> list[FolderInfo]:
        """List all folders in Gmail account.

        Returns:
            list[FolderInfo]: List of folder information
        """
        self._connect()

        # List all folders
        status, folders = self._imap.list()
        if status != "OK":
            raise Exception(f"Failed to list folders: {status}")

        folder_infos = []
        for folder_data in folders:
            # Parse folder name from IMAP response
            # Format: b'(\\HasNoChildren) "/" "INBOX"'
            parts = folder_data.decode().split('" "')
            if len(parts) >= 2:
                folder_name = parts[-1].strip('"')

                try:
                    # Get UIDVALIDITY using STATUS (doesn't require SELECT)
                    status, data = self._imap.status(folder_name, "(UIDVALIDITY)")
                    if status == "OK" and data:
                        uid_validity = data[0].decode().split("UIDVALIDITY ")[1].split(")")[0]
                        folder_infos.append(FolderInfo(name=folder_name, uid_validity=uid_validity))
                except Exception as e:
                    # Skip folders that can't be accessed
                    logger.warning(f"Skipping folder {folder_name}: {e}")
                    continue

        return folder_infos

    def fetch(
        self,
        folder: str,
        high_water_mark: Optional[int],
        low_water_mark: Optional[int],
        batch_size: int
    ) -> list[EmailMessage]:
        """Fetch emails from Gmail folder.

        Strategy:
        - If both watermarks are None: Fetch latest batch_size messages
        - Otherwise: Fetch UIDs > high_water_mark (new messages)

        Args:
            folder: Folder name (e.g., "INBOX")
            high_water_mark: Largest UID processed
            low_water_mark: Smallest UID processed
            batch_size: Maximum number of messages

        Returns:
            list[EmailMessage]: List of email messages
        """
        self._connect()

        # Select folder
        self._imap.select(folder)

        # Determine search criteria
        if high_water_mark is None and low_water_mark is None:
            # First run: Fetch latest batch_size messages
            status, data = self._imap.uid("SEARCH", None, "ALL")
            if status != "OK":
                raise Exception(f"Failed to search: {status}")

            all_uids = data[0].split()
            # Get latest N UIDs
            uids_to_fetch = all_uids[-batch_size:] if len(all_uids) > batch_size else all_uids
        else:
            # Subsequent runs: Fetch UIDs > high_water_mark OR UIDs < low_water_mark
            # This allows progressive ingestion of historical data
            new_uids = []
            historical_uids = []

            # Search 1: New messages (UID > high_water_mark)
            if high_water_mark is not None:
                status, data = self._imap.uid("SEARCH", None, f"UID {high_water_mark + 1}:*")
                if status == "OK" and data and data[0]:
                    new_uids = data[0].split()

            # Search 2: Historical messages (UID < low_water_mark)
            if low_water_mark is not None:
                status, data = self._imap.uid("SEARCH", None, f"UID 1:{low_water_mark - 1}")
                if status == "OK" and data and data[0]:
                    historical_uids = data[0].split()

            # Combine results: prioritize new messages, then historical
            # New messages are more important, so take those first
            new_uids_list = [int(uid.decode()) for uid in new_uids]
            historical_uids_list = [int(uid.decode()) for uid in historical_uids]

            # Take newest messages first, then oldest historical messages
            # Sort historical in ascending order (oldest first)
            historical_uids_list.sort()

            combined = new_uids_list + historical_uids_list

            # Limit to batch_size
            if len(combined) > batch_size:
                combined = combined[:batch_size]

            uids_to_fetch = [str(uid).encode() for uid in combined]

        # Fetch email data
        messages = []
        for uid_bytes in uids_to_fetch:
            uid = int(uid_bytes.decode())

            # Fetch RFC822 data
            status, data = self._imap.uid("FETCH", uid_bytes, "(RFC822)")
            if status != "OK" or not data or data[0] is None:
                continue

            rfc822_data = data[0][1]
            messages.append(EmailMessage(uid=uid, rfc822_data=rfc822_data))

        return messages

    def close(self):
        """Close IMAP connection."""
        if self._imap is not None:
            try:
                self._imap.close()
                self._imap.logout()
            except:
                pass
            self._imap = None

    def refresh_access_token(self) -> str:
        """Refresh OAuth2 access token.

        Returns:
            str: New access token

        Raises:
            Exception: If token refresh fails
        """
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise Exception("Missing OAuth2 credentials for token refresh")

        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(token_url, data=data)
        response.raise_for_status()

        new_token = response.json()["access_token"]
        self.access_token = new_token
        return new_token
