"""
Helper functions for ODK Sync
"""
import os
import json
from datetime import datetime
import logging
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LAST_SYNC_FILE

logger = logging.getLogger(__name__)

def get_last_sync_time():
    """
    Get the timestamp of the last successful synchronization
    
    Returns:
        datetime or None: The timestamp of the last synchronization, or None if never synchronized
    """
    if not os.path.exists(LAST_SYNC_FILE):
        return None
    
    try:
        with open(LAST_SYNC_FILE, 'r') as f:
            ts_str = f.read().strip()
            if ts_str:
                return datetime.fromisoformat(ts_str)
    except Exception as e:
        logger.error(f"Error reading last sync time: {e}")
    
    return None

def set_last_sync_time(ts):
    """
    Set the timestamp of the last successful synchronization
    
    Args:
        ts: Timestamp to save
    """
    try:
        with open(LAST_SYNC_FILE, 'w') as f:
            f.write(ts.isoformat())
    except Exception as e:
        logger.error(f"Error writing last sync time: {e}")

def parse_json_field(field_value):
    """
    Parse a JSON string field into a Python object
    
    Args:
        field_value: String value to parse
        
    Returns:
        dict or original value: Parsed JSON object or original value if parsing fails
    """
    if not field_value or not isinstance(field_value, str):
        return field_value
    
    try:
        return json.loads(field_value)
    except:
        return field_value
