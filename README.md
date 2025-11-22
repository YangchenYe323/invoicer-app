# Invoice Extraction Pipeline

Serverless pipeline for extracting structured invoice data from Gmail using LLMs on Modal.

## Setup

```bash
# Install dependencies
uv sync

# Configure Modal secrets (database managed separately)
modal token new
modal secret create invoicer-secrets \
  DATABASE_URL=postgresql://... \
  AWS_ACCESS_KEY_ID=... \
  AWS_SECRET_ACCESS_KEY=... \
  S3_ENDPOINT=https://....r2.cloudflarestorage.com \
  S3_BUCKET=invoicer \
  INFERENCE_API_URL=https://....modal.run/v1 \
  GOOGLE_OAUTH2_CLIENT_ID=... \
  GOOGLE_OAUTH2_CLIENT_SECRET=...

# Deploy inference server
modal deploy modal/inference.py

# Run scheduler
modal run modal/scheduler.py --batch-size 10 --chunk-size 5
```

## Architecture

- **Scheduler** (`modal/scheduler.py`): Refreshes OAuth tokens, reconciles folders, spawns parallel workers
- **Workers** (`modal/worker.py`): Fetch emails via IMAP, classify with LLM, extract invoices, upload to R2, commit to PostgreSQL
- **Ingestion** (`src/invoicer/ingestion/`): Progressive backfill (UID > high_water_mark OR UID < low_water_mark)
- **Storage**: PostgreSQL (managed externally), Cloudflare R2, Modal volumes

## Structure

```
src/invoicer/          # Core library (ingestion, processing, semantic, storage)
modal/                 # Scheduler, worker, inference deployment
schema.sql             # Database schema (reference, managed externally)
docs/                  # Design documentation
```

## Monitoring

```bash
modal volume ls invoicer-metrics
modal volume get invoicer-metrics worker_1_*.json
```

See [docs/design.md](docs/design.md) for complete architecture.
