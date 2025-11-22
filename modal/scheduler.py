"""Invoice extraction scheduler - orchestrates token refresh, folder reconciliation, and worker spawning."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import modal

# Create Modal app
app = modal.App("invoicer-scheduler")

# Create image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "psycopg[binary]==3.2.3",
        "boto3==1.41.2",
        "openai==1.59.5",
        "pydantic==2.12.4",
        "requests==2.32.3",
    )
    .add_local_dir(Path(__file__).parent.parent / "src" / "invoicer", "/root/invoicer")
    .add_local_file(Path(__file__).parent / "worker.py", "/root/worker.py")
)

# Modal secrets and volumes
secrets = [modal.Secret.from_name("invoicer-secrets")]
metrics_volume = modal.Volume.from_name("invoicer-metrics", create_if_missing=True)

logger = logging.getLogger(__name__)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/metrics": metrics_volume},
    timeout=3600,
)
def process_source_folder(
    source_folder_id: int,
    access_token: str,
    batch_size: int = 2000,
    chunk_size: int = 200,
) -> dict:
    """Process emails for a single source folder.

    This worker:
    1. Fetches source_folder metadata from database
    2. Uses ingestion module to fetch emails via IMAP
    3. Divides emails into chunks
    4. For each chunk:
       - Parse and classify emails
       - Extract invoice data
       - Upload attachments to S3
       - Insert invoices and update watermarks in transaction
       - Record metrics

    Args:
        source_folder_id: ID of source_folder to process
        access_token: Valid OAuth2 access token for IMAP
        batch_size: Maximum emails to fetch (default: 2000)
        chunk_size: Emails per transaction chunk (default: 200)

    Returns:
        dict: Aggregate metrics for this worker run
    """
    sys.path.insert(0, "/root")

    from invoicer.config import Config
    from invoicer.storage.database import DatabaseClient
    from invoicer.ingestion import GmailSource
    from worker import process_chunk

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Load config from environment
    config = Config.from_env()

    # Connect to database
    db = DatabaseClient(config.database_url)

    logger.info(f"Processing source_folder_id={source_folder_id}")

    # Fetch source_folder from database
    folder = db.get_source_folder_by_id(source_folder_id)
    if not folder:
        return {"error": f"Source folder {source_folder_id} not found"}

    logger.info(
        f"Folder: {folder.folder_name}, "
        f"watermarks: high={folder.high_water_mark}, low={folder.low_water_mark}"
    )

    # Fetch source
    source = db.get_source_by_id(folder.source_id)
    if not source:
        return {"error": f"Source {folder.source_id} not found"}

    logger.info(f"Source: {source.email_address}")

    # Create Gmail ingestion client with provided access token
    gmail = GmailSource(
        email_address=source.email_address,
        access_token=access_token,  # Use refreshed token from scheduler
        client_id=config.google_oauth2_client_id,
        client_secret=config.google_oauth2_client_secret,
        refresh_token=source.oauth2_refresh_token,
    )

    try:
        # Fetch emails
        logger.info(f"Fetching up to {batch_size} emails from {folder.folder_name}")
        email_messages = gmail.fetch(
            folder=folder.folder_name,
            high_water_mark=folder.high_water_mark,
            low_water_mark=folder.low_water_mark,
            batch_size=batch_size,
        )

        logger.info(f"Fetched {len(email_messages)} emails")

        if not email_messages:
            return {
                "source_folder_id": source_folder_id,
                "emails_fetched": 0,
                "message": "No new emails to process"
            }

        # Divide into chunks
        chunks = []
        for i in range(0, len(email_messages), chunk_size):
            chunk = email_messages[i:i + chunk_size]
            chunks.append([(msg.uid, msg.rfc822_data) for msg in chunk])

        logger.info(f"Divided into {len(chunks)} chunks of size {chunk_size}")

        # Process each chunk
        all_metrics = []
        total_invoices = 0
        total_non_invoices = 0
        total_errors = 0

        for chunk_num, emails in enumerate(chunks, start=1):
            logger.info(f"Processing chunk {chunk_num}/{len(chunks)} ({len(emails)} emails)")

            try:
                metrics = process_chunk(
                    emails=emails,
                    source_folder_id=source_folder_id,
                    user_id=source.user_id,
                    source_id=source.id,
                    folder_name=folder.folder_name,
                    uid_validity=folder.uid_validity,
                    config=config,
                    chunk_num=chunk_num,
                )

                all_metrics.append(metrics)
                total_invoices += metrics.invoices_found
                total_non_invoices += metrics.non_invoices
                total_errors += len(metrics.errors)

                logger.info(
                    f"Chunk {chunk_num} complete: "
                    f"{metrics.invoices_found} invoices, "
                    f"{metrics.non_invoices} non-invoices, "
                    f"{len(metrics.errors)} errors"
                )

            except Exception as e:
                logger.error(f"Chunk {chunk_num} failed: {e}", exc_info=True)
                total_errors += len(emails)
                # Continue with next chunk

        # Close Gmail connection
        gmail.close()

        logger.info(
            f"Processing complete: {total_invoices} invoices, "
            f"{total_non_invoices} non-invoices, {total_errors} errors"
        )

        # Write metrics to volume
        from datetime import datetime, timezone
        import json
        from pathlib import Path

        metrics_dir = Path("/metrics")
        metrics_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        metrics_file = metrics_dir / f"worker_{source_folder_id}_{timestamp}.json"

        metrics_data = {
            "source_folder_id": source_folder_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "emails_fetched": len(email_messages),
            "chunks_processed": len(all_metrics),
            "invoices_found": total_invoices,
            "non_invoices": total_non_invoices,
            "errors": total_errors,
            "metrics": [m.model_dump() for m in all_metrics],
        }

        with open(metrics_file, "w") as f:
            json.dump(metrics_data, f, indent=2)

        logger.info(f"Wrote metrics to {metrics_file}")

        # Commit volume changes
        metrics_volume.commit()
        logger.info("Metrics volume committed")

        # Return aggregate metrics
        return {
            "source_folder_id": source_folder_id,
            "emails_fetched": len(email_messages),
            "chunks_processed": len(all_metrics),
            "invoices_found": total_invoices,
            "non_invoices": total_non_invoices,
            "errors": total_errors,
            "metrics": [m.model_dump() for m in all_metrics],
        }

    except Exception as e:
        logger.error(f"Failed to process source_folder {source_folder_id}: {e}", exc_info=True)
        gmail.close()
        raise


def refresh_source_token(source, config) -> Optional[str]:
    """Refresh OAuth2 access token for a source.

    Args:
        source: Source object with OAuth credentials
        config: Application config with OAuth client credentials

    Returns:
        str: New access token, or None if refresh failed
    """
    from invoicer.ingestion import GmailSource

    # Check if token needs refresh
    if source.oauth2_access_token_expires_at:
        now = datetime.now(timezone.utc)
        # Make expires_at timezone-aware if it isn't
        expires_at = source.oauth2_access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at > now:
            logger.info(f"Source {source.id} token still valid")
            return source.oauth2_access_token

    logger.info(f"Refreshing token for source {source.id}")

    try:
        gmail = GmailSource(
            email_address=source.email_address,
            access_token=source.oauth2_access_token,
            client_id=config.google_oauth2_client_id,
            client_secret=config.google_oauth2_client_secret,
            refresh_token=source.oauth2_refresh_token,
        )

        new_token = gmail.refresh_access_token()
        logger.info(f"Successfully refreshed token for source {source.id}")
        return new_token

    except Exception as e:
        logger.error(f"Failed to refresh token for source {source.id}: {e}")
        return None


def reconcile_folders(source, access_token, config, db):
    """Reconcile folders for a source - create missing source_folder records.

    Args:
        source: Source object
        access_token: Valid OAuth2 access token
        config: Application config
        db: Database client

    Returns:
        list[int]: List of source_folder IDs that were reconciled
    """
    from invoicer.ingestion import GmailSource

    logger.info(f"Reconciling folders for source {source.id}")

    try:
        # Connect to Gmail and list folders
        gmail = GmailSource(
            email_address=source.email_address,
            access_token=access_token,
            client_id=config.google_oauth2_client_id,
            client_secret=config.google_oauth2_client_secret,
            refresh_token=source.oauth2_refresh_token,
        )

        folder_infos = gmail.list_folders()
        gmail.close()

        logger.info(f"Found {len(folder_infos)} folders for source {source.id}")

        # Check each folder in database
        reconciled_ids = []

        for folder_info in folder_infos:
            # Check if folder exists with this UID validity
            existing = db.get_folder_by_name_and_uidvalidity(
                source_id=source.id,
                folder_name=folder_info.name,
                uid_validity=folder_info.uid_validity,
            )

            if existing:
                logger.info(f"Folder {folder_info.name} already exists (id={existing.id})")
                reconciled_ids.append(existing.id)
            else:
                # Create new source_folder
                logger.info(
                    f"Creating new source_folder: {folder_info.name} "
                    f"(uidvalidity={folder_info.uid_validity})"
                )
                folder_id = db.create_source_folder(
                    source_id=source.id,
                    folder_name=folder_info.name,
                    uid_validity=folder_info.uid_validity,
                )
                reconciled_ids.append(folder_id)

        return reconciled_ids

    except Exception as e:
        logger.error(f"Failed to reconcile folders for source {source.id}: {e}")
        return []


@app.function(
    image=image,
    secrets=secrets,
    timeout=7200,  # 2 hours for full orchestration
)
def scheduler(batch_size: int = 2000, chunk_size: int = 200):
    """Main scheduler function - orchestrates the entire workflow.

    Workflow:
    1. Fetch all sources from database
    2. Refresh OAuth tokens (transiently, not written back to DB)
    3. Reconcile folders (create missing source_folder records)
    4. Spawn one worker per source_folder (parallel execution)

    Args:
        batch_size: Maximum emails per worker (default: 2000)
        chunk_size: Emails per transaction chunk (default: 200)
    """
    sys.path.insert(0, "/root")

    from invoicer.config import Config
    from invoicer.storage.database import DatabaseClient

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("SCHEDULER STARTED")
    logger.info("=" * 80)

    # Load config
    config = Config.from_env()

    # Connect to database
    db = DatabaseClient(config.database_url)

    # Step 1: Fetch all sources
    logger.info("[1] Fetching all sources from database...")
    sources = db.get_all_sources()
    logger.info(f"Found {len(sources)} sources")

    if not sources:
        logger.info("No sources to process")
        return {"message": "No sources found"}

    # Step 2: Refresh tokens (transiently - not written back)
    logger.info("[2] Refreshing OAuth tokens...")
    source_tokens = {}  # source_id -> access_token

    for source in sources:
        token = refresh_source_token(source, config)
        if token:
            source_tokens[source.id] = token
        else:
            logger.warning(f"Skipping source {source.id} - token refresh failed")

    logger.info(f"Successfully refreshed {len(source_tokens)}/{len(sources)} tokens")

    # Step 3: Reconcile folders
    logger.info("[3] Reconciling folders...")
    all_folder_ids = []

    for source in sources:
        if source.id not in source_tokens:
            logger.info(f"Skipping folder reconciliation for source {source.id} (no valid token)")
            continue

        folder_ids = reconcile_folders(
            source=source,
            access_token=source_tokens[source.id],
            config=config,
            db=db,
        )
        all_folder_ids.extend(folder_ids)

    logger.info(f"Reconciled {len(all_folder_ids)} source_folders")

    # Step 4: Spawn workers (one per source_folder, in parallel)
    logger.info("[4] Spawning workers...")
    logger.info(f"Spawning {len(all_folder_ids)} workers in parallel")

    # Spawn all workers using .remote() for parallel execution
    worker_calls = []

    for folder_id in all_folder_ids:
        # Get the folder to find its source
        folder = db.get_source_folder_by_id(folder_id)
        if not folder:
            logger.warning(f"Source folder {folder_id} not found, skipping")
            continue

        # Get the access token for this source
        access_token = source_tokens.get(folder.source_id)
        if not access_token:
            logger.warning(f"No valid token for source {folder.source_id}, skipping folder {folder_id}")
            continue

        # Spawn worker asynchronously
        logger.info(f"Spawning worker for source_folder {folder_id} ({folder.folder_name})")
        call = process_source_folder.spawn(
            source_folder_id=folder_id,
            access_token=access_token,
            batch_size=batch_size,
            chunk_size=chunk_size,
        )
        worker_calls.append((folder_id, call))

    logger.info(f"Spawned {len(worker_calls)} workers")

    # Wait for all workers to complete and collect results
    logger.info("[5] Waiting for workers to complete...")
    results = []

    for folder_id, call in worker_calls:
        try:
            # Get result from spawned worker
            result = call.get()
            results.append(result)
            logger.info(f"Worker for folder {folder_id} completed successfully")
        except Exception as e:
            logger.error(f"Worker for folder {folder_id} failed: {e}")
            results.append({
                "source_folder_id": folder_id,
                "error": str(e)
            })

    # Aggregate results
    total_emails = sum(r.get("emails_fetched", 0) for r in results)
    total_invoices = sum(r.get("invoices_found", 0) for r in results)
    total_non_invoices = sum(r.get("non_invoices", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)

    logger.info("=" * 80)
    logger.info("SCHEDULER COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Workers completed: {len(results)}/{len(worker_calls)}")
    logger.info(f"Emails fetched: {total_emails}")
    logger.info(f"Invoices found: {total_invoices}")
    logger.info(f"Non-invoices: {total_non_invoices}")
    logger.info(f"Errors: {total_errors}")

    return {
        "sources_processed": len(source_tokens),
        "folders_reconciled": len(all_folder_ids),
        "workers_spawned": len(worker_calls),
        "workers_completed": len(results),
        "total_emails_fetched": total_emails,
        "total_invoices_found": total_invoices,
        "total_non_invoices": total_non_invoices,
        "total_errors": total_errors,
        "results": results,
    }


@app.local_entrypoint()
def main(batch_size: int = 10, chunk_size: int = 5):
    """Local entrypoint for testing.

    Args:
        batch_size: Maximum emails per worker (default: 10 for testing)
        chunk_size: Emails per transaction chunk (default: 5 for testing)
    """
    print(f"Running scheduler with batch_size={batch_size}, chunk_size={chunk_size}")
    result = scheduler.remote(batch_size=batch_size, chunk_size=chunk_size)
    print(f"\nScheduler Result: {result}")
