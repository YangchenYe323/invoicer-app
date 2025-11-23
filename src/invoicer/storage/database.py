"""Database operations using psycopg (PostgreSQL)."""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from ..models import Source, SourceFolder, Invoice

logger = logging.getLogger(__name__)


def _decimal_to_float(obj):
    """JSON serializer for Decimal objects.

    Args:
        obj: Object to serialize

    Returns:
        float: Decimal converted to float

    Raises:
        TypeError: If object is not Decimal
    """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DatabaseClient:
    """PostgreSQL database client using psycopg."""

    def __init__(self, database_url: str):
        """Initialize database client.

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self._conn: Optional[psycopg.Connection] = None

    def connect(self):
        """Establish database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self.database_url,
                row_factory=dict_row,
                autocommit=False,  # We'll manage transactions explicitly
            )
            logger.info("Database connection established")
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.info("Database connection closed")

    @contextmanager
    def transaction(self):
        """Context manager for database transactions.

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
                # Automatically commits on success, rolls back on exception

        Yields:
            psycopg.Connection: Database connection object
        """
        conn = self.connect()
        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise

    # ========================================================================
    # Source Operations
    # ========================================================================

    def get_all_sources(self) -> list[Source]:
        """Fetch all email sources.

        Returns:
            list[Source]: List of all email sources
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, name, email_address, source_type,
                       oauth2_access_token, oauth2_refresh_token,
                       oauth2_access_token_expires_at, oauth2_refresh_token_expires_at,
                       created_at, updated_at
                FROM source
                ORDER BY id
            """)
            rows = cur.fetchall()
            return [Source(**row) for row in rows]

    def get_source_by_id(self, source_id: int) -> Optional[Source]:
        """Fetch source by ID.

        Args:
            source_id: Source ID to fetch

        Returns:
            Optional[Source]: Source object if found, None otherwise
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, name, email_address, source_type,
                       oauth2_access_token, oauth2_refresh_token,
                       oauth2_access_token_expires_at, oauth2_refresh_token_expires_at,
                       created_at, updated_at
                FROM source
                WHERE id = %s
            """, (source_id,))
            row = cur.fetchone()
            return Source(**row) if row else None

    # ========================================================================
    # Source Folder Operations
    # ========================================================================

    def get_source_folders(self, source_id: int) -> list[SourceFolder]:
        """Fetch all folders for a source.

        Args:
            source_id: Source ID to fetch folders for

        Returns:
            list[SourceFolder]: List of folders for this source
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_id, folder_name, uid_validity,
                       high_water_mark, low_water_mark, last_processed_at,
                       created_at, updated_at
                FROM source_folder
                WHERE source_id = %s
                ORDER BY id
            """, (source_id,))
            rows = cur.fetchall()
            return [SourceFolder(**row) for row in rows]

    def get_source_folder_by_id(self, folder_id: int) -> Optional[SourceFolder]:
        """Fetch source folder by ID.

        Args:
            folder_id: Folder ID to fetch

        Returns:
            Optional[SourceFolder]: SourceFolder object if found, None otherwise
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_id, folder_name, uid_validity,
                       high_water_mark, low_water_mark, last_processed_at,
                       created_at, updated_at
                FROM source_folder
                WHERE id = %s
            """, (folder_id,))
            row = cur.fetchone()
            return SourceFolder(**row) if row else None

    def get_folder_by_name_and_uidvalidity(
        self, source_id: int, folder_name: str, uid_validity: str
    ) -> Optional[SourceFolder]:
        """Fetch folder by source_id, folder_name, and uid_validity.

        Args:
            source_id: Source ID
            folder_name: Folder name (e.g., "INBOX")
            uid_validity: IMAP UIDVALIDITY value

        Returns:
            Optional[SourceFolder]: SourceFolder object if found, None otherwise
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_id, folder_name, uid_validity,
                       high_water_mark, low_water_mark, last_processed_at,
                       created_at, updated_at
                FROM source_folder
                WHERE source_id = %s AND folder_name = %s AND uid_validity = %s
            """, (source_id, folder_name, uid_validity))
            row = cur.fetchone()
            return SourceFolder(**row) if row else None

    def create_source_folder(
        self, source_id: int, folder_name: str, uid_validity: str
    ) -> int:
        """Create a new source folder and return its ID.

        Args:
            source_id: Source ID
            folder_name: Folder name (e.g., "INBOX")
            uid_validity: IMAP UIDVALIDITY value

        Returns:
            int: ID of the newly created folder
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO source_folder
                    (source_id, folder_name, uid_validity, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (source_id, folder_name, uid_validity, datetime.now(), datetime.now()))
            folder_id = cur.fetchone()["id"]
            conn.commit()
            logger.info(f"Created source_folder id={folder_id} for source={source_id}, folder={folder_name}")
            return folder_id

    def update_source_folder_watermarks(
        self,
        folder_id: int,
        high_water_mark: Optional[int],
        low_water_mark: Optional[int],
    ):
        """Update watermarks for a source folder.

        Args:
            folder_id: Folder ID to update
            high_water_mark: Highest UID processed (or None)
            low_water_mark: Lowest UID processed (or None)

        Note:
            This should be called within a transaction context.
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE source_folder
                SET high_water_mark = %s,
                    low_water_mark = %s,
                    last_processed_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (high_water_mark, low_water_mark, datetime.now(), datetime.now(), folder_id))
            logger.debug(f"Updated watermarks for folder_id={folder_id}: high={high_water_mark}, low={low_water_mark}")

    # ========================================================================
    # Invoice Operations
    # ========================================================================

    def insert_invoices(self, invoices: list[Invoice]):
        """Bulk insert invoices.

        Args:
            invoices: List of Invoice objects to insert

        Note:
            This should be called within a transaction context.
        """
        if not invoices:
            return

        conn = self.connect()
        with conn.cursor() as cur:
            # Prepare values for bulk insert
            values = []
            for inv in invoices:
                values.append((
                    inv.user_id,
                    inv.source_id,
                    inv.uid,
                    inv.message_id,
                    inv.invoice_number,
                    inv.vendor_name,
                    inv.due_date,
                    inv.total_amount,
                    inv.currency,
                    inv.payment_status,
                    json.dumps([item.model_dump(by_alias=True) for item in inv.line_items], default=_decimal_to_float),
                    json.dumps([file.model_dump(by_alias=True) for file in inv.attached_files], default=_decimal_to_float),
                    datetime.now(),  # created_at
                    datetime.now(),  # updated_at
                ))

            # Bulk insert with conflict handling
            # ON CONFLICT DO NOTHING ignores duplicate invoice_number (guards against concurrent workers)
            cur.executemany("""
                INSERT INTO invoice (
                    user_id, source_id, uid, message_id,
                    invoice_number, vendor_name, due_date,
                    total_amount, currency, payment_status,
                    line_items, attached_files,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (invoice_number) DO NOTHING
            """, values)

            logger.info(f"Inserted {len(invoices)} invoices (duplicates skipped)")

    def delete_all_invoices(self) -> int:
        """Delete all invoices (for testing/rollback).

        Returns:
            int: Number of invoices deleted
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM invoice")
            deleted = cur.rowcount
            conn.commit()
            logger.warning(f"Deleted {deleted} invoices")
            return deleted

    def delete_all_source_folders(self) -> int:
        """Delete all source folders (for testing/rollback).

        Returns:
            int: Number of source folders deleted
        """
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM source_folder")
            deleted = cur.rowcount
            conn.commit()
            logger.warning(f"Deleted {deleted} source folders")
            return deleted
