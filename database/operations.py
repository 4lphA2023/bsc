from utils.logging_setup import logger
from database.models import get_connection

def record_failed_transaction(token_address, token_symbol, transaction_type, 
                             amount, tx_hash=None, error_reason=None):
    """
    Record a failed transaction in the database
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        transaction_type: Transaction type (buy, sell, approve)
        amount: Amount of tokens or BNB
        tx_hash: Transaction hash
        error_reason: Error reason
        
    Returns:
        bool: True if recorded successfully, False otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS failed_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT NOT NULL,
            token_symbol TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL,
            tx_hash TEXT,
            error_reason TEXT,
            timestamp TEXT NOT NULL
        )
        ''')
        
        # Insert failed transaction
        cursor.execute('''
        INSERT INTO failed_transactions 
        (token_address, token_symbol, transaction_type, amount, tx_hash, error_reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (token_address, token_symbol, transaction_type, amount, tx_hash, error_reason))
        
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error recording failed transaction: {e}")
        return False

# Blacklist operations
def is_token_blacklisted(token_address):
    """Check if a token is blacklisted
    
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
    """Add a token to the blacklist
    
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

# Portfolio operations
def add_to_portfolio(token_address, token_symbol, amount_tokens, purchase_price_bnb, investment_amount_bnb, take_profit, stop_loss):
    """Add a token to the portfolio
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        amount_tokens: Amount of tokens purchased
        purchase_price_bnb: Price per token in BNB
        investment_amount_bnb: Total investment in BNB
        take_profit: Take profit percentage
        stop_loss: Stop loss percentage
        
    Returns:
        int: Portfolio entry ID if successful, None otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO portfolio
        (token_address, token_symbol, amount_tokens, purchase_price_bnb, investment_amount_bnb, take_profit_target, stop_loss_target)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (token_address, token_symbol, amount_tokens, purchase_price_bnb, investment_amount_bnb, take_profit, stop_loss))
        
        portfolio_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Added {token_symbol} to portfolio with ID {portfolio_id}")
        return portfolio_id
    except Exception as e:
        logger.error(f"Error adding to portfolio: {e}")
        return None

def update_portfolio_status(portfolio_id, status):
    """Update portfolio entry status
    
    Args:
        portfolio_id: Portfolio entry ID
        status: New status ('active', 'sold', 'loss', etc.)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE portfolio
        SET status = ?
        WHERE id = ?
        ''', (status, portfolio_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated portfolio entry {portfolio_id} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating portfolio status: {e}")
        return False

def get_active_portfolio():
    """Get all active portfolio entries
    
    Returns:
        list: List of active portfolio entries
    """
    try:
        conn = get_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, token_address, token_symbol, amount_tokens, purchase_price_bnb,
               investment_amount_bnb, purchase_time, take_profit_target, stop_loss_target
        FROM portfolio
        WHERE status = 'active'
        ''')
        
        columns = [column[0] for column in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error getting active portfolio: {e}")
        return []

# Transaction operations
def record_transaction(token_address, token_symbol, transaction_type, amount_tokens, amount_bnb, transaction_hash, profit_loss_bnb=None):
    """Record a transaction in the database
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        transaction_type: Type of transaction ('buy', 'sell', 'test_buy', 'test_sell')
        amount_tokens: Amount of tokens involved
        amount_bnb: Amount of BNB involved
        transaction_hash: Transaction hash
        profit_loss_bnb: Profit/loss in BNB (for sell transactions)
        
    Returns:
        int: Transaction ID if successful, None otherwise
    """
    try:
        conn = get_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO transactions
        (token_address, token_symbol, transaction_type, amount_tokens, amount_bnb, transaction_hash, profit_loss_bnb)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (token_address, token_symbol, transaction_type, amount_tokens, amount_bnb, transaction_hash, profit_loss_bnb))
        
        transaction_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded {transaction_type} transaction for {token_symbol} with ID {transaction_id}")
        return transaction_id
    except Exception as e:
        logger.error(f"Error recording transaction: {e}")
        return None