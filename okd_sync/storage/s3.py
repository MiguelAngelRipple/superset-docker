"""
S3 storage operations module
"""
import os
import json
import logging
import tempfile
import shutil
import threading
import concurrent.futures
from queue import PriorityQueue
from datetime import datetime
from urllib.parse import urlparse, unquote

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image, ImageDraw, ImageFont

from config import (
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_BUCKET_NAME,
    AWS_REGION,
    ODK_CENTRAL_URL,
    ODK_CENTRAL_EMAIL,
    ODK_CENTRAL_PASSWORD,
    ODK_PROJECT_ID,
    ODK_FORM_ID,
    ODK_BASE_URL,
    S3_BASE_FOLDER,
    S3_BUILDING_IMAGES_FOLDER,
    S3_ADDRESS_PLUS_CODE_FOLDER,
    S3_PLACEHOLDERS_FOLDER
)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Construct the S3 URL prefix
AWS_S3_URL_PREFIX = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

# Global session for ODK Central API
odk_session = None

# Get an S3 client
def get_s3_client():
    """
    Get an S3 client
    
    Returns:
        boto3.client: S3 client
    """
    # Create a boto3 session with explicit credentials
    logger.info(f"Creating S3 client with region: {AWS_REGION}")
    
    # For af-south-1 region, we need to use the specific endpoint
    endpoint_url = f"https://s3.{AWS_REGION}.amazonaws.com"
    
    # Log credentials (masked) for debugging
    masked_key = AWS_ACCESS_KEY[:4] + "****" + AWS_ACCESS_KEY[-4:] if AWS_ACCESS_KEY else None
    logger.info(f"Using AWS credentials: {masked_key}, region: {AWS_REGION}, endpoint: {endpoint_url}")
    
    # Create a boto3 client with explicit configuration
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
        endpoint_url=endpoint_url
    )


def get_odk_session():
    """
    Get or create a session for ODK Central API
    
    Returns:
        requests.Session: Session for ODK Central API
    """
    global odk_session
    
    if odk_session is not None:
        return odk_session
    
    if not ODK_CENTRAL_URL or not ODK_CENTRAL_EMAIL or not ODK_CENTRAL_PASSWORD:
        logger.error("ODK Central credentials not configured")
        return None
    
    try:
        # Create a session
        session = requests.Session()
        
        # Authenticate with ODK Central
        auth_url = f"{ODK_CENTRAL_URL}/v1/sessions"
        auth_data = {
            "email": ODK_CENTRAL_EMAIL,
            "password": ODK_CENTRAL_PASSWORD
        }
        
        response = session.post(auth_url, json=auth_data)
        
        if response.status_code == 200:
            # Store the session token
            token = response.json().get('token')
            session.headers.update({
                "Authorization": f"Bearer {token}"
            })
            
            odk_session = session
            logger.info("Successfully authenticated with ODK Central")
            return session
        else:
            logger.error(f"Failed to authenticate with ODK Central: {response.status_code} {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error authenticating with ODK Central: {e}")
        return None


def generate_s3_file_path(submission_id, attachment_field, filename):
    """
    Generate S3 file path based on attachment field type
    
    Args:
        submission_id: ID of the submission
        attachment_field: Type of attachment ('building_image' or 'address_plus_code')
        filename: Name of the file
        
    Returns:
        str: S3 file path
    """
    # Determine the appropriate subfolder based on attachment field
    if attachment_field == 'building_image':
        subfolder = S3_BUILDING_IMAGES_FOLDER
    elif attachment_field == 'address_plus_code':
        subfolder = S3_ADDRESS_PLUS_CODE_FOLDER
    else:
        # Default to building images folder for unknown types
        subfolder = S3_BUILDING_IMAGES_FOLDER
        logger.warning(f"Unknown attachment field '{attachment_field}', using building images folder")
    
    # Generate the full S3 path: base_folder/subfolder/submission_id-filename
    s3_file_path = f"{S3_BASE_FOLDER}/{subfolder}/{submission_id}-{filename}"
    
    logger.debug(f"Generated S3 path for {attachment_field}: {s3_file_path}")
    return s3_file_path


