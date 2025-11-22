# Implementation Plan

## Overview

This document outlines the phased implementation plan for the invoice extraction pipeline based on the finalized design in [design.md](design.md).

## Implementation Strategy

**Approach**: Incremental development with testable milestones

**Principles**:
1. Build and test each module independently
2. Use existing prototype code as reference
3. Maintain local testing capability throughout
4. Deploy to Modal incrementally

## Phase 1: Data Models & Database Layer

**Goal**: Align Pydantic models with PostgreSQL schema and implement database operations.

### Tasks

**1.1 Create Pydantic Models** (`src/invoicer/models.py`)
- [ ] Align with PostgreSQL schema (schema.sql)
- [ ] Models to create:
  - `User` (read-only, for joins)
  - `Source` (with OAuth fields)
  - `SourceFolder` (with watermarks)
  - `Invoice` (with all DB fields)
  - `LineItem` (for JSONB)
  - `AttachedFile` (for JSONB)
  - `ParsedEmail` (internal, not DB-backed)
  - `EmailMessage` (raw email with UID)
  - `FolderInfo` (IMAP folder metadata)
- [ ] Add validation (Field validators)
- [ ] Add `model_dump()` configurations for DB insertion
- [ ] Write unit tests for model validation

**1.2 Implement Database Layer** (`src/invoicer/storage/database.py`)
- [ ] Connection management using `psycopg`
- [ ] Context manager for transactions
- [ ] Operations to implement:
  - `get_all_sources() -> list[Source]`
  - `get_source_folders(source_id: int) -> list[SourceFolder]`
  - `create_source_folder(folder: SourceFolder) -> int`
  - `update_source_folder_watermarks(folder_id, high, low, timestamp)`
  - `insert_invoices(invoices: list[Invoice])` (bulk insert)
  - `get_source_by_id(source_id: int) -> Source`
- [ ] Write integration tests (using test database)

**1.3 Implement S3 Storage Layer** (`src/invoicer/storage/attachments.py`)
- [ ] S3 client using `boto3` (Cloudflare R2 compatible)
- [ ] Operations:
  - `generate_key(user_id, source_id, folder, uid_validity, uid, filename) -> str`
  - `object_exists(key: str) -> bool`
  - `upload_attachment(key: str, data: bytes, metadata: dict)`
  - `download_attachment(key: str) -> bytes` (for testing)
- [ ] Write integration tests (using test bucket or mocks)

**Deliverables**:
- ✅ Pydantic models aligned with schema
- ✅ Database operations with transaction support
- ✅ S3 operations with existence checks
- ✅ Unit + integration tests passing

---

## Phase 2: Email Processing Pipeline

**Goal**: Refactor and integrate email parsing and LLM inference modules.

### Tasks

**2.1 Email Parser** (`src/invoicer/processing/email_parser.py`)
- [ ] Reuse existing `parser.py` logic
- [ ] Refactor to use new `ParsedEmail` model
- [ ] Ensure robust handling of:
  - Multipart emails
  - Inline images vs attachments
  - Encoding issues (UTF-8, base64, etc.)
- [ ] Add comprehensive tests with real .eml files

**2.2 LLM Inference Module** (`src/invoicer/semantic/inference.py`)
- [ ] Create OpenAI client wrapper
- [ ] Implement classification:
  - `classify_email(parsed: ParsedEmail) -> bool` (is_invoice)
  - Use existing prompts from prototype
  - Handle JSON parsing errors (fallback extraction)
- [ ] Implement extraction:
  - `extract_invoice(parsed: ParsedEmail) -> Invoice`
  - Use existing prompts
  - Validate extracted data against Pydantic models
- [ ] Add retry logic for LLM timeouts
- [ ] Write tests (mock OpenAI API or use real vLLM endpoint)

**2.3 Configuration Management**
- [ ] Create `src/invoicer/config.py`
- [ ] Load from environment variables:
  - `DATABASE_URL`
  - `S3_ENDPOINT`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - `GOOGLE_OAUTH2_CLIENT_ID`, `GOOGLE_OAUTH2_CLIENT_SECRET`
  - `INFERENCE_API_URL`
