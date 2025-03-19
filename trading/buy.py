import time
from web3.exceptions import TimeExhausted, BadFunctionCallOutput, TransactionNotFound

from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from contracts.interfaces import get_router_contract, get_token_contract
from database.operations import record_transaction, add_to_portfolio, add_to_blacklist
import config

def calculate_min_tokens(token_address, bnb_amount, slippage_percentage=None):
    """Calculate minimum tokens to receive based on current rate and slippage
    
    Args:
        token_address: Token address
        bnb_amount: Amount of BNB to spend
        slippage_percentage: Slippage percentage (defaults to config value)
        
    Returns:
        int: Minimum tokens to receive or None if calculation fails
    """
    if slippage_percentage is None:
        slippage_percentage = config.SLIPPAGE
        
    try:
        # Get web3 instance
        w3 = Web3Singleton.get_instance()
        router_contract = get_router_contract()
        
        # Convert BNB amount to wei
        bnb_amount_wei = w3.to_wei(bnb_amount, 'ether')
        
        # Get expected tokens out
        amount_out = router_contract.functions.getAmountsOut(
            bnb_amount_wei,
            [config.WBNB_ADDRESS, token_address]
        ).call()
        
        # Apply slippage tolerance
        min_tokens = int(amount_out[1] * (100 - slippage_percentage) / 100)
        
        logger.info(f"Expected tokens: {amount_out[1]}, Min tokens after {slippage_percentage}% slippage: {min_tokens}")
        return min_tokens
    except Exception as e:
        logger.error(f"Error calculating minimum tokens: {e}")
        return None

def execute_buy(token_address, bnb_amount, is_test=False, max_retries=3):
    """Execute a buy transaction
    
    Args:
        token_address: Token address to buy
        bnb_amount: Amount of BNB to spend
        is_test: Whether this is a test buy (for honeypot check)
        max_retries: Maximum number of retry attempts
        
    Returns:
        dict: Transaction result or None if failed
    """
    for attempt in range(max_retries):
        try:
            # Get web3 instance
            w3 = Web3Singleton.get_instance()
            router_contract = get_router_contract()
            token_contract = get_token_contract(token_address)
            
            if not token_contract:
                logger.error(f"Failed to get token contract for {token_address}")
                return None
                
            # Get token symbol and decimals for reporting
            token_symbol = token_contract.functions.symbol().call()
            token_decimals = token_contract.functions.decimals().call()
            
            # Calculate minimum tokens to receive
            min_tokens = calculate_min_tokens(token_address, bnb_amount)
            if not min_tokens:
                logger.error(f"Failed to calculate minimum tokens for {token_address}")
                return None
                
            # Convert BNB amount to wei
            bnb_amount_wei = w3.to_wei(bnb_amount, 'ether')
            
            # Current gas price
            gas_price = int(w3.eth.gas_price * config.GAS_MULTIPLIER)
            
            # For nonce management: add a small delay and get the latest nonce
            time.sleep(1)  # Short delay to ensure blockchain state is updated
            
            # Current nonce with logging
            nonce = w3.eth.get_transaction_count(config.WALLET_ADDRESS)
            logger.info(f"Using nonce {nonce} for buy transaction")
            
            # Transaction deadline (5 minutes from now)
            deadline = int(time.time() + 300)
            
            # Build transaction
            tx = router_contract.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
                min_tokens,  # Minimum tokens to receive
                [config.WBNB_ADDRESS, token_address],  # Path
                config.WALLET_ADDRESS,  # Recipient
                deadline  # Deadline
            ).build_transaction({
                'from': config.WALLET_ADDRESS,
                'value': bnb_amount_wei,
                'gas': 300000,  # Gas limit
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': 56  # BSC Chain ID
            })
            
            # Sign transaction - Updated for Web3.py 7.x
            signed_tx = w3.eth.account.sign_transaction(tx, config.PRIVATE_KEY)
            
            # Web3.py 7.x compatibility: the raw_transaction attribute is different
            if hasattr(signed_tx, 'rawTransaction'):
                # For older Web3.py versions
                raw_tx = signed_tx.rawTransaction
            else:
                # For Web3.py 7.x
                raw_tx = signed_tx.raw_transaction
                
            # Send transaction
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Buy transaction sent: {tx_hash_hex}")
            
            # Wait for transaction receipt
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if tx_receipt['status'] == 1:
                logger.info(f"Buy transaction successful: {tx_hash_hex}")
                
                # Get token balance after purchase
                token_balance = token_contract.functions.balanceOf(
                    config.WALLET_ADDRESS
                ).call()
                
                # Record transaction
                transaction_type = "test_buy" if is_test else "buy"
                record_transaction(
                    token_address,
                    token_symbol,
                    transaction_type,
                    token_balance / (10 ** token_decimals),  # Convert to token units
                    bnb_amount,
                    tx_hash_hex
                )
                
                # Add to portfolio if not a test buy
                if not is_test:
                    token_price = bnb_amount / (token_balance / (10 ** token_decimals))
                    
                    add_to_portfolio(
                        token_address,
                        token_symbol,
                        token_balance / (10 ** token_decimals),
                        token_price,
                        bnb_amount,
                        config.TAKE_PROFIT_PERCENTAGE,
                        config.STOP_LOSS_PERCENTAGE
                    )
                
                return {
                    "status": "success",
                    "tx_hash": tx_hash_hex,
                    "token_balance": token_balance / (10 ** token_decimals),
                    "bnb_spent": bnb_amount
                }
            else:
                logger.error(f"Buy transaction failed: {tx_hash_hex}")
                
                # Add to blacklist if regular buy fails
                if not is_test:
                    add_to_blacklist(token_address, token_symbol, "Buy transaction failed")
                    
                return {
                    "status": "failed",
                    "tx_hash": tx_hash_hex
                }
                
        except (TimeExhausted, BadFunctionCallOutput, TransactionNotFound) as e:
            logger.warning(f"Transaction error during buy (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error executing buy (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff with larger delay for transaction-related errors
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1) * 2  # Double the backoff
            logger.info(f"Retrying buy in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries
    logger.error(f"Failed to execute buy for {token_address} after {max_retries} attempts")
    return None