def generate_signed_url(s3_key, expires=86400):
    """
    Generate a signed URL for an S3 object
    
    Args:
        s3_key: S3 key of the object
        expires: Expiration time in seconds (default: 24 hours)
        
    Returns:
        str: Signed URL for the S3 object
    """
    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY or not AWS_BUCKET_NAME or not AWS_REGION:
        logger.error("AWS credentials not configured")
        return None
    
    try:
        # Generate a signed URL using the boto3 client
        # Importante: Configurar el cliente con la región correcta
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
            # Usar el endpoint correcto para la región
            endpoint_url=f'https://s3.{AWS_REGION}.amazonaws.com'
        )
        
        # Generate a signed URL for the S3 object
        # No modificar la URL después de generarla para evitar problemas de firma
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWS_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expires
        )
        
        # No modificar la URL firmada, ya que esto invalidaría la firma
        logger.info(f"Generated signed URL for {s3_key} (expires in {expires} seconds)")
        return signed_url
    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return None

def upload_to_s3(file_data, s3_file_name):
    """
    Upload a file to S3 and return a signed URL
    
    Args:
        file_data: File data or path to upload
        s3_file_name: Name of the file in S3
        
    Returns:
        str: Signed URL of the uploaded file
    """
    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY or not AWS_BUCKET_NAME:
        logger.warning("AWS credentials not configured. Cannot upload to S3.")
        return None
    
    try:
        # Create an S3 client with explicit endpoint
        endpoint_url = f"https://s3.{AWS_REGION}.amazonaws.com"
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
            endpoint_url=endpoint_url
        )
        
        logger.info(f"Proceeding with upload to S3: {s3_file_name} (region: {AWS_REGION})")
        
        # If file_data is a file path, upload directly
        if isinstance(file_data, str) and os.path.isfile(file_data):
            logger.info(f"Uploading file from path: {file_data} to {s3_file_name}")
            # Use put_object instead of upload_file for more control
            with open(file_data, 'rb') as f:
                file_content = f.read()
                s3_client.put_object(
                    Body=file_content,
                    Bucket=AWS_BUCKET_NAME,
                    Key=s3_file_name,
                    ContentType='image/jpeg'  # Set appropriate content type
                )
        # If file_data is a URL, download first
        elif isinstance(file_data, str) and (file_data.startswith('http://') or file_data.startswith('https://')):
            logger.info(f"Downloading from URL and uploading to S3: {file_data}")
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                try:
                    response = requests.get(file_data, stream=True)
                    if response.status_code == 200:
                        with open(temp_file.name, 'wb') as f:
                            response.raw.decode_content = True
                            shutil.copyfileobj(response.raw, f)
                        
                        # Use put_object instead of upload_file
                        with open(temp_file.name, 'rb') as f:
                            file_content = f.read()
                            s3_client.put_object(
                                Body=file_content,
                                Bucket=AWS_BUCKET_NAME,
                                Key=s3_file_name,
                                ContentType='image/jpeg'  # Set appropriate content type
                            )
                    else:
                        logger.error(f"Failed to download file from {file_data}, status code: {response.status_code}")
                        return None
                except Exception as e:
                    logger.error(f"Error downloading file from {file_data}: {e}")
                    return None
                finally:
                    # Clean up the temporary file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
        # If file_data is binary data, upload directly
        else:
            logger.info(f"Uploading binary data to S3: {s3_file_name}")
            s3_client.put_object(
                Body=file_data, 
                Bucket=AWS_BUCKET_NAME, 
                Key=s3_file_name,
                ContentType='image/jpeg'  # Set appropriate content type
            )
        
        logger.info(f"Successfully uploaded file to S3: {s3_file_name}")
        
        # Generate a signed URL for the uploaded file
        return generate_signed_url(s3_file_name)
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        return None