- [ ] Hardcoded constants:
  - `BATCH_SIZE = 2000`
  - `CHUNK_SIZE = 200`
  - `CRON_SCHEDULE = "0 0 * * *"`
- [ ] Validation (raise error if required vars missing)

**Deliverables**:
- ✅ Email parser handling all edge cases
- ✅ LLM inference with classification + extraction
- ✅ Configuration management with validation
- ✅ End-to-end test: email → parsed → classified → extracted

---

## Phase 3: IMAP Ingestion Module

**Goal**: Implement Gmail IMAP integration with OAuth2 authentication.

### Tasks

**3.1 Abstract Base Class** (`src/invoicer/ingestion/base.py`)
- [ ] Define `EmailSource` ABC
- [ ] Methods:
  - `list_folders() -> list[FolderInfo]`
  - `fetch(folder, high, low, batch_size) -> list[EmailMessage]`
- [ ] Document interface contract clearly

**3.2 Gmail Implementation** (`src/invoicer/ingestion/gmail.py`)
- [ ] OAuth2 token refresh logic
  - Use existing `get_gmail_token.py` as reference
  - Implement `refresh_access_token(refresh_token) -> str`
- [ ] IMAP connection via `imaplib`
  - OAuth2 SASL authentication
  - Folder selection
  - UIDVALIDITY retrieval
- [ ] `list_folders()` implementation
  - LIST command
  - Parse folder names
  - Get UIDVALIDITY for each
- [ ] `fetch()` implementation
  - **Case 1**: Both watermarks NULL → Fetch latest N messages (highest UIDs)
  - **Case 2**: high set, low NULL → Fetch UIDs > high (new messages)
  - **Case 3**: Both set → Fetch UIDs > high OR UIDs < low (combined, limit N)
  - Use IMAP SEARCH + FETCH
  - Return `EmailMessage` objects with UID + RFC822 bytes
- [ ] Connection pooling/retry logic
- [ ] Write integration tests (requires test Gmail account)

**Deliverables**:
- ✅ Abstract `EmailSource` interface
- ✅ Gmail implementation with OAuth2
- ✅ Robust folder listing and email fetching
- ✅ Integration tests passing

---

## Phase 4: Worker Implementation

**Goal**: Implement the worker function that processes a batch of emails for a source folder.

### Tasks

**4.1 Worker Core Logic** (`modal/worker.py`)
- [ ] Function signature:
  ```python
  def process_folder(
      source_folder_id: int,
      batch_size: int = 2000,
      chunk_size: int = 200
  ) -> dict:  # Returns metrics
  ```
- [ ] Workflow steps:
  1. Fetch source_folder from DB
  2. Initialize ingestion module (Gmail)
  3. Fetch emails via `ingestion.fetch()`
  4. Divide into chunks
  5. For each chunk:
     - Parse emails (skip failures)
     - Classify with LLM
     - Extract invoices
     - Upload attachments to S3
     - BEGIN transaction
     - Insert invoices
     - Update watermarks
     - COMMIT
     - Record metrics
  6. Return aggregate metrics

**4.2 Error Handling**
- [ ] Per-email error logging (skip and continue)
- [ ] Chunk-level rollback on failure
- [ ] Comprehensive logging with context

**4.3 Metrics Recording**
- [ ] Create metrics abstraction (`modal/metrics.py`)
- [ ] Write to Modal Volume (JSON lines)
- [ ] Schema as defined in design.md
- [ ] Include error details in metrics

**4.4 Local Testing**
- [ ] Create test script (`scripts/test_worker.py`)
- [ ] Test with sample data from `my_data/invoices/`
- [ ] Verify:
  - DB inserts
  - S3 uploads
  - Watermark updates
  - Error handling

**Deliverables**:
- ✅ Worker function with complete workflow
- ✅ Robust error handling
- ✅ Metrics recording
- ✅ Local testing successful

---

## Phase 5: Scheduler Implementation

**Goal**: Implement the scheduler that orchestrates token refresh, folder reconciliation, and worker spawning.

