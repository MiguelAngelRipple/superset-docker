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
    ODK_BASE_URL
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
            s3_file_name = f"odk_images/{datetime.now().strftime('%Y-%m')}/{submission_id}-{attachment_url}"
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
            s3_file_name = f"odk_images/{datetime.now().strftime('%Y-%m')}/{submission_id}-{os.path.basename(attachment_url)}"
            s3_url = upload_to_s3(temp_file.name, s3_file_name)
            
            # Clean up the temporary file
            os.unlink(temp_file.name)
            
            return s3_url
    except Exception as e:
        logger.error(f"Error processing attachment: {e}")
        return None

def generate_image_html(image_url, width=300, height=200, is_placeholder=False):
    """
    Generate HTML to display an image in Superset
    
    Args:
        image_url: URL of the image (signed URL)
        width: Width of the image in pixels
        height: Height of the image in pixels
        is_placeholder: Whether this is a placeholder image
        
    Returns:
        str: HTML string for displaying the image
    """
    if not image_url:
        return ""
    
    placeholder_class = " placeholder-image" if is_placeholder else ""
    
    # Escape any quotes in the URL to prevent HTML injection
    safe_url = image_url.replace('"', '&quot;')
    
    # Create responsive HTML with the signed URL
    html = f'''
    <div class="image-container{placeholder_class}">
        <a href="{safe_url}" target="_blank" rel="noopener noreferrer">
            <img src="{safe_url}" width="{width}" height="{height}" 
                 style="object-fit: cover; border-radius: 4px; max-width: 100%;" 
                 loading="lazy" alt="Building Image" />
        </a>
    </div>
    '''
    
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
            # Process building_image from property_description
            building_image = extract_building_image(submission)
            
            if building_image:
                # Upload to S3 and get a signed URL
                s3_url = download_and_upload_attachment(submission_id, 'building_image', building_image)
                if s3_url:
                    # Store both the signed URL and the HTML in the results dictionary
                    with results_lock:
                        results_dict[submission_id] = {
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
                    s3_url = upload_to_s3(placeholder_path, f"placeholders/{submission_id}.png")
                    if s3_url:
                        # Store both the signed URL and the HTML in the results dictionary
                        with results_lock:
                            results_dict[submission_id] = {
                                'url': s3_url,
                                'html': generate_image_html(s3_url, is_placeholder=True)
                            }
                        logger.info(f"Uploaded placeholder image to S3 with signed URL: {s3_url}")
            
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
    image_count = 0
    for submission in submissions:
        submission_id = submission.get('UUID') or submission.get('__id')
        if submission_id in results_dict:
            result = results_dict[submission_id]
            # Set the URL for the image
            submission['building_image_url'] = result['url']
            # No agregamos building_image_url_html aquí ya que no está en el modelo MainSubmission
            # Este campo se genera en la vista unificada
            image_count += 1
    
    logger.info(f"Attachment process completed: {processed_count} submissions processed, {image_count} images uploaded")
    return submissions
