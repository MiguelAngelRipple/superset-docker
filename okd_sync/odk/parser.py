"""
ODK data parsing and processing module
"""
import logging
import json
import os
import sys

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
    
    # Process JSON fields
    for field in ['property_description']:
        if field in submission and isinstance(submission[field], str):
            try:
                submission[field] = json.loads(submission[field])
            except:
                # Keep as string if parsing fails
                pass
    
    return submission
