"""Invoice extraction pipeline using AI models."""

from .models import (
    Attachment,
    EmailClassification,
    Invoice,
    InvoiceLineItem,
    ProcessedEmail,
    ProcessingMetrics,
)
from .pipeline import InvoiceExtractionPipeline
from .storage import AttachmentStorage, FileSystemAttachmentStorage

__version__ = "0.1.0"

__all__ = [
    "InvoiceExtractionPipeline",
    "Attachment",
    "EmailClassification",
    "Invoice",
    "InvoiceLineItem",
    "ProcessedEmail",
    "ProcessingMetrics",
    "AttachmentStorage",
    "FileSystemAttachmentStorage",
]
