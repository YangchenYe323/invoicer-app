"""Pydantic models aligned with PostgreSQL schema and internal processing."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# JSONB Models (stored in database as JSON)
# ============================================================================


class LineItem(BaseModel):
    """Line item in an invoice (stored in invoice.line_items JSONB)."""

    description: str = Field(description="Description of the item or service")
    quantity: Optional[float] = Field(None, description="Quantity of items")
    unitPrice: Optional[Decimal] = Field(None, description="Price per unit", alias="unit_price")

    model_config = ConfigDict(populate_by_name=True)


class AttachedFile(BaseModel):
    """Attached file metadata (stored in invoice.attached_files JSONB)."""

    fileName: str = Field(description="Original filename", alias="file_name")
    fileKey: str = Field(description="S3 object key", alias="file_key")

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# Database Models (aligned with PostgreSQL schema)
# ============================================================================


class User(BaseModel):
    """User account (read-only, managed by separate auth app)."""

    id: str
    name: str
    email: str
    email_verified: bool
    image: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Source(BaseModel):
    """Email source with OAuth credentials."""

    id: int
    user_id: str
    name: str
    email_address: str
    source_type: str  # "gmail", "outlook", etc.
    oauth2_access_token: Optional[str] = None
    oauth2_refresh_token: Optional[str] = None
    oauth2_access_token_expires_at: Optional[datetime] = None
    oauth2_refresh_token_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceFolder(BaseModel):
    """Folder within an email source with processing state."""

    id: int
    source_id: int
    folder_name: str
    uid_validity: str
    high_water_mark: Optional[int] = None
    low_water_mark: Optional[int] = None
    last_processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Invoice(BaseModel):
    """Invoice record (aligned with database schema)."""

    # Database fields
    id: Optional[int] = None  # Auto-generated
    user_id: str
    source_id: int
    uid: int  # IMAP message UID
    message_id: Optional[str] = None  # Email Message-ID header

    # Invoice data
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    due_date: Optional[datetime] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payment_status: Optional[str] = None  # "paid", "unpaid", "pending", etc.

    # JSONB fields
    line_items: list[LineItem] = Field(default_factory=list)
    attached_files: list[AttachedFile] = Field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ============================================================================
# Internal Processing Models (not stored in database)
# ============================================================================


class EmailAttachment(BaseModel):
    """Email attachment with raw data (internal processing)."""

    filename: str
    content_type: str
    data: bytes
    size_bytes: int


class ParsedEmail(BaseModel):
    """Parsed email data (internal processing)."""

    subject: str
    from_address: str
    to_address: Optional[str] = None
    date: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    attachments: list[EmailAttachment] = Field(default_factory=list)
    message_id: Optional[str] = None  # Email Message-ID header


class EmailMessage(BaseModel):
    """Raw email message from IMAP with UID."""

    uid: int
    rfc822_data: bytes  # Raw RFC822 email bytes


class FolderInfo(BaseModel):
    """IMAP folder information."""

    name: str
    uid_validity: str


class EmailClassification(BaseModel):
    """LLM classification result."""

    is_invoice: bool = Field(description="Whether this email contains an invoice")
    confidence: Optional[str] = Field(None, description="Confidence level")
    reasoning: Optional[str] = Field(None, description="Reasoning for classification")


# ============================================================================
# Metrics Models
# ============================================================================


class ChunkMetrics(BaseModel):
    """Metrics for processing a chunk of emails."""

    worker_id: str
    source_folder_id: int
    chunk_num: int
    emails_fetched: int
    emails_processed: int
    invoices_found: int
    non_invoices: int
    errors: list[dict] = Field(default_factory=list)  # [{"uid": int, "error": str}, ...]
    duration_sec: float
    classification_time_sec: float = 0.0
    extraction_time_sec: float = 0.0
    s3_upload_time_sec: float = 0.0
    db_commit_time_sec: float = 0.0


# ============================================================================
# Configuration Models
# ============================================================================


class WorkerConfig(BaseModel):
    """Configuration passed to worker function."""

    source_folder_id: int
    batch_size: int = 2000
    chunk_size: int = 200
