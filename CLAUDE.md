# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered invoice extraction pipeline that processes RFC822 email messages and extracts structured invoice data using large language models.

**Core Abstraction**: Email bytes in (RFC822 format) → Structured data out

**Key Design Principles**:
- Source-agnostic: Accepts email bytes, not files (enables IMAP, API, file ingestion)
- Modular architecture: Parser, storage, and inference are separate concerns
- Performance tracked: Latency metrics for each pipeline stage

**Quick Start**: See [QUICKSTART.md](QUICKSTART.md) for immediate usage instructions.

## Architecture

### Module Structure (src/invoicer/)

```
src/invoicer/
├── __init__.py          # Package exports
├── parser.py            # RFC822 email parsing (bytes → dict)
├── models.py            # Pydantic data models
├── pipeline.py          # Core pipeline (email bytes → ProcessedEmail)
├── storage.py           # Attachment storage abstraction
└── metrics.py           # Performance metrics collection
```

### Core Pipeline Flow

```
Email Bytes (RFC822)
    ↓
[EmailParser] → Parse email structure
    ↓
[AttachmentStorage] → Save attachments (optional)
    ↓
[LLM Classification] → Invoice vs Non-invoice
    ↓
[LLM Extraction] → Extract structured fields (if invoice)
    ↓
ProcessedEmail (with metrics)
```

### Key Abstractions

