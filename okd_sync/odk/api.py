"""
ODK Central API interaction module
"""
import logging
import requests
from datetime import datetime
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ODATA_USER, ODATA_PASS, SUBMISSIONS_URL, PERSON_DETAILS_URL

logger = logging.getLogger(__name__)

def fetch_odata(url, last_sync=None, filter_field='__system/submissionDate'):
    """
    Fetch data from ODK Central OData API
    
    Args:
        url: OData URL to fetch from
        last_sync: Timestamp of last synchronization
        filter_field: Field to filter by for incremental sync (None for no filtering)
        
    Returns:
        list: List of records from the API
    """
    auth = (ODATA_USER, ODATA_PASS)
    params = {
        "$format": "json",
        "$count": "true"
    }
    
    # Add filter for incremental sync if last_sync is provided and filter_field is specified
    if last_sync and filter_field:
        # Format timestamp for OData filter
        ts_str = last_sync.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        params["$filter"] = f"{filter_field} gt {ts_str}"
    
    try:
        response = requests.get(url, auth=auth, params=params)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('value', [])
        
        # Process timestamps
        for record in records:
            for field in ['SubmittedDate', 'SubmissionDate']:
                if field in record and record[field]:
                    try:
                        record[field] = datetime.fromisoformat(record[field].replace('Z', '+00:00'))
                    except Exception as e:
                        logger.warning(f"Error parsing timestamp {record[field]}: {e}")
        
        return records
    except Exception as e:
        logger.error(f"Error fetching data from {url}: {e}")
        return []

def fetch_main_submissions(last_sync):
    """
    Fetch main form submissions from ODK Central
    
    Args:
        last_sync: Timestamp of last synchronization
        
    Returns:
        list: List of submission records
    """
    return fetch_odata(SUBMISSIONS_URL, last_sync, '__system/submissionDate')

def fetch_person_details(last_sync):
    """
    Fetch person details records from ODK Central
    
    Args:
        last_sync: Timestamp of last synchronization (not used for filtering)
        
    Returns:
        list: List of person details records or empty list if the table doesn't exist
    """
    # Person details are child records that don't support OData filtering
    # We'll fetch all person_details and filter them locally based on main submissions
    try:
        # Fetch all person_details without filter
        return fetch_odata(PERSON_DETAILS_URL, None, None)
    except requests.exceptions.HTTPError as e:
        # If we get a 404, it means the person_details table doesn't exist in the form
        if e.response.status_code == 404:
            logger.warning(f"Person details table not found in ODK Central. This is normal if the form doesn't have a person_details repeat group.")
            return []
        # For other HTTP errors, re-raise the exception
        raise
