import time
import pandas as pd
from datetime import datetime

from utils.logging_setup import logger
from database.models import get_connection

def format_amount(amount, decimals=18):
    """Format a token amount with appropriate decimals
    
    Args:
        amount: Amount to format
        decimals: Number of decimals
        
    Returns:
        str: Formatted amount
    """
    return format(amount, f'.{decimals}f').rstrip('0').rstrip('.')

def time_since(timestamp):
    """Calculate time elapsed since a timestamp
    
    Args:
        timestamp: Timestamp to compare against
        
    Returns:
        str: Formatted time difference
    """
    if isinstance(timestamp, str):
        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    else:
        dt = timestamp
        
    delta = datetime.now() - dt
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def retry_function(func, max_retries=3, retry_delay=2, *args, **kwargs):
    """Retry a function with exponential backoff
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function or None if all retries fail
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                backoff_time = retry_delay * (attempt + 1)
                logger.warning(f"Function {func.__name__} failed (attempt {attempt+1}/{max_retries}): {e}")
                logger.info(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
            else:
                logger.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                return None

def get_portfolio_summary():
    """Get a summary of the portfolio
    
    Returns:
        pandas.DataFrame: Portfolio summary
    """
    try:
        conn = get_connection()
        if not conn:
            return None
            
        # Query for active portfolio entries
        query = '''
        SELECT token_symbol, token_address, amount_tokens, investment_amount_bnb, 
               purchase_time, purchase_price_bnb, status
        FROM portfolio
        ORDER BY purchase_time DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return pd.DataFrame(columns=['Token', 'Amount', 'Investment (BNB)', 'Status', 'Holding Time'])
            
        # Add holding time
        df['Holding Time'] = df['purchase_time'].apply(time_since)
        
        # Rename columns for display
        df = df.rename(columns={
            'token_symbol': 'Token',
            'amount_tokens': 'Amount',
            'investment_amount_bnb': 'Investment (BNB)',
            'status': 'Status'
        })
        
        # Select only relevant columns
        summary = df[['Token', 'Amount', 'Investment (BNB)', 'Status', 'Holding Time']]
        
        conn.close()
        return summary
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        return None

def get_transaction_history(limit=20):
    """Get transaction history
    
    Args:
        limit: Maximum number of transactions to return
        
    Returns:
        pandas.DataFrame: Transaction history
    """
    try:
        conn = get_connection()
        if not conn:
            return None
            
        # Query for transactions
        query = f'''
        SELECT token_symbol, transaction_type, amount_tokens, amount_bnb, 
               timestamp, profit_loss_bnb
        FROM transactions
        ORDER BY timestamp DESC
        LIMIT {limit}
        '''
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return pd.DataFrame(columns=['Token', 'Type', 'Amount', 'BNB', 'Time', 'P/L (BNB)'])
            
        # Add time ago
        df['Time Ago'] = df['timestamp'].apply(time_since)
        
        # Rename columns for display
        df = df.rename(columns={
            'token_symbol': 'Token',
            'transaction_type': 'Type',
            'amount_tokens': 'Amount',
            'amount_bnb': 'BNB',
            'profit_loss_bnb': 'P/L (BNB)'
        })
        
        # Select only relevant columns
        history = df[['Token', 'Type', 'Amount', 'BNB', 'Time Ago', 'P/L (BNB)']]
        
        conn.close()
        return history
    except Exception as e:
        logger.error(f"Error getting transaction history: {e}")
        return None

def calculate_total_profits():
    """Calculate total profits from all transactions
    
    Returns:
        float: Total profits in BNB
    """
    try:
        conn = get_connection()
        if not conn:
            return 0
            
        cursor = conn.cursor()
        
        # Get total profits
        cursor.execute('''
        SELECT SUM(profit_loss_bnb) 
        FROM transactions 
        WHERE transaction_type = 'sell' AND profit_loss_bnb IS NOT NULL
        ''')
        
        result = cursor.fetchone()
        total_profit = result[0] if result[0] else 0
        
        conn.close()
        return total_profit
    except Exception as e:
        logger.error(f"Error calculating total profits: {e}")
        return 0

def print_banner():
    """Print a banner for the application"""
    banner = """
    ██████╗ ███████╗ ██████╗    ████████╗ ██████╗ ██╗  ██╗███████╗███╗   ██╗
    ██╔══██╗██╔════╝██╔════╝    ╚══██╔══╝██╔═══██╗██║ ██╔╝██╔════╝████╗  ██║
    ██████╔╝███████╗██║            ██║   ██║   ██║█████╔╝ █████╗  ██╔██╗ ██║
    ██╔══██╗╚════██║██║            ██║   ██║   ██║██╔═██╗ ██╔══╝  ██║╚██╗██║
    ██████╔╝███████║╚██████╗       ██║   ╚██████╔╝██║  ██╗███████╗██║ ╚████║
    ╚═════╝ ╚══════╝ ╚═════╝       ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝
                      ███████╗███╗   ██╗██╗██████╗ ███████╗██████╗ 
                      ██╔════╝████╗  ██║██║██╔══██╗██╔════╝██╔══██╗
                      ███████╗██╔██╗ ██║██║██████╔╝█████╗  ██████╔╝
                      ╚════██║██║╚██╗██║██║██╔═══╝ ██╔══╝  ██╔══██╗
                      ███████║██║ ╚████║██║██║     ███████╗██║  ██║
                      ╚══════╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝
    """
    print(banner)