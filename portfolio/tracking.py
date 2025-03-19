"""
Portfolio tracking and analysis functions
"""
import pandas as pd
from datetime import datetime

from utils.logging_setup import logger
from database.models import get_connection
from tokendata.analysis import fetch_token_data
from trading.sell import estimate_bnb_output

def get_active_portfolio():
    """
    Get all active portfolio entries
    
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

def get_portfolio_value():
    """
    Calculate total current portfolio value
    
    Returns:
        dict: Portfolio summary with total value
    """
    try:
        # Get active portfolio entries
        portfolio_entries = get_active_portfolio()
        
        if not portfolio_entries:
            return {
                "total_investment": 0,
                "total_current_value": 0,
                "total_profit_loss": 0,
                "profit_loss_percentage": 0,
                "entries": []
            }
            
        total_investment = 0
        total_current_value = 0
        entries_with_value = []
        
        for entry in portfolio_entries:
            # Get token data to get decimals
            token_data = fetch_token_data(entry['token_address'])
            
            if not token_data:
                logger.warning(f"Failed to fetch data for {entry['token_symbol']} ({entry['token_address']})")
                continue
                
            # Calculate current value
            current_value = estimate_bnb_output(
                entry['token_address'],
                entry['amount_tokens'],
                token_data['decimals']
            )
            
            if current_value is None:
                logger.warning(f"Failed to calculate current value for {entry['token_symbol']}")
                continue
                
            # Calculate profit/loss
            profit_loss = current_value - entry['investment_amount_bnb']
            profit_loss_percentage = (profit_loss / entry['investment_amount_bnb']) * 100 if entry['investment_amount_bnb'] > 0 else 0
            
            # Add entry data
            entry_with_value = {
                "id": entry['id'],
                "token_symbol": entry['token_symbol'],
                "token_address": entry['token_address'],
                "amount_tokens": entry['amount_tokens'],
                "investment_amount_bnb": entry['investment_amount_bnb'],
                "current_value_bnb": current_value,
                "profit_loss_bnb": profit_loss,
                "profit_loss_percentage": profit_loss_percentage
            }
            
            entries_with_value.append(entry_with_value)
            
            # Update totals
            total_investment += entry['investment_amount_bnb']
            total_current_value += current_value
            
        # Calculate overall profit/loss
        total_profit_loss = total_current_value - total_investment
        profit_loss_percentage = (total_profit_loss / total_investment) * 100 if total_investment > 0 else 0
        
        return {
            "total_investment": total_investment,
            "total_current_value": total_current_value,
            "total_profit_loss": total_profit_loss,
            "profit_loss_percentage": profit_loss_percentage,
            "entries": entries_with_value
        }
        
    except Exception as e:
        logger.error(f"Error calculating portfolio value: {e}")
        return {
            "total_investment": 0,
            "total_current_value": 0,
            "total_profit_loss": 0,
            "profit_loss_percentage": 0,
            "entries": []
        }

def get_transaction_history(limit=20):
    """
    Get transaction history
    
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
        df['Time Ago'] = df['timestamp'].apply(lambda x: time_since(datetime.strptime(x, '%Y-%m-%d %H:%M:%S')))
        
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
    """
    Calculate total profits from all transactions
    
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

def get_portfolio_summary():
    """
    Get a summary of the portfolio
    
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
        df['Holding Time'] = df['purchase_time'].apply(lambda x: time_since(datetime.strptime(x, '%Y-%m-%d %H:%M:%S')))
        
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

def time_since(timestamp):
    """
    Calculate time elapsed since a timestamp
    
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

def generate_performance_report():
    """
    Generate a comprehensive performance report
    
    Returns:
        dict: Performance metrics
    """
    try:
        # Get transaction history
        conn = get_connection()
        if not conn:
            return {}
            
        # Query for all completed transactions
        query = '''
        SELECT token_symbol, transaction_type, amount_tokens, amount_bnb, 
               timestamp, profit_loss_bnb
        FROM transactions
        WHERE transaction_type IN ('buy', 'sell')
        ORDER BY timestamp
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {
                "total_trades": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "total_profit_loss": 0,
                "win_rate": 0,
                "average_profit": 0,
                "average_loss": 0,
                "largest_profit": 0,
                "largest_loss": 0
            }
            
        # Calculate metrics
        buys = df[df['transaction_type'] == 'buy']
        sells = df[df['transaction_type'] == 'sell']
        
        # Count trades
        total_buys = len(buys)
        total_sells = len(sells)
        
        # Count profitable sells
        profitable_sells = sells[sells['profit_loss_bnb'] > 0]
        losing_sells = sells[sells['profit_loss_bnb'] <= 0]
        
        win_rate = (len(profitable_sells) / total_sells) * 100 if total_sells > 0 else 0
        
        # Calculate profit/loss metrics
        total_profit_loss = sells['profit_loss_bnb'].sum()
        average_profit = profitable_sells['profit_loss_bnb'].mean() if not profitable_sells.empty else 0
        average_loss = losing_sells['profit_loss_bnb'].mean() if not losing_sells.empty else 0
        largest_profit = profitable_sells['profit_loss_bnb'].max() if not profitable_sells.empty else 0
        largest_loss = losing_sells['profit_loss_bnb'].min() if not losing_sells.empty else 0
        
        return {
            "total_trades": total_buys,
            "completed_trades": total_sells,
            "pending_trades": total_buys - total_sells,
            "successful_trades": len(profitable_sells),
            "failed_trades": len(losing_sells),
            "total_profit_loss": total_profit_loss,
            "win_rate": win_rate,
            "average_profit": average_profit,
            "average_loss": average_loss,
            "largest_profit": largest_profit,
            "largest_loss": largest_loss
        }
        
    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        return {}