"""Invoice extraction pipeline - email bytes in, structured data out."""

# Models
from .models import (
    # Database models
    User,
    Source,
    SourceFolder,
    Invoice,
    LineItem,
    AttachedFile,
    # Processing models
    ParsedEmail,
    EmailAttachment,
    EmailMessage,
    FolderInfo,
    EmailClassification,
    # Metrics
    ChunkMetrics,
    WorkerConfig,
)

# Processing
from .processing import EmailParser

# Semantic
from .semantic import InferenceClient

# Storage
from .storage import DatabaseClient, S3Client

# Configuration
from .config import Config

__version__ = "0.1.0"

__all__ = [
    # Models
    "User",
    "Source",
    "SourceFolder",
    "Invoice",
    "LineItem",
    "AttachedFile",
    "ParsedEmail",
    "EmailAttachment",
    "EmailMessage",
    "FolderInfo",
    "EmailClassification",
    "ChunkMetrics",
    "WorkerConfig",
    # Components
    "EmailParser",
    "InferenceClient",
    "DatabaseClient",
    "S3Client",
    "Config",
]
