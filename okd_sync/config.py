"""
Configuration module for ODK Sync

This module loads environment variables and provides configuration settings
for the application.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

# File to store the last synchronization timestamp
LAST_SYNC_FILE = os.path.join(os.path.dirname(__file__), 'last_sync.txt')

# ODK Central API configuration
ODK_BASE_URL = os.getenv("ODK_BASE_URL", "")
ODK_PROJECT_ID = os.getenv("ODK_PROJECT_ID", "")
ODK_FORM_ID = os.getenv("ODK_FORM_ID", "")

# ODK Central API URLs
SUBMISSIONS_URL = f"{ODK_BASE_URL}/v1/projects/{ODK_PROJECT_ID}/forms/{ODK_FORM_ID}.svc/Submissions"
PERSON_DETAILS_URL = f"{ODK_BASE_URL}/v1/projects/{ODK_PROJECT_ID}/forms/{ODK_FORM_ID}.svc/Submissions.person_details"

# ODK Central credentials
ODATA_USER = os.getenv("ODATA_USER", "")
ODATA_PASS = os.getenv("ODATA_PASS", "")

# ODK Central API credentials (for direct API access)
ODK_CENTRAL_URL = os.getenv("ODK_BASE_URL", "")
ODK_CENTRAL_EMAIL = os.getenv("ODATA_USER", "")
ODK_CENTRAL_PASSWORD = os.getenv("ODATA_PASS", "")

# PostgreSQL connection details
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "postgres")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "postgres")

# AWS S3 configuration
# Use standard AWS SDK environment variable names with fallbacks
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY", ""))
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_KEY", ""))
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", ""))

# Log the AWS credentials being used (with masking for security)
masked_key = AWS_ACCESS_KEY[:4] + "****" + AWS_ACCESS_KEY[-4:] if len(AWS_ACCESS_KEY) > 8 else "Not set"
logging.info(f"Using AWS credentials: {masked_key}, region: {AWS_REGION}, bucket: {AWS_BUCKET_NAME}")

# Construct the S3 URL prefix correctly with region
AWS_S3_URL_PREFIX = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com" if AWS_BUCKET_NAME and AWS_REGION else ""

# S3 folder structure configuration
# Base folder name for storing ODK images (configurable via environment)
S3_BASE_FOLDER = os.getenv("S3_BASE_FOLDER", "odk_images")

# Subfolder names following S3 best practices (lowercase with hyphens)
S3_BUILDING_IMAGES_FOLDER = "building-images"
S3_ADDRESS_PLUS_CODE_FOLDER = "address-plus-code-images" 
S3_PLACEHOLDERS_FOLDER = "placeholders"

# Synchronization settings
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "60"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
PRIORITIZE_NEW = os.getenv("PRIORITIZE_NEW", "true").lower() == "true"

# URL Refresh settings
# How many hours before expiration to refresh URLs (default: 2 hours)
URL_REFRESH_THRESHOLD_HOURS = int(os.getenv("URL_REFRESH_THRESHOLD_HOURS", "2"))
# Enable/disable automatic URL refresh (default: enabled)
ENABLE_URL_REFRESH = os.getenv("ENABLE_URL_REFRESH", "true").lower() == "true"

# Database table names
MAIN_TABLE = "GRARentalDataCollection"
PERSON_DETAILS_TABLE = "GRARentalDataCollection_person_details"
UNIFIED_TABLE = "GRARentalDataCollection_unified"
