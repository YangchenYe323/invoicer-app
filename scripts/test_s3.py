"""Test S3/R2 access with environment variables."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load from .env file if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}\n")
    else:
        print(f"No .env file found at {env_file}")
        print("Using system environment variables\n")
except ImportError:
    print("python-dotenv not installed, using system environment variables\n")

from invoicer.storage.attachments import S3Client


def test_s3_access():
    """Test S3 operations."""

    # Get credentials from environment
    endpoint = os.getenv("S3_ENDPOINT")
    bucket = os.getenv("S3_BUCKET")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    print("Configuration:")
    print(f"  Endpoint: {endpoint}")
    print(f"  Bucket: {bucket}")
    print(f"  Access Key: {access_key[:10]}..." if access_key else "  Access Key: None")
    print(f"  Secret Key: {'***' if secret_key else 'None'}")
    print()

    if not all([endpoint, bucket, access_key, secret_key]):
        print("ERROR: Missing required environment variables:")
        print("  S3_ENDPOINT, S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        return False

    # Create S3 client
    print("Creating S3 client...")
    s3 = S3Client(
        endpoint_url=endpoint,
        bucket_name=bucket,
        access_key_id=access_key,
        secret_access_key=secret_key,
    )
    print(f"✓ S3 client initialized for bucket: {bucket}\n")

    # Test 1: List objects
    print("Test 1: List objects in bucket")
    try:
        response = s3.s3_client.list_objects_v2(Bucket=bucket, MaxKeys=5)
        if 'Contents' in response:
            print(f"✓ Found {len(response.get('Contents', []))} objects")
            for obj in response.get('Contents', [])[:3]:
                print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("✓ Bucket is empty or no objects found")
    except Exception as e:
        print(f"✗ Failed to list objects: {e}")
        return False
    print()

    # Test 2: Upload a test file
    print("Test 2: Upload test file")
    test_key = "test/test_upload.txt"
    test_data = b"Hello from S3 test script!"

    try:
        s3.upload_attachment(
            key=test_key,
            data=test_data,
            content_type="text/plain",
        )
        print(f"✓ Uploaded test file: {test_key}")
    except Exception as e:
        print(f"✗ Failed to upload: {e}")
        return False
    print()

    # Test 3: Check if object exists (this is where 403 error occurred)
    print("Test 3: Check object existence (HEAD request)")
    try:
        exists = s3.object_exists(test_key)
        if exists:
            print(f"✓ Object exists: {test_key}")
        else:
            print(f"✗ Object does not exist: {test_key}")
            return False
    except Exception as e:
        print(f"✗ Failed to check existence: {e}")
        print(f"    This is likely the 403 Forbidden error you saw!")
        return False
    print()

    # Test 4: Download the file
    print("Test 4: Download test file")
    try:
        downloaded_data = s3.download_attachment(test_key)
        if downloaded_data == test_data:
            print(f"✓ Downloaded and verified: {len(downloaded_data)} bytes")
        else:
            print(f"✗ Downloaded data doesn't match")
            return False
    except Exception as e:
        print(f"✗ Failed to download: {e}")
        return False
    print()

    # Test 5: Delete the test file
    print("Test 5: Delete test file")
    try:
        s3.s3_client.delete_object(Bucket=bucket, Key=test_key)
        print(f"✓ Deleted: {test_key}")
    except Exception as e:
        print(f"✗ Failed to delete: {e}")
        return False
    print()

    print("=" * 60)
    print("All S3 tests passed! ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_s3_access()
    sys.exit(0 if success else 1)
