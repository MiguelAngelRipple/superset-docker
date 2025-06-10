"""
Database connection module
"""
import logging
import psycopg2
from psycopg2.extras import execute_values
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS

logger = logging.getLogger(__name__)

def get_connection():
    """
    Get a connection to the PostgreSQL database
    
    Returns:
        Connection object
    """
    try:
        conn = psycopg2.connect(
            f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def execute_query(query, params=None, fetch=False, many=False):
    """
    Execute a SQL query on the database
    
    Args:
        query: SQL query to execute
        params: Parameters for the query
        fetch: Whether to fetch results
        many: Whether to execute many statements
        
    Returns:
        Query results if fetch=True, otherwise None
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        if many and params:
            execute_values(cur, query, params)
        elif params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            results = cur.fetchall()
        else:
            results = None
        
        conn.commit()
        return results
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error executing query: {e}")
        raise
    finally:
        if conn:
            conn.close()

def table_exists(table_name):
    """
    Check if a table exists in the database
    
    Args:
        table_name: Name of the table to check
        
    Returns:
        bool: True if the table exists, False otherwise
    """
    # First try with the exact name
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        )
    """
    result = execute_query(query, (table_name,), fetch=True)
    if result and result[0][0]:
        return True
        
    # Then try with lowercase
    result = execute_query(query, (table_name.lower(),), fetch=True)
    if result and result[0][0]:
        return True
        
    # Finally try with uppercase
    result = execute_query(query, (table_name.upper(),), fetch=True)
    return result[0][0] if result else False

def column_exists(table_name, column_name):
    """
    Check if a column exists in a table
    
    Args:
        table_name: Name of the table
        column_name: Name of the column
        
    Returns:
        bool: True if the column exists, False otherwise
    """
    # In PostgreSQL, when columns are created with double quotes, names preserve their capitalization
    # When created without quotes, they are converted to lowercase
    # Therefore, we need to check both possibilities
    
    # First check with the exact name
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        )
    """
    result = execute_query(query, (table_name.lower(), column_name), fetch=True)
    if result and result[0][0]:
        return True
        
    # If it doesn't exist, check with the lowercase name
    result = execute_query(query, (table_name.lower(), column_name.lower()), fetch=True)
    if result and result[0][0]:
        return True
        
    # Also check with the uppercase name (just in case)
    result = execute_query(query, (table_name.lower(), column_name.upper()), fetch=True)
    return result[0][0] if result else False
