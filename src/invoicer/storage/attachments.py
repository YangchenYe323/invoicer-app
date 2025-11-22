"""S3/R2 storage for email attachments using boto3."""

import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Client:
    """S3-compatible storage client (supports Cloudflare R2)."""

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
    ):
        """Initialize S3 client.

        Args:
            endpoint_url: S3 endpoint URL (for R2: https://<account>.r2.cloudflarestorage.com)
            bucket_name: S3 bucket name
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        logger.info(f"S3 client initialized for bucket: {bucket_name}")

    def generate_key(
        self,
        user_id: str,
        source_id: int,
        folder_name: str,
        uid_validity: str,
        message_uid: int,
        filename: str,
    ) -> str:
        """Generate S3 object key.

        Format: {user_id}/{source_id}/{folder}/{uid_validity}/{message_uid}/{filename}
        """
        # Sanitize filename (remove path separators)
        safe_filename = Path(filename).name
        key = f"{user_id}/{source_id}/{folder_name}/{uid_validity}/{message_uid}/{safe_filename}"
        return key

    def object_exists(self, key: str) -> bool:
        """Check if object exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                logger.error(f"Error checking object existence: {e}")
                raise

    def upload_attachment(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ):
        """Upload attachment to S3.

        Args:
            key: S3 object key
            data: File data as bytes
            content_type: MIME type of the file
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.debug(f"Uploaded attachment: {key} ({len(data)} bytes)")
        except ClientError as e:
            logger.error(f"Error uploading attachment {key}: {e}")
            raise

    def download_attachment(self, key: str) -> bytes:
        """Download attachment from S3 (for testing).

        Args:
            key: S3 object key

        Returns:
            File data as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = response["Body"].read()
            logger.debug(f"Downloaded attachment: {key} ({len(data)} bytes)")
            return data
        except ClientError as e:
            logger.error(f"Error downloading attachment {key}: {e}")
            raise

    def delete_all_objects_with_prefix(self, prefix: str) -> int:
        """Delete all objects with a given prefix (for testing/cleanup).

        Args:
            prefix: Object key prefix (e.g., "user123/")

        Returns:
            Number of objects deleted
        """
        try:
            # List objects
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )

            if "Contents" not in response:
                logger.info(f"No objects found with prefix: {prefix}")
                return 0

            # Delete objects
            objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
            delete_response = self.s3_client.delete_objects(
                Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
            )

            deleted_count = len(delete_response.get("Deleted", []))
            logger.warning(f"Deleted {deleted_count} objects with prefix: {prefix}")
            return deleted_count

        except ClientError as e:
            logger.error(f"Error deleting objects with prefix {prefix}: {e}")
            raise
