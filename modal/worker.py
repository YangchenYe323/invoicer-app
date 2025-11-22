"""Worker function for processing email batches."""

import logging
import time
from typing import Optional

from invoicer import (
    DatabaseClient,
    S3Client,
    EmailParser,
    InferenceClient,
    Invoice,
    AttachedFile,
    ChunkMetrics,
)
from invoicer.config import Config

logger = logging.getLogger(__name__)


def process_chunk(
    emails: list[tuple[int, bytes]],  # List of (uid, rfc822_data)
    source_folder_id: int,
    user_id: str,
    source_id: int,
    folder_name: str,
    uid_validity: str,
    config: Config,
    chunk_num: int,
) -> ChunkMetrics:
    """Process a single chunk of emails.

    Args:
        emails: List of (uid, rfc822_data) tuples
        source_folder_id: Source folder ID
        user_id: User ID for invoice records
        source_id: Source ID for invoice records
        folder_name: Folder name for S3 keys
        uid_validity: UID validity for S3 keys
        config: Application configuration
        chunk_num: Chunk number for metrics

    Returns:
        ChunkMetrics: Metrics for this chunk processing
    """
    start_time = time.perf_counter()

    # Initialize clients
    db = DatabaseClient(config.database_url)
    s3 = S3Client(
        endpoint_url=config.s3_endpoint,
        bucket_name=config.s3_bucket,
        access_key_id=config.aws_access_key_id,
        secret_access_key=config.aws_secret_access_key,
    )
    inference = InferenceClient(api_url=config.inference_api_url)
    parser = EmailParser()

    # Metrics
    emails_fetched = len(emails)
    emails_processed = 0
    invoices_found = 0
    non_invoices = 0
    errors = []
    classification_time = 0.0
    extraction_time = 0.0
    s3_upload_time = 0.0

    # Process each email
    invoices_to_insert = []

    for uid, rfc822_data in emails:
        try:
            # Parse email
            parsed = parser.parse(rfc822_data)

            # Classify
            classify_start = time.perf_counter()
            classification = inference.classify_email(parsed)
            classification_time += time.perf_counter() - classify_start

            if not classification.is_invoice:
                non_invoices += 1
                emails_processed += 1
                continue

            # Extract invoice data
            extract_start = time.perf_counter()
            invoice = inference.extract_invoice(parsed)
            extraction_time += time.perf_counter() - extract_start

            if invoice is None:
                errors.append({"uid": uid, "error": "Invoice extraction returned None"})
                emails_processed += 1
                continue

            # Set database fields
            invoice.user_id = user_id
            invoice.source_id = source_id
            invoice.uid = uid
            invoice.message_id = parsed.message_id

            # Upload attachments to S3
            attached_files = []
            s3_start = time.perf_counter()
            for attachment in parsed.attachments:
                try:
                    s3_key = s3.generate_key(
                        user_id=user_id,
                        source_id=source_id,
                        folder_name=folder_name,
                        uid_validity=uid_validity,
                        message_uid=uid,
                        filename=attachment.filename,
                    )

                    # Check if exists, upload if not
                    if not s3.object_exists(s3_key):
                        s3.upload_attachment(
                            key=s3_key,
                            data=attachment.data,
                            content_type=attachment.content_type,
                        )

                    attached_files.append(
                        AttachedFile(file_name=attachment.filename, file_key=s3_key)
                    )

                except Exception as e:
                    logger.error(f"Failed to upload attachment for UID {uid}: {e}")
                    # S3 failure should fail the chunk
                    raise

            s3_upload_time += time.perf_counter() - s3_start

            # Set attached files
            invoice.attached_files = attached_files

            invoices_to_insert.append(invoice)
            invoices_found += 1
            emails_processed += 1

        except Exception as e:
            logger.error(f"Failed to process email UID {uid}: {e}")
            errors.append({"uid": uid, "error": str(e)})
            # Skip this email, continue with rest
            continue

    # Database transaction (COMMIT LAST!)
    db_start = time.perf_counter()
    try:
        with db.transaction() as conn:
            # Insert invoices
            if invoices_to_insert:
                db.insert_invoices(invoices_to_insert)

            # Update watermarks
            processed_uids = [uid for uid, _ in emails]
            if processed_uids:
                new_high = max(processed_uids)
                new_low = min(processed_uids)

                # Fetch current watermarks
                folder = db.get_source_folder_by_id(source_folder_id)
                if folder:
                    # Update high if this batch has higher UIDs
                    if folder.high_water_mark is None or new_high > folder.high_water_mark:
                        high = new_high
                    else:
                        high = folder.high_water_mark

                    # Update low if this batch has lower UIDs
                    if folder.low_water_mark is None or new_low < folder.low_water_mark:
                        low = new_low
                    else:
                        low = folder.low_water_mark

                    db.update_source_folder_watermarks(
                        folder_id=source_folder_id,
                        high_water_mark=high,
                        low_water_mark=low,
                    )

            # Commit happens here when exiting context manager
    except Exception as e:
        logger.error(f"Database transaction failed for chunk {chunk_num}: {e}")
        # Transaction will rollback automatically
        raise

    db_commit_time = time.perf_counter() - db_start

    # Clean up
    db.close()

    total_time = time.perf_counter() - start_time

    return ChunkMetrics(
        worker_id="",  # Will be set by caller
        source_folder_id=source_folder_id,
        chunk_num=chunk_num,
        emails_fetched=emails_fetched,
        emails_processed=emails_processed,
        invoices_found=invoices_found,
        non_invoices=non_invoices,
        errors=errors,
        duration_sec=total_time,
        classification_time_sec=classification_time,
        extraction_time_sec=extraction_time,
        s3_upload_time_sec=s3_upload_time,
        db_commit_time_sec=db_commit_time,
    )
