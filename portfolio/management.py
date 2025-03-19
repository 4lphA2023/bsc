import time
import threading
from datetime import datetime, timedelta

from utils.logging_setup import logger
from utils.connections import web3, get_web3_connection
from database.operations import get_active_portfolio
from tokendata.analysis import fetch_token_data
from trading.sell import estimate_bnb_output, execute_sell
import config

def calculate_current_value(token_address, token_amount, token_decimals):
    """Calculate current value of tokens in BNB
    
    Args:
        token_address: Token address
        token_amount: Amount of tokens
        token_decimals: Token decimals
        
    Returns:
        float: Current value in BNB or None if calculation fails
    """
    return estimate_bnb_output(token_address, token_amount, token_decimals)

def should_take_profit(current_value, investment_amount, take_profit_target):
    """Check if we should take profit
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        take_profit_target: Take profit target percentage
        
    Returns:
        bool: True if should take profit, False otherwise
    """
    if current_value is None:
        return False
        
    profit_percentage = (current_value - investment_amount) / investment_amount * 100
    
    if profit_percentage >= take_profit_target:
        logger.info(f"Take profit triggered: {profit_percentage:.2f}% profit (target: {take_profit_target}%)")
        return True
        
    return False

def should_stop_loss(current_value, investment_amount, stop_loss_target):
    """Check if we should stop loss
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        stop_loss_target: Stop loss target percentage
        
    Returns:
        bool: True if should stop loss, False otherwise
    """
    if current_value is None:
        return False
        
    loss_percentage = (investment_amount - current_value) / investment_amount * 100
    
    if loss_percentage >= stop_loss_target:
        logger.info(f"Stop loss triggered: {loss_percentage:.2f}% loss (target: {stop_loss_target}%)")
        return True
        
    return False

def should_sell_by_time(purchase_time, max_holding_time):
    """Check if we should sell based on holding time
    
    Args:
        purchase_time: Purchase time as string or datetime
        max_holding_time: Maximum holding time in hours
        
    Returns:
        bool: True if should sell, False otherwise
    """
    if isinstance(purchase_time, str):
        purchase_datetime = datetime.strptime(purchase_time, '%Y-%m-%d %H:%M:%S')
    else:
        purchase_datetime = purchase_time
        
    time_held = datetime.now() - purchase_datetime
    max_holding_timedelta = timedelta(hours=max_holding_time)
    
    if time_held >= max_holding_timedelta:
        hours_held = time_held.total_seconds() / 3600
        logger.info(f"Time-based sell triggered: Held for {hours_held:.2f} hours (max: {max_holding_time} hours)")
        return True
        
    return False

def monitor_portfolio():
    """Monitor portfolio and take profit/stop loss as needed"""
    try:
        # Check web3 connection
        if web3 is None or not web3.is_connected():
            logger.warning("Web3 connection lost during portfolio monitoring, reconnecting...")
            get_web3_connection()
            
        # Get active portfolio entries
        portfolio_entries = get_active_portfolio()
        
        if not portfolio_entries:
            logger.info("No active portfolio entries to monitor")
            return
            
        logger.info(f"Monitoring {len(portfolio_entries)} active portfolio entries")
        
        for entry in portfolio_entries:
            try:
                # Fetch current token data
                token_data = fetch_token_data(entry['token_address'])
                
                if not token_data:
                    logger.warning(f"Failed to fetch data for {entry['token_symbol']} ({entry['token_address']})")
                    continue
                    
                # Calculate current value
                current_value = calculate_current_value(
                    entry['token_address'],
                    entry['amount_tokens'],
                    token_data['decimals']
                )
                
                if current_value is None:
                    logger.warning(f"Failed to calculate current value for {entry['token_symbol']}")
                    continue
                    
                logger.info(f"Portfolio entry {entry['id']}: {entry['token_symbol']} - Current value: {current_value} BNB (invested: {entry['investment_amount_bnb']} BNB)")
                
                # Check take profit
                if should_take_profit(current_value, entry['investment_amount_bnb'], entry['take_profit_target']):
                    logger.info(f"Taking profit on {entry['token_symbol']}")
                    
                    # Execute sell
                    sell_result = execute_sell(
                        entry['token_address'],
                        entry['token_symbol'],
                        token_data['decimals'],
                        amount_tokens=entry['amount_tokens'],
                        portfolio_id=entry['id']
                    )
                    
                    if sell_result and sell_result['status'] == 'success':
                        logger.info(f"Successfully took profit on {entry['token_symbol']}: {sell_result['bnb_received']} BNB (profit: {sell_result['bnb_received'] - entry['investment_amount_bnb']} BNB)")
                    else:
                        logger.error(f"Failed to take profit on {entry['token_symbol']}")
                        
                # Check stop loss
                elif should_stop_loss(current_value, entry['investment_amount_bnb'], entry['stop_loss_target']):
                    logger.info(f"Stopping loss on {entry['token_symbol']}")
                    
                    # Execute sell
                    sell_result = execute_sell(
                        entry['token_address'],
                        entry['token_symbol'],
                        token_data['decimals'],
                        amount_tokens=entry['amount_tokens'],
                        portfolio_id=entry['id']
                    )
                    
                    if sell_result and sell_result['status'] == 'success':
                        logger.info(f"Successfully stopped loss on {entry['token_symbol']}: {sell_result['bnb_received']} BNB (loss: {entry['investment_amount_bnb'] - sell_result['bnb_received']} BNB)")
                    else:
                        logger.error(f"Failed to stop loss on {entry['token_symbol']}")
                        
                # Check time-based selling
                elif should_sell_by_time(entry['purchase_time'], config.MAX_HOLDING_TIME):
                    logger.info(f"Selling {entry['token_symbol']} based on maximum holding time")
                    
                    # Execute sell
                    sell_result = execute_sell(
                        entry['token_address'],
                        entry['token_symbol'],
                        token_data['decimals'],
                        amount_tokens=entry['amount_tokens'],
                        portfolio_id=entry['id']
                    )
                    
                    if sell_result and sell_result['status'] == 'success':
                        profit_loss = sell_result['bnb_received'] - entry['investment_amount_bnb']
                        logger.info(f"Successfully sold {entry['token_symbol']} based on time: {sell_result['bnb_received']} BNB (P/L: {profit_loss} BNB)")
                    else:
                        logger.error(f"Failed to sell {entry['token_symbol']} based on time")
                
            except Exception as e:
                logger.error(f"Error monitoring portfolio entry {entry['id']} ({entry['token_symbol']}): {e}")
                
    except Exception as e:
        logger.error(f"Error in portfolio monitoring: {e}")

def start_portfolio_monitoring():
    """Start portfolio monitoring in a separate thread"""
    def monitoring_thread():
        while True:
            try:
                monitor_portfolio()
            except Exception as e:
                logger.error(f"Error in monitoring thread: {e}")
                
            # Sleep for monitoring interval
            time.sleep(config.MONITORING_INTERVAL)
    
    # Start monitoring thread
    thread = threading.Thread(target=monitoring_thread)
    thread.daemon = True
    thread.start()
    
    logger.info(f"Portfolio monitoring started (interval: {config.MONITORING_INTERVAL} seconds)")
    return thread