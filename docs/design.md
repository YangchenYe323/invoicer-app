# Invoice Extraction Pipeline - Final Design Document

## Executive Summary

AI-powered invoice extraction pipeline that processes Gmail emails via IMAP and extracts structured invoice data using LLMs. Deployed on Modal with Neon Postgres database and Cloudflare R2 object storage.

**Core Flow**: Gmail IMAP → Email Parsing → LLM Classification/Extraction → PostgreSQL + S3

## System Architecture

### Deployment Platform

- **Compute**: [Modal](modal-deployment.md) - Serverless Python platform
- **Database**: [Neon Postgres](https://neon.com/docs/introduction) - Serverless PostgreSQL
- **Object Storage**: Cloudflare R2 (S3-compatible)
- **Scheduling**: Modal Cron Jobs (daily)

### Modal Applications

Two separate Modal apps deployed independently:

1. **`invoicer-vllm-inference`** (`modal/vllm_inference.py`)
   - vLLM inference server with OpenAI-compatible API
   - Model: `Qwen/Qwen3-8B-FP8`
   - GPU: L40S (1x GPU)
   - Endpoint: `/v1/chat/completions`
   - Auto-scales: 5min scaledown window

2. **`invoicer-scheduler`** (to be implemented)
   - Main workflow orchestrator
   - Triggered via Modal Cron (daily)
   - Components:
     - Scheduler function: Token refresh, folder reconciliation, worker spawning
     - Worker function: Email fetching, processing, storage
     - Shared utilities

## Data Model

### Database Schema

Schema managed by separate project. This app consumes schema via:
- `pull_schema.sh` - Pulls latest schema from Neon database
- `schema.sql` - Local copy of schema

### Core Tables

**`public.user`**
- `id` (text, PK) - User identifier
- `name`, `email`, `email_verified`
- Managed by separate auth app (we consume read-only)

**`public.source`**
- `id` (int, PK) - Auto-incrementing source ID
- `user_id` (text, FK) - Owner
- `email_address` (text) - Email being monitored
- `source_type` (text) - "gmail", "outlook", etc.
- `oauth2_access_token` (text) - OAuth access token
- `oauth2_refresh_token` (text) - OAuth refresh token
- `oauth2_access_token_expires_at` (timestamp)
- `oauth2_refresh_token_expires_at` (timestamp)

**`public.source_folder`**
- `id` (int, PK)
- `source_id` (int, FK)
- `folder_name` (text) - "INBOX", "Spam", etc.
- `uid_validity` (text) - IMAP UIDVALIDITY value
- `high_water_mark` (int, nullable) - Largest UID processed
- `low_water_mark` (int, nullable) - Smallest UID processed
- `last_processed_at` (timestamp)

**`public.invoice`**
- `id` (int, PK) - Auto-incrementing
- `user_id` (text, FK)
- `source_id` (int, FK)
- `uid` (int) - IMAP message UID
- `message_id` (text) - Email Message-ID header
- `invoice_number` (text)
- `vendor_name` (text)
- `due_date` (timestamp)
- `total_amount` (numeric)
- `currency` (text)
- `payment_status` (text)
- `line_items` (jsonb) - Array of LineItem objects
- `attached_files` (jsonb) - Array of AttachedFile objects
- `created_at`, `updated_at` (timestamps)

### JSONB Schemas

**LineItem** (stored in `invoice.line_items`):
```typescript
{
  description: string;
  quantity?: number;
  unitPrice?: number;
}
```

**AttachedFile** (stored in `invoice.attached_files`):
```typescript
{
  fileName: string;  // Original filename
  fileKey: string;   // S3 object key
}
```

### S3 Key Organization

**Format**: `{user_id}/{source_id}/{folder}/{uid_validity}/{message_uid}/{filename}`

**Example**: `4PwWN01Pj8eGbxWwqYH6C1QcsMdZDGfq/1/INBOX/12345/67890/invoice.pdf`

**Benefits**:
- Privacy: No email addresses in paths
- Stability: IDs don't change
- Organized: Easy to query/delete by user or source

## Core Python Package (`src/invoicer/`)

Modular package consumed by both local testing and Modal workers.

### Module Structure

```
src/invoicer/
├── __init__.py
├── models.py              # Pydantic models (aligned with DB schema)
├── ingestion/
│   ├── __init__.py
│   ├── base.py            # Abstract base class
│   └── gmail.py           # Gmail IMAP + OAuth implementation
├── processing/
│   ├── __init__.py
│   └── email_parser.py    # RFC822 email parsing
├── semantic/
│   ├── __init__.py
│   └── inference.py       # LLM classification + extraction via OpenAI API
└── storage/
    ├── __init__.py
    ├── database.py        # PostgreSQL operations (psycopg)
    └── attachments.py     # S3/R2 operations (boto3)
```

### Ingestion Module Interface

**Abstract Interface** (`ingestion/base.py`):
```python
class EmailSource(ABC):
    @abstractmethod
    def list_folders(self) -> list[FolderInfo]:
        """List all folders in the email account."""
        pass

    @abstractmethod
    def fetch(
        self,
        folder: str,
        high_water_mark: int | None,
        low_water_mark: int | None,
        batch_size: int
    ) -> list[EmailMessage]:
        """
        Fetch emails from folder.

        Returns messages with UID > high_water_mark OR UID < low_water_mark.
        May involve 2 IMAP searches:
        - Search 1: UID > high (newer messages)
        - Search 2: UID < low (historical messages)

        Combined results limited to batch_size.
        """
        pass
```

**Gmail Implementation** (`ingestion/gmail.py`):
- OAuth2 authentication via SASL XOAUTH2
- Token refresh using refresh_token
- Handles IMAP connection, folder selection, UID searches
- Returns RFC822 email bytes

### Processing Module

**Email Parser** (`processing/email_parser.py`):
- Parses RFC822 email format
- Extracts: subject, from, to, date, body (text + HTML)
- Extracts attachments as bytes (filename, content_type, data)
- Returns structured `ParsedEmail` object

### Semantic Module

**LLM Inference** (`semantic/inference.py`):
- Two-stage pipeline via OpenAI-compatible API
- **Stage 1 - Classification**: Binary invoice/non-invoice (fast, ~1s)
- **Stage 2 - Extraction**: Extract invoice fields (slower, ~3-5s)
- Communicates with deployed vLLM server via HTTP

**API Client**:
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://yangchenye323--invoicer-vllm-inference-serve.modal.run/v1",
    api_key="not-needed"  # vLLM doesn't require auth
)
```

### Storage Module

**Database** (`storage/database.py`):
- Uses `psycopg` (PostgreSQL adapter)
- Connection from `DATABASE_URL` env var
- Operations:
  - Fetch sources and folders
  - Insert invoices (with transaction support)
  - Update folder watermarks
  - Atomic transactions for chunk commits

**Attachments** (`storage/attachments.py`):
- Uses `boto3` for S3-compatible storage
- Cloudflare R2 configuration from env vars
- Operations:
  - Check existence before upload
  - Upload with metadata
  - Generate S3 keys from folder context

## Modal Workflow Architecture

### Scheduler Flow (Daily Cron)

```
┌─────────────────────────────────────────────────────────┐
│ Scheduler (Cron Trigger - Daily)                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 1. Token Refresh                                         │
│    - Fetch all sources from DB                          │
│    - For each source with expired token:                │
│      - Refresh using refresh_token                      │
│      - If fails: Skip source, log error                 │
│      - Do NOT write back to DB (transient refresh)      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Folder Reconciliation                                │
│    - For each source (with valid token):                │
│      - Connect via IMAP                                 │
│      - List ALL folders (INBOX, Spam, Trash, etc.)      │
│      - For each folder:                                 │
│        - Get UIDVALIDITY                                │
│        - Check if source_folder exists in DB            │
│        - If not: Create with NULL watermarks            │
│        - If UIDVALIDITY changed: Create new record      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Spawn Workers                                        │
│    - For each source_folder:                            │
│      - Spawn 1 worker (no concurrent workers per folder)│
│      - Pass: folder_id, batch_size=2000, chunk_size=200 │
│    - No limit on total concurrent workers (keep simple) │
└─────────────────────────────────────────────────────────┘
```

### Worker Flow (Per Source Folder)

```
┌─────────────────────────────────────────────────────────┐
│ Worker(source_folder_id, batch_size, chunk_size)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 1. Fetch Source Folder from DB                         │
│    - Get source, folder_name, watermarks               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Fetch Emails via Ingestion Module                   │
│    - ingestion.fetch(folder, high, low, batch_size)    │
│    - Returns list of EmailMessage objects              │
│    - If first run (high=NULL, low=NULL):               │
│      - Fetch latest 2000 messages (highest UIDs)       │
│    - Subsequent runs:                                   │
│      - Fetch UIDs > high (new messages)                │
│      - Fetch UIDs < low (historical backfill)          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Divide into Chunks                                   │
│    - Split batch into chunks (e.g., 2000 → 10x200)     │
│    - Process each chunk independently                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ For Each Chunk:                                         │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Parse & Process Emails                              │
│    - For each email in chunk:                          │
│      - Parse RFC822 → ParsedEmail                      │
│      - Classify via LLM → is_invoice                   │
│      - If non-invoice: Skip (but track for watermark)  │
│      - If invoice: Extract via LLM → InvoiceData       │
│      - If error: Log, skip email, continue             │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Upload Attachments to S3                            │
│    - For each invoice with attachments:                │
│      - Generate S3 key: {user}/{source}/{folder}/...   │
│      - Check if exists (avoid duplicate uploads)        │
│      - Upload to R2                                     │
│    - If S3 fails: Entire chunk fails (rollback)        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Database Transaction (COMMIT LAST!)                 │
│    - BEGIN TRANSACTION                                  │
│    - Insert invoices with attached_files metadata      │
│    - Update source_folder watermarks:                   │
│      - high_water_mark = max(processed UIDs)           │
│      - low_water_mark = min(processed UIDs)            │
│      - last_processed_at = now()                       │
│    - COMMIT                                             │
│    - If fails: ROLLBACK (chunk will retry next run)    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 7. Record Metrics                                       │
│    - Write chunk metrics to Modal Volume               │
│    - Format: JSON lines                                 │
└─────────────────────────────────────────────────────────┘
```

## Error Handling Strategy

### Per-Email Failures

**Causes**: Malformed email, LLM timeout, parsing error

**Handling**:
- Log error with details (email UID, error message)
- Skip email, continue processing rest of chunk
- Do NOT fail entire chunk
- Still update watermarks (to avoid reprocessing)

### Chunk-Level Failures

**Causes**: S3 unavailable, DB connection lost, transaction rollback

**Handling**:
- Rollback entire chunk (nothing committed)
- Log error to Modal logs + metrics volume
- Chunk will be retried on next cron run
- Watermarks NOT updated (chunk appears unprocessed)

### Token Refresh Failures

**Causes**: Refresh token expired, OAuth revoked

**Handling**:
- Log error
- Skip entire source for this run
- Do NOT spawn workers for that source
- User must re-authenticate via web UI

### Transaction Ordering (Critical!)

To ensure atomicity:
1. ✅ Parse emails
2. ✅ LLM inference
3. ✅ Upload to S3 (with existence checks)
4. ✅ BEGIN database transaction
5. ✅ Insert invoices
6. ✅ Update watermarks
7. ✅ COMMIT

**If anything fails before COMMIT**: Entire chunk is lost, will retry next run.

## Metrics & Monitoring

### Metrics Volume

**Location**: Modal Volume at `/metrics/`

**Format**: JSON lines per worker run

**Filename**: `worker_{source_folder_id}_{timestamp}.jsonl`

**Schema**:
```json
{
  "worker_id": "abc123",
  "source_folder_id": 5,
  "chunk_num": 1,
  "emails_fetched": 200,
  "emails_processed": 198,
  "invoices_found": 45,
  "non_invoices": 153,
  "errors": [
    {"uid": 12345, "error": "LLM timeout"},
    {"uid": 12346, "error": "Malformed attachment"}
  ],
  "duration_sec": 34.5,
  "classification_time_sec": 8.2,
  "extraction_time_sec": 18.3,
  "s3_upload_time_sec": 4.1,
  "db_commit_time_sec": 3.9
}
```

**Design Note**: Schema is abstracted to allow future changes (e.g., switch to database, external monitoring).

### Logging

- Use Modal's built-in logging
- Extensive logging at each stage
- Include context: source_id, folder_id, email UID
- Error logs include full stack traces

## Configuration

### Environment Variables

Stored in `.env` (local) and Modal Secrets (production):

```bash
# Database
DATABASE_URL='postgresql://...'

