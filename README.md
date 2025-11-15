# Invoice Extraction Pipeline

AI-powered pipeline to extract structured invoice data from email messages using large language models.

## Features

- **Email Processing**: Parse RFC822 email format from any source (files, IMAP, APIs)
- **AI Classification**: Automatically distinguish invoices from non-invoices
- **Data Extraction**: Extract structured fields (vendor, amount, date, line items)
- **Attachment Handling**: Save invoice PDFs and attachments automatically
- **Gmail IMAP**: Fetch emails directly from Gmail via OAuth2
- **Performance Metrics**: Track latency for each pipeline stage

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Process Local Email Files

```bash
# Place .eml files in my_data/invoices/ and my_data/noninvoices/
uv run python src/cli.py
```

Results saved to `results.json`, attachments in `attachments/`

### 3. Fetch from Gmail (Optional)

See [IMAP_SETUP.md](IMAP_SETUP.md) for OAuth2 setup.

```bash
# Get OAuth token
uv run python get_gmail_token.py --credentials credentials.json

# Set environment variables
export GMAIL_ACCESS_TOKEN='your-token'
export GMAIL_EMAIL='your@gmail.com'

# Fetch emails
uv run python imap_main.py
```

## Architecture

**Core Abstraction**: Email bytes in -> Structured data out

```
Email Bytes (RFC822)
    |
    v
[Parse Email] -> subject, body, attachments
    |
    v
[Classify with LLM] -> invoice vs non-invoice
    |
    v
[Extract with LLM] -> vendor, amount, date (if invoice)
    |
    v
ProcessedEmail + Metrics
```

## Key Design Decisions

1. **Source-Agnostic**: Accepts email bytes, not files (enables IMAP, S3, API ingestion)
2. **Two-Stage Pipeline**: Fast classification (1s) -> Slower extraction only for invoices (3-5s)
3. **Modular Storage**: Pluggable attachment storage (filesystem, S3, database)
4. **Latency-Focused Metrics**: Tracks processing time, not memory (inference moving to separate service)
5. **Model**: Qwen2.5-7B-Instruct (fits RTX 4090 24GB VRAM, excellent at structured output)

## Project Structure

```
src/invoicer/          # Core package
  |-- parser.py        # RFC822 email parsing
  |-- pipeline.py      # Orchestrator (email bytes -> ProcessedEmail)
  |-- models.py        # Pydantic data models
  |-- storage.py       # Attachment storage abstraction
  |-- metrics.py       # Performance tracking

src/cli.py             # CLI for processing local files
imap_main.py           # Gmail IMAP fetcher
get_gmail_token.py     # OAuth2 token helper
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)**: Comprehensive architecture, usage, and design rationale
- **[IMAP_SETUP.md](IMAP_SETUP.md)**: Gmail OAuth2 setup guide
- **[OAUTH_SETUP_FIX.md](OAUTH_SETUP_FIX.md)**: Troubleshooting redirect_uri_mismatch

## Hardware Requirements

- **GPU**: 24GB VRAM (RTX 4090, A5000, etc.) for Qwen2.5-7B
- **Disk**: ~15GB for model weights
- **RAM**: 16GB+ recommended

Smaller models (Qwen2.5-3B) available for less powerful hardware.

## Example Output

```json
{
  "subject": "Invoice #12345 - Monthly Subscription",
  "classification": {
    "is_invoice": true,
    "confidence": 0.98
  },
  "invoice": {
    "vendor": "Acme Corp",
    "total_amount": 1299.99,
    "currency": "USD",
    "invoice_number": "INV-12345",
    "invoice_date": "2025-11-01"
  },
  "attachments": [
    {
      "filename": "invoice-12345.pdf",
      "path": "attachments/email-001/invoice-12345.pdf"
    }
  ],
  "metrics": {
    "total_time_sec": 4.23,
    "classification_time_sec": 0.89,
    "extraction_time_sec": 3.12
  }
}
```

## License

[Your License]
