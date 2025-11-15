"""Attachment storage abstraction."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class AttachmentStorage(ABC):
    """Abstract interface for storing email attachments."""

    @abstractmethod
    def save_attachment(
        self,
        filename: str,
        data: bytes,
        content_type: str,
        email_identifier: Optional[str] = None,
    ) -> str:
        """Save an attachment and return its storage path/identifier.

        Args:
            filename: Original filename
            data: File data as bytes
            content_type: MIME content type
            email_identifier: Optional identifier to group attachments by email

        Returns:
            Storage path or identifier for the saved attachment
        """
        pass


class FileSystemAttachmentStorage(AttachmentStorage):
    """Store attachments on local filesystem."""

    def __init__(self, base_dir: Path):
        """Initialize filesystem storage.

        Args:
            base_dir: Base directory for storing attachments
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_attachment(
        self,
        filename: str,
        data: bytes,
        content_type: str,
        email_identifier: Optional[str] = None,
    ) -> str:
        """Save attachment to filesystem.

        Args:
            filename: Original filename
            data: File data as bytes
            content_type: MIME content type
            email_identifier: Optional identifier to group by email

        Returns:
            Relative path to the saved file
        """
        # Create subdirectory for email if identifier provided
        if email_identifier:
            email_dir = self.base_dir / email_identifier
            email_dir.mkdir(parents=True, exist_ok=True)
            file_path = email_dir / filename
        else:
            file_path = self.base_dir / filename

        # Write file
        with open(file_path, 'wb') as f:
            f.write(data)

        # Return relative path from base directory
        return str(file_path.relative_to(self.base_dir.parent))


class InMemoryAttachmentStorage(AttachmentStorage):
    """Store attachments in memory (for testing)."""

    def __init__(self):
        self.attachments: dict[str, bytes] = {}

    def save_attachment(
        self,
        filename: str,
        data: bytes,
        content_type: str,
        email_identifier: Optional[str] = None,
    ) -> str:
        """Store attachment in memory.

        Args:
            filename: Original filename
            data: File data as bytes
            content_type: MIME content type
            email_identifier: Optional identifier

        Returns:
            Storage key for the attachment
        """
        key = f"{email_identifier}/{filename}" if email_identifier else filename
        self.attachments[key] = data
        return key

    def get_attachment(self, key: str) -> Optional[bytes]:
        """Retrieve attachment by key."""
        return self.attachments.get(key)