# S3/R2
S3_ENDPOINT='https://...r2.cloudflarestorage.com/invoicer'
S3_BUCKET='invoicer'
AWS_ACCESS_KEY_ID='...'
AWS_SECRET_ACCESS_KEY='...'

# OAuth (for token refresh)
GOOGLE_OAUTH2_CLIENT_ID='...'
GOOGLE_OAUTH2_CLIENT_SECRET='...'

# Inference Server (for workers)
INFERENCE_API_URL='https://yangchenye323--invoicer-vllm-inference-serve.modal.run/v1'
```

### Worker Configuration

**Hardcoded Constants** (for MVP):
```python
BATCH_SIZE = 2000      # Messages per worker run
CHUNK_SIZE = 200       # Messages per transaction
CRON_SCHEDULE = "0 0 * * *"  # Daily at midnight UTC
```

**Design Note**: Establish proper abstraction for passing config to worker functions. Future: Make configurable per-source in database.

## Technology Stack

- **Language**: Python 3.12
- **Deployment**: Modal (serverless)
- **Database**: PostgreSQL 18 (Neon)
- **Object Storage**: Cloudflare R2 (S3-compatible)
- **LLM Inference**: vLLM (OpenAI-compatible API)
- **Model**: Qwen/Qwen3-8B-FP8

**Key Libraries**:
- `psycopg` - PostgreSQL adapter
- `boto3` - S3/R2 client
- `openai` - LLM API client
- `pydantic` - Data validation
- `modal` - Serverless platform SDK

## Future Enhancements

1. **Configurable batch/chunk sizes** per source
2. **Rate limiting** for IMAP providers
3. **PDF OCR** for invoice extraction from PDFs
4. **Fine-tuned models** for better accuracy
5. **Metrics dashboard** for monitoring
6. **Dead letter queue** for persistently failing emails
7. **Multi-provider support** (Outlook, Yahoo, etc.)
8. **Incremental sync** optimization

## References

- [Modal Documentation](modal-deployment.md)
- Database Schema: `schema.sql`
- Schema Pull Script: `pull_schema.sh`
- Inference Server: `modal/vllm_inference.py`
- Prototype: `src/invoicer/` (reference implementation)
