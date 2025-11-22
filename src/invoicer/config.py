"""Configuration management for the invoicer application."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Database
    database_url: str

    # S3/R2
    s3_endpoint: str
    s3_bucket: str
    aws_access_key_id: str
    aws_secret_access_key: str

    # OAuth
    google_oauth2_client_id: str
    google_oauth2_client_secret: str

    # Inference
    inference_api_url: str

    # Worker configuration (hardcoded for MVP)
    batch_size: int = 2000
    chunk_size: int = 200

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config: Configuration object

        Raises:
            ValueError: If required environment variables are missing
        """
        required_vars = [
            "DATABASE_URL",
            "S3_ENDPOINT",
            "S3_BUCKET",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "GOOGLE_OAUTH2_CLIENT_ID",
            "GOOGLE_OAUTH2_CLIENT_SECRET",
            "INFERENCE_API_URL",
        ]

        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            database_url=os.getenv("DATABASE_URL"),
            s3_endpoint=os.getenv("S3_ENDPOINT"),
            s3_bucket=os.getenv("S3_BUCKET"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            google_oauth2_client_id=os.getenv("GOOGLE_OAUTH2_CLIENT_ID"),
            google_oauth2_client_secret=os.getenv("GOOGLE_OAUTH2_CLIENT_SECRET"),
            inference_api_url=os.getenv("INFERENCE_API_URL"),
            batch_size=int(os.getenv("BATCH_SIZE", "2000")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "200")),
        )
