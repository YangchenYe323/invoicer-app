"""Email ingestion module."""

from .base import EmailSource, FolderInfo, EmailMessage
from .gmail import GmailSource

__all__ = ["EmailSource", "FolderInfo", "EmailMessage", "GmailSource"]
