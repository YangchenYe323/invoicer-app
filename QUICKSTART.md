# Quick Start Guide

This guide helps you get started with the invoice extraction pipeline.

## Current Status

✅ **Core Pipeline**: Fully implemented and tested
- Email parsing (RFC822 format)
- AI classification (invoice vs non-invoice)
- Data extraction using Qwen2.5-7B-Instruct
- Attachment storage
- Performance metrics

✅ **IMAP Integration**: Ready to use
- Gmail OAuth2 authentication
- Email metadata fetching
- Token management

✅ **Documentation**: Complete
- Architecture (CLAUDE.md)
- IMAP setup (IMAP_SETUP.md)
- OAuth troubleshooting (OAUTH_SETUP_FIX.md)
- Project overview (README.md)

## Usage Options

### Option 1: Process Local Email Files

Process .eml files from the filesystem:

```bash
# Place test emails in my_data/
uv run python src/cli.py
```

**Output**:
- `results.json` - Structured invoice data
- `attachments/` - Extracted PDF invoices

### Option 2: Fetch from Gmail via IMAP

**Step 1: Setup OAuth2 Credentials**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project and enable Gmail API
3. Create OAuth client (Desktop app type)
4. Download credentials.json

See [IMAP_SETUP.md](IMAP_SETUP.md) for detailed instructions.

**Step 2: Get OAuth Token**

```bash
# Standard flow (opens browser)
uv run python get_gmail_token.py --credentials credentials.json

# Console flow (if redirect_uri_mismatch error)
uv run python get_gmail_token.py --credentials credentials.json --console
```

**Step 3: Fetch Email Metadata**

```bash
export GMAIL_ACCESS_TOKEN='<token-from-step-2>'
export GMAIL_EMAIL='your@gmail.com'
uv run python imap_main.py
```

This displays metadata for last 1000 emails (subject, from, date, size, attachments).

### Option 3: Integrate Programmatically

```python
from pathlib import Path
from invoicer import InvoiceExtractionPipeline, FileSystemAttachmentStorage

# Initialize pipeline
storage = FileSystemAttachmentStorage(Path("attachments"))
pipeline = InvoiceExtractionPipeline(
    model_name="Qwen/Qwen2.5-7B-Instruct",
    attachment_storage=storage
)

# Process email bytes from any source
with open("email.eml", "rb") as f:
    email_bytes = f.read()

result = pipeline.process_email(email_bytes, email_identifier="email-001")

# Access results
print(f"Invoice: {result.classification.is_invoice}")
if result.classification.is_invoice:
    print(f"Vendor: {result.invoice.vendor}")
    print(f"Amount: {result.invoice.total_amount}")
print(f"Time: {result.metrics.total_time_sec:.2f}s")
```

## Testing the Setup

### 1. Test Package Installation

```bash
uv run python -c "from invoicer import InvoiceExtractionPipeline; print('✓ Package OK')"
```

### 2. Test IMAP Module

```bash
uv run python -c "from get_gmail_token import get_oauth_token; print('✓ IMAP OK')"
```

### 3. Run Invoice Extraction (requires GPU)

```bash
# This will download ~15GB model on first run
uv run python src/cli.py
```

**First run**: ~2-3 minutes (model download + initialization)
**Subsequent runs**: ~30-60 seconds (model load only)

## Common Commands

```bash
# Install/update dependencies
uv sync

# Process local emails
uv run python src/cli.py

# Get Gmail token
uv run python get_gmail_token.py --credentials credentials.json

# Fetch Gmail metadata
export GMAIL_ACCESS_TOKEN='...'
export GMAIL_EMAIL='...'
uv run python imap_main.py

# View results
cat results.json | python -m json.tool

# List attachments
ls -lh attachments/
```

## Next Steps

After verifying the basic setup works:

1. **Test with your emails**: Place .eml files in `my_data/invoices/`
2. **Try IMAP fetching**: Follow OAuth setup in IMAP_SETUP.md
3. **Integrate with pipeline**: Combine IMAP fetcher with invoice extraction
4. **Customize**: Modify prompts, model, or storage backend

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: invoicer` | Run `uv sync` |
| `redirect_uri_mismatch` | See OAUTH_SETUP_FIX.md |
| `CUDA out of memory` | Reduce `gpu_memory_utilization` or use smaller model |
| `Token expired` | Re-run `get_gmail_token.py` to refresh |
| Slow processing | Normal for first email (CUDA compilation) |

## Architecture Overview

```
┌─────────────────────┐
│  Email Source       │
│  (File/IMAP/API)    │
└──────────┬──────────┘
           │ email_bytes (RFC822)
           v
┌─────────────────────┐
│  EmailParser        │
│  (src/invoicer/     │
│   parser.py)        │
└──────────┬──────────┘
           │ parsed_data
           v
┌─────────────────────┐
│  AttachmentStorage  │
│  (save PDFs)        │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│  LLM Classification │
│  (Qwen2.5-7B)       │
└──────────┬──────────┘
           │ is_invoice?
           v
    ┌──────┴──────┐
    │             │
    NO           YES
    │             │
    v             v
  Skip      ┌─────────────┐
            │ LLM Extract │
            │ (Qwen2.5-7B)│
            └──────┬──────┘
                   │
                   v
           ┌───────────────┐
           │ ProcessedEmail│
           │  + Metrics    │
           └───────────────┘
```

## Performance Expectations

| Metric | Value |
|--------|-------|
| Model load (cold start) | ~30-120s |
| Classification per email | ~1s |
| Extraction per invoice | ~3-5s |
| Non-invoice processing | ~1s (classification only) |
| Sequential throughput | ~10-15 emails/minute |

For complete documentation, see [CLAUDE.md](CLAUDE.md).
