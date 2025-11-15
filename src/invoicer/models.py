"""Pydantic models for structured invoice data."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """An email attachment."""

    filename: str = Field(description="Original filename of the attachment")
    content_type: str = Field(description="MIME type of the attachment")
    size_bytes: int = Field(description="Size of the attachment in bytes")
    path: str = Field(description="Local filesystem path to the saved attachment")


class InvoiceLineItem(BaseModel):
    """A single line item on an invoice."""

    description: str = Field(description="Description of the item or service")
    quantity: Optional[int] = Field(None, description="Quantity of items")
    unit_price: Optional[Decimal] = Field(None, description="Price per unit")
    total: Optional[Decimal] = Field(None, description="Total for this line item")


class Invoice(BaseModel):
    """Structured invoice data extracted from email."""

    vendor: str = Field(description="Name of the vendor/company issuing the invoice")
    invoice_number: Optional[str] = Field(None, description="Invoice or receipt number")
    invoice_date: Optional[str] = Field(None, description="Date of invoice (YYYY-MM-DD format if possible)")
    due_date: Optional[str] = Field(None, description="Payment due date (YYYY-MM-DD format if possible)")
    total_amount: Optional[Decimal] = Field(None, description="Total amount due or paid")
    currency: str = Field(default="USD", description="Currency code (e.g., USD, EUR)")
    payment_status: Optional[Literal["paid", "unpaid", "unknown"]] = Field(
        None, description="Payment status if mentioned"
    )
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list, description="Individual line items on the invoice"
    )
    notes: Optional[str] = Field(None, description="Any additional relevant information")


class EmailClassification(BaseModel):
    """Classification result for an email."""

    is_invoice: bool = Field(description="Whether this email contains an invoice or receipt")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of the classification"
    )
    reasoning: str = Field(description="Brief explanation for the classification")


class ProcessingMetrics(BaseModel):
    """Performance metrics for email processing - latency focused."""

    # Timing metrics (end-to-end latency)
    model_load_time_sec: Optional[float] = Field(None, description="Time to load the model")
    total_time_sec: float = Field(description="Total processing time")
    parse_time_sec: float = Field(description="Email parsing time")
    attachment_extraction_time_sec: float = Field(description="Attachment extraction time")
    classification_time_sec: float = Field(description="Classification time")
    extraction_time_sec: float = Field(default=0.0, description="Invoice data extraction time (0 if skipped)")

    # Attachment metrics
    num_attachments: int = Field(default=0, description="Number of attachments")
    total_attachment_bytes: int = Field(default=0, description="Total attachment size in bytes")


class ProcessedEmail(BaseModel):
    """Complete result of processing an email."""

    subject: str
    from_address: str
    date: str
    classification: EmailClassification
    invoice: Optional[Invoice] = None
    attachments: list[Attachment] = Field(
        default_factory=list,
        description="List of file attachments extracted from the email"
    )
    metrics: ProcessingMetrics = Field(description="Performance metrics for this email")