### Tasks

**5.1 Scheduler Core Logic** (`modal/scheduler_app.py`)
- [ ] Function signature:
  ```python
  @app.function(schedule=modal.Cron("0 0 * * *"))
  def scheduler():
      """Daily cron job to process all sources."""
  ```
- [ ] Workflow:
  1. **Token Refresh**:
     - Fetch all sources
     - For each with expired token:
       - Refresh using refresh_token
       - If fails: skip source, log error
       - Do NOT write to DB
  2. **Folder Reconciliation**:
     - For each source (with valid token):
       - Connect via ingestion module
       - List folders
       - For each folder:
         - Check if source_folder exists in DB
         - If not: create
         - If UIDVALIDITY changed: create new record
  3. **Spawn Workers**:
     - For each source_folder:
       - Spawn worker function (1 per folder)
       - No concurrency limits

**5.2 Token Refresh Helper**
- [ ] Implement `refresh_source_token(source: Source) -> str | None`
- [ ] Handle OAuth refresh flow
- [ ] Log errors comprehensively

**5.3 Folder Reconciliation Helper**
- [ ] Implement `reconcile_folders(source: Source)`
- [ ] Use ingestion module to list folders
- [ ] Create/update source_folder records

**5.4 Worker Spawning**
- [ ] Use `worker.spawn()` for async execution
- [ ] Pass configuration (batch_size, chunk_size)
- [ ] Track spawned workers (for metrics aggregation)

**Deliverables**:
- ✅ Scheduler function with cron trigger
- ✅ Token refresh logic
- ✅ Folder reconciliation
- ✅ Worker spawning
- ✅ Comprehensive logging

---

## Phase 6: Modal Deployment & Integration

**Goal**: Deploy all components to Modal and integrate with existing vLLM inference server.

### Tasks

**6.1 Modal App Structure** (`modal/scheduler_app.py`)
- [ ] Create Modal App definition
- [ ] Configure image:
  ```python
  image = (
      modal.Image.debian_slim(python_version="3.12")
      .uv_pip_install("psycopg", "boto3", "openai", "pydantic")
      .add_local_dir("src/invoicer", "/invoicer")  # Include core package
  )
  ```
- [ ] Add Modal Secrets for environment variables
- [ ] Configure Modal Volume for metrics

**6.2 Deployment Configuration**
- [ ] Create Modal Secrets:
  ```bash
  modal secret create invoicer-secrets \
    DATABASE_URL=... \
    S3_ENDPOINT=... \
    S3_BUCKET=... \
    AWS_ACCESS_KEY_ID=... \
    AWS_SECRET_ACCESS_KEY=... \
    GOOGLE_OAUTH2_CLIENT_ID=... \
    GOOGLE_OAUTH2_CLIENT_SECRET=... \
    INFERENCE_API_URL=...
  ```
- [ ] Create Modal Volume:
  ```bash
  modal volume create invoicer-metrics
  ```

**6.3 Deploy & Test**
- [ ] Deploy scheduler: `modal deploy modal/scheduler_app.py`
- [ ] Test scheduler manually: `modal run modal/scheduler_app.py::scheduler`
- [ ] Verify:
  - Token refresh works
  - Folders reconciled
  - Workers spawned
  - Invoices inserted
  - S3 uploads successful
  - Metrics recorded

**6.4 Monitor Cron Job**
- [ ] Wait for daily cron trigger
- [ ] Monitor logs: `modal app logs invoicer-scheduler`
- [ ] Check database for new invoices
- [ ] Review metrics in Modal Volume

**Deliverables**:
- ✅ Scheduler deployed to Modal
- ✅ Cron job running successfully
- ✅ End-to-end workflow validated
- ✅ Monitoring in place

---

## Phase 7: Testing & Validation

**Goal**: Comprehensive testing and validation of the entire system.

### Tasks

**7.1 Integration Tests**
- [ ] End-to-end test with real Gmail account
- [ ] Verify invoice extraction accuracy
- [ ] Test error scenarios:
  - Token refresh failure
  - S3 unavailable
  - DB connection lost
  - Malformed emails
