#!/usr/bin/env python3
"""
Script to delete S3 images from odk_images and placeholders folders
"""
import boto3
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# AWS S3 configuration
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "rtcs-gm-images")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION", "af-south-1")

def delete_s3_folder(prefix):
    """Delete all objects in an S3 folder"""
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
            endpoint_url=f'https://s3.{AWS_REGION}.amazonaws.com'
        )
        
        # List objects in the folder
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=AWS_BUCKET_NAME, Prefix=prefix)
        
        # Count deleted objects
        deleted_count = 0
        
        # Process each page of objects
        for page in pages:
            if 'Contents' in page:
                # Get list of objects to delete
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                
                # Delete objects
                if objects_to_delete:
                    s3_client.delete_objects(
                        Bucket=AWS_BUCKET_NAME,
                        Delete={'Objects': objects_to_delete}
                    )
                    deleted_count += len(objects_to_delete)
                    logger.info(f"Deleted {len(objects_to_delete)} objects from {prefix}")
        
        logger.info(f"Total objects deleted from {prefix}: {deleted_count}")
        return deleted_count
    
    except Exception as e:
        logger.error(f"Error deleting objects from {prefix}: {e}")
        return 0

if __name__ == "__main__":
    # Delete images from odk_images folder
    odk_count = delete_s3_folder('odk_images/')
    
    # Delete images from placeholders folder
    placeholders_count = delete_s3_folder('placeholders/')
    
    logger.info(f"Total objects deleted: {odk_count + placeholders_count}")
