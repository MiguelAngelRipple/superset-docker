"""
ODK data parsing and processing module
"""
import logging
import json
import os
import sys
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import parse_json_field

logger = logging.getLogger(__name__)

def extract_building_image(submission):
    """
    Extract building image URL from a submission
    
    Args:
        submission: Submission record
        
    Returns:
        str or None: URL of the building image, or None if not found
    """
    if not submission:
        return None
    
    # Check property_description field
    if 'property_description' in submission and submission['property_description']:
        prop_desc = submission['property_description']
        
        # Parse JSON string if needed
        if isinstance(prop_desc, str):
            try:
                prop_desc = json.loads(prop_desc)
            except:
                logger.warning(f"Could not parse property_description as JSON for submission {submission.get('UUID')}")
                prop_desc = {}
        
        # Extract building_image
        if isinstance(prop_desc, dict) and 'building_image' in prop_desc:
            building_image = prop_desc.get('building_image')
            if building_image and isinstance(building_image, str):
                return building_image
    
    # Check for building image in top-level fields
    for field, value in submission.items():
        if 'building' in field.lower() and 'image' in field.lower() and value and isinstance(value, str):
            return value
    
    return None

def process_submission(submission):
    """
    Process a submission record to prepare it for database storage
    
    Args:
        submission: Raw submission record from ODK
        
    Returns:
        dict: Processed submission record
    """
    if not submission:
        return submission
    
    # Ensure UUID field exists
    if '__id' in submission and not submission.get('UUID'):
        submission['UUID'] = submission['__id']
    
    # Extract submissionDate from __system and add as SubmittedDate for tracking
    if '__system' in submission and submission['__system']:
        system_data = submission['__system']
        
        # Parse JSON string if needed
        if isinstance(system_data, str):
            try:
                system_data = json.loads(system_data)
            except:
                logger.warning(f"Could not parse __system as JSON for submission {submission.get('UUID')}")
                system_data = {}
        
        # Extract submissionDate and convert to datetime
        if isinstance(system_data, dict) and 'submissionDate' in system_data:
            submission_date_str = system_data.get('submissionDate')
            if submission_date_str:
                try:
                    # Parse the ISO timestamp and convert to datetime
                    # Remove 'Z' and replace with '+00:00' for proper parsing
                    submission_date_str = submission_date_str.replace('Z', '+00:00')
                    submission['SubmittedDate'] = datetime.fromisoformat(submission_date_str)
                    logger.debug(f"Extracted SubmittedDate: {submission['SubmittedDate']} for submission {submission.get('UUID')}")
                except Exception as e:
                    logger.warning(f"Could not parse submissionDate '{submission_date_str}' for submission {submission.get('UUID')}: {e}")
    
    # Process JSON fields
    for field in ['property_description']:
        if field in submission and isinstance(submission[field], str):
            try:
                submission[field] = json.loads(submission[field])
            except:
                # Keep as string if parsing fails
                pass
    
    return submission