- [ ] Validate watermark updates

**7.2 Performance Testing**
- [ ] Measure throughput (emails/minute)
- [ ] Measure latency (per-email, per-chunk)
- [ ] Review LLM inference costs
- [ ] Check S3 storage usage

**7.3 Monitoring & Metrics**
- [ ] Review metrics in Modal Volume
- [ ] Aggregate statistics:
  - Total emails processed
  - Invoices found
  - Success rate
  - Error rate
- [ ] Validate metrics schema

**7.4 Documentation**
- [ ] Update README.md with deployment instructions
- [ ] Document common issues and solutions
- [ ] Create runbook for operations

**Deliverables**:
- ✅ All tests passing
- ✅ Performance metrics validated
- ✅ Monitoring operational
- ✅ Documentation complete

---

## Dependencies & Prerequisites

### External Services
- [x] Neon Postgres database (already configured)
- [x] Cloudflare R2 bucket (already configured)
- [x] vLLM inference server (already deployed)
- [x] Modal account with access

### Development Environment
- [ ] Python 3.12
- [ ] `uv` package manager
- [ ] Modal CLI installed
- [ ] PostgreSQL client (for schema pulls)
- [ ] Access to test Gmail account

### Configuration Files
- [x] `.env` with all required variables
- [x] `schema.sql` (pulled from database)
- [x] `pull_schema.sh` (schema sync script)

---

## Risk Mitigation

### Technical Risks

**Risk**: OAuth token refresh failures
- **Mitigation**: Comprehensive error logging, skip source and alert

**Risk**: S3 upload failures causing data loss
- **Mitigation**: Transaction ordering (S3 before DB commit), chunk-level rollback

**Risk**: LLM inference timeouts/errors
- **Mitigation**: Per-email error handling, retry logic, skip and continue

**Risk**: Database transaction deadlocks
- **Mitigation**: Serialize workers per folder, proper transaction isolation

**Risk**: IMAP rate limiting
- **Mitigation**: Batch size limits, future: implement throttling

### Operational Risks

**Risk**: Unexpected costs (GPU, storage, egress)
- **Mitigation**: Monitor costs daily, set budget alerts, scale-to-zero for inference

**Risk**: Data privacy/security
- **Mitigation**: S3 keys use IDs not emails, secure secrets in Modal

**Risk**: Schema changes breaking pipeline
- **Mitigation**: Version Pydantic models, comprehensive validation

---

## Success Criteria

### Phase 1-3 (Foundation)
- ✅ All models aligned with schema
- ✅ Database operations working
- ✅ S3 uploads successful
- ✅ Email parsing handles edge cases
- ✅ LLM inference accurate (>90% on test set)
- ✅ IMAP ingestion fetches emails correctly

### Phase 4-5 (Workflow)
- ✅ Worker processes emails end-to-end
- ✅ Scheduler orchestrates workflow
- ✅ Error handling robust
- ✅ Metrics recording working

### Phase 6-7 (Deployment)
- ✅ Deployed to Modal successfully
- ✅ Cron job running daily
- ✅ Processing >1000 emails/day
- ✅ Invoice extraction accuracy >85%
- ✅ Zero data loss (all chunks atomic)

---

## Timeline Estimate

**Aggressive Timeline** (1-2 weeks):
- Phase 1: 2 days
- Phase 2: 2 days
- Phase 3: 2 days
- Phase 4: 2 days
- Phase 5: 1 day
- Phase 6: 1 day
- Phase 7: 1 day

**Conservative Timeline** (3-4 weeks):
- Buffer for debugging, testing, refinement
- Production hardening
- Documentation

---

## Next Steps

1. **Immediate**: Start Phase 1 - Create Pydantic models aligned with schema
2. **Week 1**: Complete Phases 1-3 (foundation layers)
3. **Week 2**: Complete Phases 4-5 (workflow implementation)
4. **Week 3**: Complete Phases 6-7 (deployment & validation)

**Ready to begin?** Start with Phase 1, Task 1.1: Create Pydantic models in `src/invoicer/models.py`