def download_and_upload_attachment(submission_id, attachment_field, attachment_url):
    """
    Downloads an attachment from ODK Central and uploads it to S3.
    Returns the signed URL of the uploaded file.
    
    Args:
        submission_id: ID of the submission
        attachment_field: Name of the attachment field
        attachment_url: URL or filename of the attachment
        
    Returns:
        str: Signed URL of the uploaded file in S3
    """
    if not attachment_url:
        logger.warning(f"No attachment URL provided for {submission_id} {attachment_field}")
        return None
    
    # Check if the attachment_url is just a filename
    if not attachment_url.startswith('http'):
        logger.info(f"Using value as filename: {attachment_url}")
        
        # First, check if the file exists locally
        local_path = os.path.join('downloads', attachment_url)
        if os.path.exists(local_path):
            logger.info(f"Found local file at {local_path}")
            # Upload the local file to S3 and get a signed URL
            s3_file_name = generate_s3_file_path(submission_id, attachment_field, attachment_url)
            return upload_to_s3(local_path, s3_file_name)
        
        # If not found locally, try to construct the ODK Central URL
        if ODK_CENTRAL_URL and ODK_PROJECT_ID and ODK_FORM_ID:
            # Replace spaces with %20 in the URL
            safe_url = attachment_url.replace(' ', '%20')
            download_url = f"{ODK_CENTRAL_URL}/v1/projects/{ODK_PROJECT_ID}/forms/{ODK_FORM_ID}/submissions/{submission_id}/attachments/{safe_url}"
            logger.info(f"Constructed download URL: {download_url}")
        else:
            logger.error("ODK Central URL, project ID, or form ID not configured")
            return None
    else:
        download_url = attachment_url
    
    try:
        # Get or create the ODK Central session
        session = get_odk_session()
        if not session:
            logger.error("Could not create ODK Central session")
            return None
        
        # Download the attachment
        response = session.get(download_url, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to download attachment: {response.status_code} {response.text}")
            return None
        
        # Create a temporary file to store the downloaded attachment
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write the attachment to the temporary file
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    temp_file.write(chunk)
            
            # Get the file size
            temp_file.flush()
            file_size = os.path.getsize(temp_file.name)
            logger.info(f"Downloaded file size: {file_size} bytes")
            
            # Check if the file is empty or too small
            if file_size < 100:  # Arbitrary small size threshold
                logger.warning(f"Downloaded file is too small ({file_size} bytes), might be corrupted")
            
            # Upload the file to S3 and get a signed URL
            s3_file_name = generate_s3_file_path(submission_id, attachment_field, os.path.basename(attachment_url))
            s3_url = upload_to_s3(temp_file.name, s3_file_name)
            
            # Clean up the temporary file
            os.unlink(temp_file.name)
            
            return s3_url
    except Exception as e:
        logger.error(f"Error processing attachment: {e}")
        return None

def generate_image_html(image_url, width="100%", height="100%", is_placeholder=False):
    """
    Generate HTML to display an image in Superset
    
    Args:
        image_url: URL of the image (signed URL)
        width: Width of the image (default: 100%)
        height: Height of the image (default: 100%)
        is_placeholder: Whether this is a placeholder image
        
    Returns:
        str: HTML string for displaying the image
    """
    if not image_url:
        return ""
    
    placeholder_class = " placeholder-image" if is_placeholder else ""
    
    # Escape any quotes in the URL to prevent HTML injection
    safe_url = image_url.replace('"', '&quot;')
    
    # Create responsive HTML with the signed URL - using single quotes for HTML attributes
    html = f'<div class="image-container{placeholder_class}">'
    html += f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">'
    html += f'<img src="{safe_url}" width="{width}" height="{height}" '
    html += f'style="object-fit: cover; border-radius: 4px; max-width: 100%;" '
    html += f'loading="lazy" alt="Building Image" />'
    html += f'</a>'
    html += f'</div>'
    
    return html

def create_placeholder_image(submission_id, width=300, height=200):
    """
    Create a placeholder image for submissions without images
    
    Args:
        submission_id: ID of the submission
        width: Width of the image in pixels
        height: Height of the image in pixels
        
    Returns:
        str: Path to the created placeholder image
    """
    try:
        import os
        from PIL import Image, ImageDraw, ImageFont
        import tempfile
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Create a blank image with a light gray background
        image = Image.new('RGB', (width, height), color=(240, 240, 240))
        draw = ImageDraw.Draw(image)
        
        # Draw a border
        draw.rectangle([(0, 0), (width-1, height-1)], outline=(200, 200, 200), width=2)
        
        # Add text
        try:
            # Try to use a system font
            font = ImageFont.truetype("DejaVuSans.ttf", 20)
        except IOError:
            # Fallback to default font
            font = ImageFont.load_default()
        
        # Draw text in the center
        text = "No Image Available"
        text_width = draw.textlength(text, font=font) if hasattr(draw, 'textlength') else font.getsize(text)[0]
        text_position = ((width - text_width) // 2, height // 2 - 10)
        draw.text(text_position, text, fill=(100, 100, 100), font=font)
        
        # Add submission ID at the bottom
        id_text = f"ID: {submission_id[:8]}..."
        id_width = draw.textlength(id_text, font=font) if hasattr(draw, 'textlength') else font.getsize(id_text)[0]
        id_position = ((width - id_width) // 2, height - 30)
        draw.text(id_position, id_text, fill=(100, 100, 100), font=font)
        
        # Save the image
        image.save(temp_path)
        logger.info(f"Created placeholder image at {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error creating placeholder image: {e}")
        return None

def extract_building_image(submission):
    """
    Extract building_image from property_description
    
    Args:
        submission: Submission record
        
    Returns:
        str: Building image URL or filename
    """
    if 'property_description' not in submission:
        return None
    
    prop_desc = submission['property_description']
    
    # Handle string JSON
    if isinstance(prop_desc, str):
        try:
            prop_desc = json.loads(prop_desc)
        except:
            logger.warning(f"Could not parse property_description as JSON")
            return None
    
    # Extract building_image
    if isinstance(prop_desc, dict) and 'building_image' in prop_desc:
        return prop_desc.get('building_image')
    
    return None

def extract_address_plus_code(submission):
    """
    Extract address_plus_code_image from property_location
    
    Args:
        submission: Submission record
        
    Returns:
        str: Address plus code image URL or filename
    """
    if 'property_location' not in submission:
        return None
    
    prop_location = submission['property_location']
    
    # Handle string JSON
    if isinstance(prop_location, str):
        try:
            prop_location = json.loads(prop_location)
        except:
            logger.warning(f"Could not parse property_location as JSON")
            return None
    
    # Extract address_plus_code_image (correct field name)
    if isinstance(prop_location, dict) and 'address_plus_code_image' in prop_location:
        return prop_location.get('address_plus_code_image')
    
    return None

def process_attachments(submissions, max_workers=10, prioritize_new=True):
    """
    Process submissions to download attachments, upload them to S3,
    and update the submission records with S3 URLs.
    
    Args:
        submissions: List of submission records to process
        max_workers: Maximum number of concurrent workers for parallel processing
        prioritize_new: If True, prioritize processing new submissions first
        
    Returns:
        list: Updated submission records with S3 URLs
    """
    if not submissions:
        return submissions
    
    # Check if AWS credentials are configured
    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY or not AWS_BUCKET_NAME:
        logger.warning("AWS credentials not configured. Skipping attachment processing.")
        return submissions
    
    # Get existing submission IDs to avoid reprocessing
    from db.sqlalchemy_models import MainSubmission, engine
    from sqlalchemy.orm import Session
    
    # Función para obtener IDs de envíos existentes usando SQLAlchemy
    def get_existing_submission_ids():
        session = Session(engine)
        try:
            ids = [id[0] for id in session.query(MainSubmission.UUID).all() if id[0]]
            logger.info(f"Found {len(ids)} existing submissions in the database")
            return set(ids)
        except Exception as e:
            logger.error(f"Error getting existing submission IDs: {e}")
            return set()
        finally:
            session.close()
    
    existing_submissions = get_existing_submission_ids()
    logger.info(f"Found {len(existing_submissions)} existing submissions in the database")
    
    # Create a thread-safe dictionary to store results
    results_dict = {}
    results_lock = threading.Lock()
    
    # Create a priority queue for submissions
    # Lower priority number = higher priority
    submission_queue = PriorityQueue()
    
    # Add submissions to the queue with appropriate priorities
    for idx, submission in enumerate(submissions):
        submission_id = submission.get('UUID') or submission.get('__id')
        
        # Skip if already processed and has building_image_url
        if existing_submissions and submission_id in existing_submissions and submission.get('building_image_url'):
            continue
        
        # Determine priority: new submissions get priority 0, existing get priority 1
        priority = 1
        if prioritize_new and (not existing_submissions or submission_id not in existing_submissions):
            priority = 0
        
        # Add to queue with (priority, index, submission) to ensure stable sorting
        submission_queue.put((priority, idx, submission))
    
    # Process a single submission
    def process_single_submission(queue_item):
        priority, idx, submission = queue_item
        submission_id = submission.get('UUID') or submission.get('__id')
        
        try:
            # Initialize result data for this submission
            submission_result = {}
            
            # Process building_image from property_description
            building_image = extract_building_image(submission)
            
            if building_image:
                # Upload to S3 and get a signed URL
                s3_url = download_and_upload_attachment(submission_id, 'building_image', building_image)
                if s3_url:
                    # Store building image data
                    submission_result['building_image'] = {
                        'url': s3_url,
                        'html': generate_image_html(s3_url)
                    }
                    logger.info(f"Uploaded building_image to S3 with signed URL: {s3_url}")
            else:
                # Try to upload a placeholder if no image was found
                logger.warning(f"No building_image found for submission {submission_id}, attempting to create placeholder")
                placeholder_path = create_placeholder_image(submission_id)
                if placeholder_path:
                    # Upload the placeholder and get a signed URL
                    s3_url = upload_to_s3(placeholder_path, f"{S3_BASE_FOLDER}/{S3_PLACEHOLDERS_FOLDER}/{submission_id}.png")
                    if s3_url:
                        # Store building image data
                        submission_result['building_image'] = {
                            'url': s3_url,
                            'html': generate_image_html(s3_url, is_placeholder=True)
                        }
                        logger.info(f"Uploaded placeholder image to S3 with signed URL: {s3_url}")
            
            # Process address_plus_code from property_location
            address_plus_code = extract_address_plus_code(submission)
            
            if address_plus_code:
                # Upload to S3 and get a signed URL
                s3_url = download_and_upload_attachment(submission_id, 'address_plus_code', address_plus_code)
                if s3_url:
                    # Store address plus code data
                    submission_result['address_plus_code'] = {
                        'url': s3_url,
                        'html': generate_image_html(s3_url)
                    }
                    logger.info(f"Uploaded address_plus_code to S3 with signed URL: {s3_url}")
            else:
                logger.debug(f"No address_plus_code found for submission {submission_id}")
            
            # Store results in the dictionary if we have any data
            if submission_result:
                with results_lock:
                    results_dict[submission_id] = submission_result
            
            return True
        except Exception as e:
            logger.error(f"Error processing submission {submission_id}: {e}")
            return False
    
    # Process submissions in parallel
    processed_count = 0
    total_count = submission_queue.qsize()
    
    if total_count > 0:
        logger.info(f"Processing attachments from {total_count} submissions using {max_workers} parallel workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # Submit all tasks to the executor
            while not submission_queue.empty():
                queue_item = submission_queue.get()
                futures.append(executor.submit(process_single_submission, queue_item))
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_count:
                    logger.info(f"Processed {processed_count}/{total_count} submissions")
    
    # Update submissions with S3 URLs
    building_image_count = 0
    address_plus_code_count = 0
    
    for submission in submissions:
        submission_id = submission.get('UUID') or submission.get('__id')
        if submission_id in results_dict:
            result = results_dict[submission_id]
            
            # Handle building image (old format compatibility)
            if 'url' in result:
                submission['building_image_url'] = result['url']
                building_image_count += 1
            # Handle building image (new format)
            elif 'building_image' in result:
                submission['building_image_url'] = result['building_image']['url']
                building_image_count += 1
            
            # Handle address plus code image
            if 'address_plus_code' in result:
                submission['address_plus_code_url'] = result['address_plus_code']['url']
                address_plus_code_count += 1
    
    logger.info(f"Attachment process completed: {processed_count} submissions processed, {building_image_count} building images uploaded, {address_plus_code_count} address plus code images uploaded")
    return submissions

def refresh_expired_urls(max_workers=5):
    """
    Refresh expired or soon-to-expire S3 URLs in the database.
    
    This function checks existing database records for URLs that are expired
    or will expire soon (configurable threshold) and regenerates fresh signed URLs.
    Now includes both building_image_url and address_plus_code_url fields.
    
    Args:
        max_workers: Maximum number of concurrent workers for parallel processing
        
    Returns:
        int: Number of URLs refreshed
    """
    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY or not AWS_BUCKET_NAME:
        logger.warning("AWS credentials not configured. Cannot refresh URLs.")
        return 0
    
    from db.sqlalchemy_models import MainSubmission, engine
    from sqlalchemy.orm import Session
    from urllib.parse import urlparse, parse_qs
    from datetime import datetime, timedelta
    import concurrent.futures
    import re
    
    logger.info("Starting URL refresh process for expired/expiring URLs...")
    
    # Get records with image URLs from database
    session = Session(engine)
    try:
        # Get all records that have building_image_url or address_plus_code_url
        records = session.query(MainSubmission).filter(
            (
                MainSubmission.building_image_url.isnot(None) &
                (MainSubmission.building_image_url != '')
            ) |
            (
                MainSubmission.address_plus_code_url.isnot(None) &
                (MainSubmission.address_plus_code_url != '')
            )
        ).all()
        
        logger.info(f"Found {len(records)} records with image URLs to check")
        
        if not records:
            return 0
        
        # Import threshold configuration
        from config import URL_REFRESH_THRESHOLD_HOURS
        
        # Function to check if URL is expired or will expire soon
        def is_url_expired_soon(url, hours_threshold=URL_REFRESH_THRESHOLD_HOURS):
            """Check if S3 signed URL is expired or will expire within threshold hours"""
            if not url or 'Expires=' not in url:
                return True  # Treat as expired if no expiration found
            
            try:
                # Extract expiration timestamp from URL
                expires_match = re.search(r'Expires=(\d+)', url)
                if not expires_match:
                    return True
                
                expires_timestamp = int(expires_match.group(1))
                expires_datetime = datetime.fromtimestamp(expires_timestamp)
                threshold_datetime = datetime.now() + timedelta(hours=hours_threshold)
                
                is_expiring = expires_datetime <= threshold_datetime
                if is_expiring:
                    logger.debug(f"URL expires at {expires_datetime}, threshold is {threshold_datetime}")
                
                return is_expiring
                
            except Exception as e:
                logger.warning(f"Could not parse expiration from URL: {e}")
                return True  # Treat as expired if parsing fails
        
        # Filter records that need URL refresh
        records_to_refresh = []
        for record in records:
            needs_refresh = False
            
            # Check building_image_url if it exists
            if record.building_image_url and record.building_image_url.strip():
                if is_url_expired_soon(record.building_image_url):
                    needs_refresh = True
            
            # Check address_plus_code_url if it exists
            if record.address_plus_code_url and record.address_plus_code_url.strip():
                if is_url_expired_soon(record.address_plus_code_url):
                    needs_refresh = True
            
            if needs_refresh:
                records_to_refresh.append(record)
        
        logger.info(f"Found {len(records_to_refresh)} URLs that need refreshing")
        
        if not records_to_refresh:
            logger.info("No URLs need refreshing at this time")
            return 0
        
        # Function to refresh a single record's URLs
        def refresh_single_url(record):
            """
            Refresh URLs for a single record. Handles both building_image_url 
            and address_plus_code_url fields.
            
            Returns:
                int: Number of URLs successfully refreshed (0, 1, or 2)
            """
            refresh_count = 0
            
            # Helper function to refresh a single URL field
            def refresh_url_field(url, field_name):
                if not url or not url.strip():
                    return False
                    
                try:
                    # Parse S3 key from URL - handle both path styles
                    if AWS_BUCKET_NAME in url:
                        # Extract key after bucket name
                        if f"{AWS_BUCKET_NAME}.s3." in url:
                            # Virtual hosted-style URL
                            key_match = re.search(f'https://{re.escape(AWS_BUCKET_NAME)}\\.s3\\.[^/]+/([^?]+)', url)
                        else:
                            # Path-style URL
                            key_match = re.search(f'/{re.escape(AWS_BUCKET_NAME)}/([^?]+)', url)
                        
                        if key_match:
                            s3_key = key_match.group(1)
                            
                            # URL decode the S3 key to prevent double encoding
                            # This is critical because the extracted key might already be URL encoded
                            # We need to decode multiple times in case of nested encoding
                            from urllib.parse import unquote
                            
                            # Keep unquoting until no more changes occur (handles multiple encoding levels)
                            original_key = s3_key
                            previous_key = None
                            decode_attempts = 0
                            
                            while previous_key != s3_key and decode_attempts < 10:  # Safety limit
                                previous_key = s3_key
                                s3_key = unquote(s3_key)
                                decode_attempts += 1
                            
                            logger.debug(f"S3 key decoding for {field_name}: '{original_key}' -> '{s3_key}' (attempts: {decode_attempts})")
                            
                            # Generate new signed URL
                            new_signed_url = generate_signed_url(s3_key)
                            
                            if new_signed_url:
                                # Update record in database
                                setattr(record, field_name, new_signed_url)
                                logger.info(f"Refreshed {field_name} URL for submission {record.UUID}")
                                return True
                            else:
                                logger.error(f"Failed to generate new signed URL for {field_name} in {record.UUID}")
                                return False
                        else:
                            logger.error(f"Could not extract S3 key from {field_name} URL: {url}")
                            return False
                    else:
                        logger.error(f"{field_name} URL does not contain expected bucket name: {url}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error refreshing {field_name} URL for record {record.UUID}: {e}")
                    return False
            
            try:
                # Refresh building_image_url if it exists and needs refresh
                if record.building_image_url and record.building_image_url.strip():
                    if is_url_expired_soon(record.building_image_url):
                        if refresh_url_field(record.building_image_url, 'building_image_url'):
                            refresh_count += 1
                
                # Refresh address_plus_code_url if it exists and needs refresh
                if record.address_plus_code_url and record.address_plus_code_url.strip():
                    if is_url_expired_soon(record.address_plus_code_url):
                        if refresh_url_field(record.address_plus_code_url, 'address_plus_code_url'):
                            refresh_count += 1
                
                return refresh_count
                
            except Exception as e:
                logger.error(f"Error refreshing URLs for record {record.UUID}: {e}")
                return 0
        
        # Process URLs in parallel
        total_refreshed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_record = {
                executor.submit(refresh_single_url, record): record 
                for record in records_to_refresh
            }
            
            for future in concurrent.futures.as_completed(future_to_record):
                record = future_to_record[future]
                try:
                    refresh_count = future.result()
                    total_refreshed_count += refresh_count
                except Exception as e:
                    logger.error(f"Error in URL refresh thread for {record.UUID}: {e}")
        
        # Commit all changes
        if total_refreshed_count > 0:
            session.commit()
            logger.info(f"Successfully refreshed {total_refreshed_count} URLs in database")
        
        return total_refreshed_count
        
    except Exception as e:
        logger.error(f"Error in refresh_expired_urls: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

def update_unified_html_after_refresh():
    """
    Update both building_image_url_html and address_plus_code_url_html fields
    in the unified table after URL refresh.

    This function regenerates the HTML img tags for all records that have
    building_image_url or address_plus_code_url to ensure the HTML fields
    contain the latest URLs.

    Note: With the new optimized unified table, HTML fields are generated
    directly in the query, so this function may not be needed. It will
    check if the required columns exist before attempting updates.
    """
    try:
        from db.connection import execute_query, table_exists
        from config import UNIFIED_TABLE

        logger.info("Checking if HTML field update is needed after URL refresh...")

        # First, check if the unified table exists
        if not table_exists(UNIFIED_TABLE):
            logger.warning(f"Unified table {UNIFIED_TABLE} does not exist. Skipping HTML update.")
            return

        # Check if the required columns exist in the unified table
        # The new optimized query generates HTML fields directly, so these columns may not exist
        column_check_query = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{UNIFIED_TABLE}'
        AND column_name IN ('building_image_url', 'address_plus_code_url', 'building_image_url_html', 'address_plus_code_url_html')
        """

        column_result = execute_query(column_check_query, fetch=True)

        if not column_result:
            logger.info("No relevant columns found in unified table. HTML fields are likely generated directly in the optimized query.")
            return

        existing_columns = [row[0] for row in column_result]
        logger.info(f"Found columns in unified table: {existing_columns}")

        # Check if we have the source URL columns needed for the update
        has_building_url = 'building_image_url' in existing_columns
        has_address_url = 'address_plus_code_url' in existing_columns
        has_building_html = 'building_image_url_html' in existing_columns
        has_address_html = 'address_plus_code_url_html' in existing_columns

        if not (has_building_url or has_address_url):
            logger.info("No source URL columns found. HTML fields are generated directly in the optimized query.")
            return

        if not (has_building_html or has_address_html):
            logger.info("No HTML columns found to update. HTML fields are generated directly in the optimized query.")
            return

        logger.info("Updating HTML fields in unified table after URL refresh...")

        # Build dynamic UPDATE statement based on available columns
        update_parts = []
        where_conditions = []

        if has_building_url and has_building_html:
            update_parts.append("""
                building_image_url_html = CASE
                    WHEN building_image_url IS NOT NULL AND building_image_url != '' THEN
                        '<img src="' || building_image_url || '"
                        style="max-width: 100%; height: auto; border-radius: 4px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                        onerror="this.style.display=''none''" />'
                    ELSE NULL
                END
            """)
            where_conditions.append("(building_image_url IS NOT NULL AND building_image_url != '')")

        if has_address_url and has_address_html:
            update_parts.append("""
                address_plus_code_url_html = CASE
                    WHEN address_plus_code_url IS NOT NULL AND address_plus_code_url != '' THEN
                        '<img src="' || address_plus_code_url || '"
                        style="max-width: 100%; height: auto; border-radius: 4px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                        onerror="this.style.display=''none''" />'
                    ELSE NULL
                END
            """)
            where_conditions.append("(address_plus_code_url IS NOT NULL AND address_plus_code_url != '')")

        if not update_parts:
            logger.info("No columns available to update. Skipping HTML field update.")
            return

        # Construct the final UPDATE statement
        update_sql = f"""
        UPDATE "{UNIFIED_TABLE}"
        SET {', '.join(update_parts)}
        WHERE {' OR '.join(where_conditions)};
        """

        result = execute_query(update_sql)
        logger.info("Successfully updated HTML fields in unified table after URL refresh")

    except Exception as e:
        logger.error(f"Error updating unified HTML after refresh: {e}")
        logger.info("Note: With the new optimized unified table, HTML fields are generated directly in the query and may not need manual updates.")
