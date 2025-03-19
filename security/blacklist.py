"""
Blacklist management functions for token security
"""
from utils.logging_setup import logger
from database.models import get_connection

def check_blacklisted_patterns(token_name, token_symbol, patterns_list):
    """
    Check if token name or symbol contains blacklisted patterns
    
    Args:
        token_name: Token name to check
        token_symbol: Token symbol to check
        patterns_list: List of blacklisted patterns
        
    Returns:
        tuple: (is_blacklisted, matching_pattern)
    """
    name_lower = token_name.lower()
    symbol_lower = token_symbol.lower()
    
    for pattern in patterns_list:
        if pattern in name_lower or pattern in symbol_lower:
            return True, pattern
            
    return False, None

def get_blacklisted_tokens():
    """
    Get all blacklisted tokens from the database
    
    Returns:
        list: Blacklisted tokens with reason
    """
    try:
        conn = get_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT token_address, token_symbol, reason, blacklist_time 
        FROM blacklisted_tokens 
        ORDER BY blacklist_time DESC
        """)
        
        # Convert to list of dictionaries
        columns = [column[0] for column in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error getting blacklisted tokens: {e}")
        return []

def is_token_blacklisted(token_address):
    """
    Check if a token is blacklisted
    
    Args:
        token_address: Token address to check
        
    Returns:
        bool: True if token is blacklisted, False otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if token is in blacklist
        cursor.execute("SELECT token_address FROM blacklisted_tokens WHERE token_address = ?", (token_address,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Error checking blacklist: {e}")
        return False  # Default to not blacklisted in case of database error

def add_to_blacklist(token_address, token_symbol, reason):
    """
    Add a token to the blacklist
    
    Args:
        token_address: Token address to blacklist
        token_symbol: Token symbol
        reason: Reason for blacklisting
        
    Returns:
        bool: True if operation was successful, False otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Add token to blacklist
        cursor.execute('''
        INSERT OR REPLACE INTO blacklisted_tokens 
        (token_address, token_symbol, reason) 
        VALUES (?, ?, ?)
        ''', (token_address, token_symbol, reason))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"Added {token_symbol} ({token_address}) to blacklist. Reason: {reason}")
        return True
    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")
        return False

def remove_from_blacklist(token_address):
    """
    Remove a token from the blacklist
    
    Args:
        token_address: Token address to remove from blacklist
        
    Returns:
        bool: True if operation was successful, False otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Remove token from blacklist
        cursor.execute("DELETE FROM blacklisted_tokens WHERE token_address = ?", (token_address,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Removed {token_address} from blacklist")
        return True
    except Exception as e:
        logger.error(f"Error removing from blacklist: {e}")
        return False