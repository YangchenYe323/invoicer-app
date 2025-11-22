"""Abstract base class for email ingestion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class FolderInfo:
    """Information about an email folder."""

    name: str
    uid_validity: str


@dataclass
class EmailMessage:
    """Email message with metadata."""

    uid: int
    rfc822_data: bytes


class EmailSource(ABC):
    """Abstract interface for fetching emails from a source."""

    @abstractmethod
    def list_folders(self) -> list[FolderInfo]:
        """List all folders in the email account.

        Returns:
            list[FolderInfo]: List of folder information
        """
        pass

    @abstractmethod
    def fetch(
        self,
        folder: str,
        high_water_mark: Optional[int],
        low_water_mark: Optional[int],
        batch_size: int
    ) -> list[EmailMessage]:
        """Fetch emails from folder.

        Strategy:
        - If both watermarks are None (first run): Fetch latest batch_size messages
        - Otherwise: Fetch UIDs > high_water_mark OR UIDs < low_water_mark

        Args:
            folder: Folder name (e.g., "INBOX")
            high_water_mark: Largest UID processed (fetch newer)
            low_water_mark: Smallest UID processed (fetch older)
            batch_size: Maximum number of messages to fetch

        Returns:
            list[EmailMessage]: List of email messages with UID and RFC822 data
        """
        pass

    @abstractmethod
    def close(self):
        """Close the connection."""
        pass
