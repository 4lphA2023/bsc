"""
Profit management and exit strategy functions
"""
from datetime import datetime, timedelta

from utils.logging_setup import logger
from trading.sell import execute_sell, estimate_bnb_output
import config

def calculate_optimal_slippage(token_address, token_symbol, base_slippage=config.SLIPPAGE):
    """
    Calculate optimal slippage based on token characteristics
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        base_slippage: Base slippage percentage
        
    Returns:
        float: Optimal slippage percentage
    """
    try:
        # Check token history for sell failures
        from database.operations import get_token_transaction_history
        
        history = get_token_transaction_history(token_address)
        
        if not history:
            return base_slippage
            
        # Count failed sells
        failed_sells = sum(1 for tx in history 
                         if tx['transaction_type'] == 'sell' and tx['status'] == 'failed')
        
        # Increase slippage based on failure rate
        if failed_sells > 5:
            # High failure rate, use more aggressive slippage
            return min(base_slippage * 2, 49.9)  # Max 49.9% to avoid frontend limits
        elif failed_sells > 2:
            # Medium failure rate
            return min(base_slippage * 1.5, 49.9)
            
        # Check if token has transfer tax
        has_tax = check_for_transfer_tax(token_address, token_symbol)
        if has_tax:
            # Add extra slippage for tokens with tax
            return min(base_slippage + 10, 49.9)
            
        return base_slippage
        
    except Exception as e:
        logger.error(f"Error calculating optimal slippage: {e}")
        return base_slippage

def calculate_profit_percentage(current_value, investment_amount):
    """
    Calculate profit percentage
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        
    Returns:
        float: Profit percentage (negative for loss)
    """
    if investment_amount == 0:
        return 0
        
    return ((current_value - investment_amount) / investment_amount) * 100

def calculate_loss_percentage(current_value, investment_amount):
    """
    Calculate loss percentage as a positive number
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        
    Returns:
        float: Loss percentage as a positive number
    """
    if investment_amount == 0:
        return 0
        
    return max(0, ((investment_amount - current_value) / investment_amount) * 100)

def should_take_profit(current_value, investment_amount, take_profit_target):
    """
    Check if we should take profit
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        take_profit_target: Take profit target percentage
        
    Returns:
        bool: True if should take profit, False otherwise
    """
    if current_value is None:
        return False
        
    profit_percentage = calculate_profit_percentage(current_value, investment_amount)
    
    if profit_percentage >= take_profit_target:
        logger.info(f"Take profit triggered: {profit_percentage:.2f}% profit (target: {take_profit_target}%)")
        return True
        
    return False

def should_stop_loss(current_value, investment_amount, stop_loss_target):
    """
    Check if we should stop loss
    
    Args:
        current_value: Current value in BNB
        investment_amount: Original investment in BNB
        stop_loss_target: Stop loss target percentage
        
    Returns:
        bool: True if should stop loss, False otherwise
    """
    if current_value is None:
        return False
        
    loss_percentage = calculate_loss_percentage(current_value, investment_amount)
    
    if loss_percentage >= stop_loss_target:
        logger.info(f"Stop loss triggered: {loss_percentage:.2f}% loss (target: {stop_loss_target}%)")
        return True
        
    return False

def should_sell_by_time(purchase_time, max_holding_time):
    """
    Check if we should sell based on holding time
    
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

def implement_trailing_stop_loss(token_address, token_symbol, token_decimals, amount_tokens, 
                                highest_value, current_value, trailing_percentage):
    """
    Implement trailing stop loss strategy
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        token_decimals: Token decimals
        amount_tokens: Amount of tokens
        highest_value: Highest recorded value in BNB
        current_value: Current value in BNB
        trailing_percentage: Trailing stop loss percentage
        
    Returns:
        tuple: (should_sell, highest_value)
    """
    if highest_value is None or current_value is None:
        return False, highest_value
        
    # Update highest value if current value is higher
    if current_value > highest_value:
        highest_value = current_value
        logger.info(f"New high for {token_symbol}: {highest_value} BNB")
        return False, highest_value
        
    # Calculate decline from highest value as a percentage
    decline_percentage = ((highest_value - current_value) / highest_value) * 100
    
    if decline_percentage >= trailing_percentage:
        logger.info(f"Trailing stop loss triggered for {token_symbol}: Declined {decline_percentage:.2f}% from high of {highest_value} BNB")
        return True, highest_value
        
    return False, highest_value

def execute_take_profit_strategy(token_address, token_symbol, token_decimals, 
                               amount_tokens, investment_amount, portfolio_id):
    """
    Execute take profit strategy with tiered selling
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        token_decimals: Token decimals
        amount_tokens: Amount of tokens
        investment_amount: Original investment in BNB
        portfolio_id: Portfolio entry ID
        
    Returns:
        dict: Result of the operation
    """
    try:
        # Current value of total position
        current_value = estimate_bnb_output(token_address, amount_tokens, token_decimals)
        
        if current_value is None:
            logger.warning(f"Failed to estimate current value for {token_symbol}")
            return {"status": "failed", "reason": "Failed to estimate current value"}
            
        profit_percentage = calculate_profit_percentage(current_value, investment_amount)
        
        # Define tiered profit-taking strategy
        # This is a simple example - modify based on your strategy
        if profit_percentage >= 100:  # 100% profit or more
            # Sell 75% of tokens
            sell_amount = amount_tokens * 0.75
            logger.info(f"Taking partial profit (75%) for {token_symbol} at {profit_percentage:.2f}% profit")
        elif profit_percentage >= 50:  # 50-100% profit
            # Sell 50% of tokens
            sell_amount = amount_tokens * 0.5
            logger.info(f"Taking partial profit (50%) for {token_symbol} at {profit_percentage:.2f}% profit")
        elif profit_percentage >= config.TAKE_PROFIT_PERCENTAGE:  # Regular take profit
            # Sell 25% of tokens
            sell_amount = amount_tokens * 0.25
            logger.info(f"Taking partial profit (25%) for {token_symbol} at {profit_percentage:.2f}% profit")
        else:
            # No profit taking yet
            return {"status": "skipped", "reason": "Profit threshold not met"}
            
        # Execute sell
        sell_result = execute_sell(
            token_address,
            token_symbol,
            token_decimals,
            amount_tokens=sell_amount,
            portfolio_id=portfolio_id
        )
        
        if sell_result and sell_result['status'] == 'success':
            logger.info(f"Partial profit taking successful for {token_symbol}: {sell_result['bnb_received']} BNB")
            return {
                "status": "success",
                "profit_percentage": profit_percentage,
                "tokens_sold": sell_amount,
                "bnb_received": sell_result['bnb_received']
            }
        else:
            logger.error(f"Failed to take profit for {token_symbol}")
            return {"status": "failed", "reason": "Sell execution failed"}
            
    except Exception as e:
        logger.error(f"Error in execute_take_profit_strategy: {e}")
        return {"status": "failed", "reason": str(e)}