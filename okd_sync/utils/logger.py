"""
Logging configuration module
"""
import logging

def get_logger(name):
    """
    Get a logger with the specified name
    
    Args:
        name: Name of the logger
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