**EmailParser**: `bytes → dict`
- Parses RFC822 email format
- Extracts subject, from, to, date, body
- Returns attachment data as bytes (doesn't save)

**AttachmentStorage**: Interface for saving attachments
- `FileSystemAttachmentStorage`: Saves to local filesystem
- `InMemoryAttachmentStorage`: Stores in memory (testing)
- Easy to add S3Storage, DatabaseStorage, etc.

**InvoiceExtractionPipeline**: Core orchestrator
- Takes email bytes + optional email_identifier
- Returns `ProcessedEmail` with classification, invoice data, attachments, metrics
- Handles all LLM interactions internally

## Data Models

**ProcessedEmail** (Main Output):
```python
ProcessedEmail(
    subject=str,
    from_address=str,
    date=str,
    classification=EmailClassification,
    invoice=Optional[Invoice],
    attachments=list[Attachment],
    metrics=ProcessingMetrics
)
```

**ProcessingMetrics** (Latency Focused):
- `model_load_time_sec`: Model initialization time
- `total_time_sec`: End-to-end processing time
- `parse_time_sec`: Email parsing
- `attachment_extraction_time_sec`: Attachment handling
- `classification_time_sec`: LLM classification
- `extraction_time_sec`: LLM extraction (0 if skipped)
- `num_attachments`: Count
- `total_attachment_bytes`: Size

**Note**: Memory/GPU metrics removed - inference will be separated to another service

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Run invoice extraction CLI
uv run python src/cli.py

# Run IMAP email fetcher
export GMAIL_ACCESS_TOKEN='your-token'
export GMAIL_EMAIL='your@gmail.com'
uv run python imap_main.py
```

### Using the Pipeline Programmatically

```python
from pathlib import Path
from invoicer import (
    InvoiceExtractionPipeline,
    FileSystemAttachmentStorage
)

# Initialize
storage = FileSystemAttachmentStorage(Path("attachments"))
pipeline = InvoiceExtractionPipeline(
    model_name="Qwen/Qwen2.5-7B-Instruct",
    attachment_storage=storage
)

# Process email from bytes
with open("email.eml", "rb") as f:
    email_bytes = f.read()

result = pipeline.process_email(
    email_bytes,
    email_identifier="email-123"  # For organizing attachments
)

# Access results
if result.classification.is_invoice:
    print(f"Vendor: {result.invoice.vendor}")
    print(f"Amount: {result.invoice.total_amount}")
    print(f"Attachments: {[a.filename for a in result.attachments]}")

print(f"Processing time: {result.metrics.total_time_sec:.2f}s")
```

### Ingesting from Different Sources

```python
# From file
with open("email.eml", "rb") as f:
    email_bytes = f.read()

# From IMAP (see IMAP Setup section below for authentication)
import imaplib
mail = imaplib.IMAP4_SSL("imap.gmail.com")
# For Gmail OAuth2, see imap_main.py for full implementation
_, data = mail.fetch("1", "(RFC822)")
email_bytes = data[0][1]

# From API/webhook
email_bytes = request.body  # FastAPI/Flask

# All use the same pipeline
result = pipeline.process_email(email_bytes)
```

## Technical Decisions

### 1. Email Bytes as Input (Not Files)
**Rationale**: Enables ingestion from any source - IMAP, S3, APIs, databases, files. The pipeline doesn't care where bytes come from.

### 2. Storage Abstraction
**Rationale**: Attachments can be saved anywhere - filesystem, S3, database. Easy to swap implementations without changing pipeline.

### 3. Metrics Focused on Latency
**Rationale**: Inference will likely be separated to another service. Memory/GPU metrics not useful when using remote inference API.

### 4. Pydantic Models Throughout
**Rationale**:
- Type safety and validation
- Easy serialization to JSON
- Self-documenting with Field descriptions
- IDE autocomplete support

### 5. Two-Stage LLM Pipeline
**Stage 1 - Classification** (fast):
- Binary: invoice vs non-invoice
- Small prompt, 256 token limit
- ~1s latency

**Stage 2 - Extraction** (slower):
- Only runs for invoices
- Extracts vendor, amounts, dates, line items
- 1500 token limit
- ~3-5s latency

**Rationale**: Don't waste time/money extracting from non-invoices

### 6. Model Choice: Qwen2.5-7B-Instruct
**Why**:
- 7B params fits RTX 4090 (24GB VRAM)
- Excellent at structured output
- Good at business documents
- Fast inference with vLLM

**Alternatives**:
- Smaller: Qwen2.5-3B for faster inference
- Larger: Qwen2.5-14B for better accuracy (needs more VRAM)

## IMAP Email Fetching

The project includes separate IMAP functionality to pull emails from Gmail.

### Quick Start

**Step 1: Get OAuth2 Token**
```bash
# Using helper script (requires credentials.json from Google Cloud Console)
uv run python get_gmail_token.py --credentials credentials.json

# If you get redirect_uri_mismatch error, use console flow
uv run python get_gmail_token.py --credentials credentials.json --console
```

**Step 2: Set Environment Variables**
```bash
export GMAIL_ACCESS_TOKEN='ya29.a0AfB_by...'  # From step 1 output
export GMAIL_EMAIL='your-email@gmail.com'
```

**Step 3: Fetch Email Metadata**
```bash
uv run python imap_main.py
```

This will:
- Connect to Gmail via IMAP using OAuth2
- Fetch metadata for last 1000 emails (subject, from, date, size, attachments)
- Display summary statistics and recent emails

### OAuth2 Setup

See [IMAP_SETUP.md](IMAP_SETUP.md) for complete setup instructions:
1. Create Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download credentials.json

**Troubleshooting**: If you get `redirect_uri_mismatch` error, see [OAUTH_SETUP_FIX.md](OAUTH_SETUP_FIX.md).

### IMAP Module Structure

- `imap_main.py`: Main IMAP fetcher - connects to Gmail and displays metadata
- `get_gmail_token.py`: Helper to obtain OAuth2 tokens (simulates external OAuth service)
- Token storage: `token.pickle` (auto-refreshes, gitignored)

### Token Management

- Access tokens expire after ~1 hour
- `get_gmail_token.py` automatically refreshes using refresh token
- For production: implement automatic refresh in your service or use service accounts

### Integration with Pipeline

To process emails fetched via IMAP:

```python
import imaplib
from invoicer import InvoiceExtractionPipeline, FileSystemAttachmentStorage

# Connect to Gmail (see imap_main.py for full OAuth2 implementation)
imap = connect_to_gmail(email_address, access_token)
imap.select("INBOX")

# Fetch email
status, data = imap.fetch(uid, "(RFC822)")
email_bytes = data[0][1]

# Process with pipeline
pipeline = InvoiceExtractionPipeline(...)
result = pipeline.process_email(email_bytes, email_identifier=uid)
```

## File Structure

```
invoicer-app/
├── src/
│   ├── invoicer/          # Core package
│   │   ├── __init__.py
│   │   ├── parser.py      # Email parsing
│   │   ├── models.py      # Data models
│   │   ├── pipeline.py    # Core pipeline
│   │   ├── storage.py     # Attachment storage
│   │   └── metrics.py     # Performance metrics
│   └── cli.py             # CLI interface
├── imap_main.py           # IMAP email fetcher
├── get_gmail_token.py     # OAuth2 token helper
├── my_data/               # Test data (gitignored)
│   ├── invoices/
│   └── noninvoices/
├── attachments/           # Extracted files (gitignored)
├── results.json           # Output (gitignored)
├── credentials.json       # OAuth credentials (gitignored)
├── token.pickle           # OAuth token (gitignored)
├── pyproject.toml         # Dependencies
├── README.md              # Project overview
├── QUICKSTART.md          # Quick start guide
├── CLAUDE.md              # This file (architecture & design)
├── IMAP_SETUP.md          # IMAP setup guide
└── OAUTH_SETUP_FIX.md     # OAuth troubleshooting
```

## Performance Characteristics

### Cold Start
- Model load: ~30-120s (depends on disk/cache)
- First inference: Additional ~2-3s (CUDA graph compilation)

### Per-Email Latency (after warmup)
- Invoice emails: ~4-6s total
  - Parse: <0.01s
  - Classify: ~1s
  - Extract: ~3-5s
- Non-invoice emails: ~1s total
  - Parse: <0.01s
  - Classify: ~1s
  - Extract: skipped

### Throughput
- Sequential: ~10-15 emails/minute
- Can be improved with batch processing

## Future Improvements

1. **Integrate IMAP with Pipeline**: Auto-process new emails from Gmail
2. **Batch Processing**: Process multiple emails in parallel
3. **Remote Inference**: Separate inference to API service
4. **PDF OCR**: Extract text from PDF attachments for better accuracy
5. **Streaming**: Process emails as they arrive (async/queue)
6. **Fine-tuning**: Train on invoice-specific data
7. **Caching**: Cache classification results for similar emails
8. **Incremental Sync**: Track last processed UID, only fetch new emails

## Common Issues

### Model Download Issues
- Requires ~15GB disk space
- May need HuggingFace token for some models
- Check internet connection

### CUDA Out of Memory
- Reduce `gpu_memory_utilization` (try 0.7 or 0.6)
- Use smaller model (Qwen2.5-3B)
- Close other GPU processes

### Slow Processing
- Normal for first email (CUDA compilation)
- Subsequent emails should be faster
- Consider batch processing for large volumes

### JSON Parsing Errors
- Model sometimes wraps JSON in markdown
- Pipeline has fallback extraction logic
- Lower temperature for more consistent output

### OAuth redirect_uri_mismatch
- Must use "Desktop app" OAuth credentials (not "Web app")
- Or use `--console` flag for copy-paste flow
- See OAUTH_SETUP_FIX.md for detailed solutions

### Token Expiration
- Access tokens expire after ~1 hour
- Re-run `get_gmail_token.py` to refresh (uses saved refresh token)
- For production: implement automatic token refresh

## Testing

```bash
# Run on test data
uv run python src/cli.py

# Check results
cat results.json | python -m json.tool

# Verify attachments
ls -lh attachments/
```

## Migration Notes

### From Old Structure
Old files (`email_parser.py`, `models.py`, `pipeline.py`, `main.py` in root) can be removed after confirming new structure works.

New entry point is `src/cli.py`, imports from `src/invoicer/` package.
