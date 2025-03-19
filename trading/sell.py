import time
from web3.exceptions import TimeExhausted, BadFunctionCallOutput, TransactionNotFound
from datetime import datetime, timedelta
from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from contracts.interfaces import get_router_contract, get_token_contract
from database.operations import record_transaction, update_portfolio_status
import config
from web3 import Web3

def estimate_bnb_output(token_address, token_amount, token_decimals, max_retries=3):
    """Estimate BNB output for a given token amount"""
    for attempt in range(max_retries):
        try:
            w3 = Web3Singleton.get_instance()
            router_contract = get_router_contract()
            
            token_amount_wei = int(token_amount * (10 ** token_decimals))
            
            amount_out = router_contract.functions.getAmountsOut(
                token_amount_wei,
                [token_address, config.WBNB_ADDRESS]
            ).call()
            
            bnb_output = w3.from_wei(amount_out[1], 'ether')
            
            logger.info(f"Estimated BNB output for {token_amount} tokens: {bnb_output} BNB")
            return float(bnb_output)
        except Exception as e:
            logger.error(f"Error estimating BNB output (attempt {attempt+1}/{max_retries}): {e}")
            
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying BNB output estimation in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    logger.error(f"Failed to estimate BNB output for {token_address} after {max_retries} attempts")
    return None

def queue_token_for_gradual_selling(token_address, token_symbol, token_decimals, total_amount):
    """
    Queue a token for gradual selling over time
    
    Args:
        token_address: Token address
        token_symbol: Token symbol
        token_decimals: Token decimals
        total_amount: Total amount to sell
        
    Returns:
        bool: True if queued successfully, False otherwise
    """
    try:
        # Create a queue entry in the database
        from database.operations import add_to_sell_queue
        
        # Calculate sell amounts: Start with 5% and gradually increase
        sell_schedule = [
            {"percent": 5, "delay_minutes": 5},   # Try 5% after 5 minutes
            {"percent": 10, "delay_minutes": 15}, # Try 10% after 15 minutes
            {"percent": 15, "delay_minutes": 30}, # Try 15% after 30 minutes
            {"percent": 20, "delay_minutes": 60}, # Try 20% after 1 hour
            {"percent": 50, "delay_minutes": 120} # Try 50% after 2 hours
        ]
        
        # Add each scheduled sell to the queue
        for schedule in sell_schedule:
            sell_amount = total_amount * (schedule["percent"] / 100)
            scheduled_time = datetime.now() + timedelta(minutes=schedule["delay_minutes"])
            
            add_to_sell_queue(
                token_address,
                token_symbol,
                token_decimals,
                sell_amount,
                scheduled_time
            )
            
        logger.info(f"Queued {token_symbol} for gradual selling over time")
        return True
    
    except Exception as e:
        logger.error(f"Error queuing token for gradual selling: {e}")
        return False

def decode_revert_reason(transaction_hash):
    """Attempt to decode revert reason from failed transaction"""
    try:
        w3 = Web3Singleton.get_instance()
        tx = w3.eth.get_transaction(transaction_hash)
        # Try to replay the transaction to get the revert reason
        try:
            w3.eth.call(
                {
                    'to': tx['to'],
                    'from': tx['from'],
                    'data': tx['input'],
                    'value': tx['value'],
                    'gas': tx['gas'],
                    'gasPrice': tx['gasPrice'],
                },
                tx['blockNumber'] - 1
            )
        except Exception as e:
            error_msg = str(e)
            # Extract revert reason
            if 'revert' in error_msg.lower():
                return error_msg
        return "Unknown reason"
    except Exception as e:
        logger.error(f"Error decoding revert reason: {e}")
        return "Could not decode"

def execute_sell(token_address, token_symbol, token_decimals, amount_tokens=None, portfolio_id=None, is_test=False, max_retries=3):
    """Execute a sell transaction"""
    # Keep track of failure reasons to adapt strategy
    failure_reasons = []
    
    for attempt in range(max_retries):
        try:
            w3 = Web3Singleton.get_instance()
            router_contract = get_router_contract()
            token_contract = get_token_contract(token_address)
            
            if not token_contract:
                logger.error(f"Failed to get token contract for {token_address}")
                return None
                
            # Get current token balance if amount not specified
            if amount_tokens is None:
                amount_tokens_wei = token_contract.functions.balanceOf(
                    config.WALLET_ADDRESS
                ).call()
                amount_tokens = amount_tokens_wei / (10 ** token_decimals)
                logger.info(f"Selling all tokens: {amount_tokens} {token_symbol}")
            else:
                # More aggressive reduction strategy based on prior failures
                if attempt > 0:
                    # If we've seen 'OUT_OF_GAS' or 'EXCEEDED_MAXIMUM' errors, reduce more aggressively
                    if any('gas' in reason.lower() for reason in failure_reasons) or any('exceed' in reason.lower() for reason in failure_reasons):
                        reduction_factor = 0.5 ** attempt  # 50% reduction each time
                    else:
                        reduction_factor = 0.8 ** attempt  # Normal 20% reduction
                        
                    original_amount = amount_tokens
                    amount_tokens = original_amount * reduction_factor
                    logger.info(f"Retry {attempt}: Reduced sell amount to {amount_tokens:.4f} {token_symbol} ({reduction_factor*100:.0f}% of original)")
                
                # Convert provided amount to wei equivalent
                amount_tokens_wei = int(amount_tokens * (10 ** token_decimals))
            
            # Add a check for minimum sell amount to avoid dust
            minimum_sell_amount_wei = 1000  # Very small amount to avoid dust sells
            if amount_tokens_wei < minimum_sell_amount_wei:
                logger.warning(f"Sell amount {amount_tokens} for {token_symbol} is too small, skipping")
                return {
                    "status": "skipped",
                    "reason": "Amount too small"
                }
            
            # Check if we need to approve the router
            allowance = token_contract.functions.allowance(
                config.WALLET_ADDRESS,
                config.PANCAKE_ROUTER_ADDRESS
            ).call()
            
            time.sleep(2)
            
            if allowance < amount_tokens_wei:
                logger.info(f"Approving PancakeSwap router to spend {token_symbol}")
                
                approval_nonce = w3.eth.get_transaction_count(config.WALLET_ADDRESS)
                logger.info(f"Using nonce {approval_nonce} for approval transaction")
                
                # Build approval transaction with higher gas
                approve_tx = token_contract.functions.approve(
                    config.PANCAKE_ROUTER_ADDRESS,
                    2 ** 256 - 1  # Max approval
                ).build_transaction({
                    'from': config.WALLET_ADDRESS,
                    'gas': 150000,  # Increased gas for approval
                    'gasPrice': int(w3.eth.gas_price * config.GAS_MULTIPLIER * 1.2),  # 20% higher
                    'nonce': approval_nonce,
                    'chainId': 56
                })
                
                signed_approve_tx = w3.eth.account.sign_transaction(approve_tx, config.PRIVATE_KEY)
                
                if hasattr(signed_approve_tx, 'rawTransaction'):
                    raw_approve_tx = signed_approve_tx.rawTransaction
                else:
                    raw_approve_tx = signed_approve_tx.raw_transaction
                    
                approve_tx_hash = w3.eth.send_raw_transaction(raw_approve_tx)
                
                approve_receipt = w3.eth.wait_for_transaction_receipt(approve_tx_hash, timeout=120)
                
                if approve_receipt['status'] != 1:
                    reason = decode_revert_reason(approve_tx_hash)
                    logger.error(f"Approval transaction failed: {approve_tx_hash.hex()}, reason: {reason}")
                    failure_reasons.append(f"APPROVAL_FAILED: {reason}")
                    return {
                        "status": "failed",
                        "reason": f"Approval failed: {reason}",
                        "tx_hash": approve_tx_hash.hex()
                    }
                    
                logger.info(f"Approval transaction successful: {approve_tx_hash.hex()}")
                
                time.sleep(3)
            
            # Estimate BNB output
            estimated_bnb = estimate_bnb_output(token_address, amount_tokens, token_decimals)
            if not estimated_bnb:
                logger.error(f"Failed to estimate BNB output for {token_symbol}")
                failure_reasons.append("ESTIMATION_FAILED")
                return {
                    "status": "failed",
                    "reason": "Failed to estimate BNB output"
                }
                
            # Increase slippage with each attempt and based on past failures
            base_extra_slippage = min(10 * attempt, 30)  # Max +30% extra slippage
            
            # If we've seen price impact errors, increase slippage more aggressively
            if any('price impact' in reason.lower() for reason in failure_reasons) or any('slippage' in reason.lower() for reason in failure_reasons):
                extra_slippage = min(base_extra_slippage + 15, 49)  # Add up to 15% more, max 49%
            else:
                extra_slippage = base_extra_slippage
                
            effective_slippage = config.SLIPPAGE + extra_slippage
            logger.info(f"Using slippage: {effective_slippage}% for sell transaction")
            
            # Calculate minimum BNB to receive (with dynamic slippage)
            min_bnb = int(w3.to_wei(estimated_bnb * (100 - effective_slippage) / 100, 'ether'))
            
            # Increased gas price and limit with each attempt and based on past failures
            gas_base_multiplier = 1 + (0.2 * attempt)  # +20% per attempt
            
            # If we've seen gas-related errors, increase gas more aggressively
            if any('gas' in reason.lower() for reason in failure_reasons):
                gas_multiplier = config.GAS_MULTIPLIER * gas_base_multiplier * 1.5  # 50% more gas
                gas_limit_multiplier = 1 + (0.4 * attempt)  # +40% per attempt
            else:
                gas_multiplier = config.GAS_MULTIPLIER * gas_base_multiplier
                gas_limit_multiplier = 1 + (0.2 * attempt)  # +20% per attempt
                
            gas_price = int(w3.eth.gas_price * gas_multiplier)
            gas_limit = 300000 * gas_limit_multiplier
            
            logger.info(f"Using gas limit {gas_limit:.0f} and gas price {gas_price} for sell transaction")
            
            # Get fresh nonce
            sell_nonce = w3.eth.get_transaction_count(config.WALLET_ADDRESS)
            logger.info(f"Using nonce {sell_nonce} for sell transaction")
            
            # Transaction deadline (longer with each attempt)
            deadline = int(time.time() + 300 + (300 * attempt))  # +5 min per attempt
            
            # Build transaction
            tx = router_contract.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
                amount_tokens_wei,  # Exact tokens to sell
                min_bnb,  # Minimum BNB to receive
                [token_address, config.WBNB_ADDRESS],  # Path
                config.WALLET_ADDRESS,  # Recipient
                deadline  # Deadline
            ).build_transaction({
                'from': config.WALLET_ADDRESS,
                'gas': int(gas_limit),
                'gasPrice': gas_price,
                'nonce': sell_nonce,
                'chainId': 56
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, config.PRIVATE_KEY)
            
            if hasattr(signed_tx, 'rawTransaction'):
                raw_tx = signed_tx.rawTransaction
            else:
                raw_tx = signed_tx.raw_transaction
                
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Sell transaction sent: {tx_hash_hex}")
            
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Log gas used for diagnostics
            gas_used = tx_receipt.get('gasUsed', 0)
            gas_usage_percent = (gas_used / int(gas_limit)) * 100
            logger.info(f"Gas used: {gas_used}/{int(gas_limit)} ({gas_usage_percent:.2f}%)")
            
            if tx_receipt['status'] == 1:
                logger.info(f"Sell transaction successful: {tx_hash_hex}")
                
                # Calculate profit/loss if not a test sell
                profit_loss_bnb = None
                if not is_test and portfolio_id is not None:
                    # TODO: Calculate profit/loss based on portfolio entry
                    pass
                
                # Record transaction
                transaction_type = "test_sell" if is_test else "sell"
                record_transaction(
                    token_address,
                    token_symbol,
                    transaction_type,
                    amount_tokens,
                    estimated_bnb,
                    tx_hash_hex,
                    profit_loss_bnb
                )
                
                # Update portfolio status if not a test sell
                if not is_test and portfolio_id is not None:
                    update_portfolio_status(portfolio_id, "sold")
                
                return {
                    "status": "success",
                    "tx_hash": tx_hash_hex,
                    "tokens_sold": amount_tokens,
                    "bnb_received": estimated_bnb
                }
            else:
                # Extract and log the reason for failure
                reason = decode_revert_reason(tx_hash)
                failure_reasons.append(reason)
                logger.error(f"Sell transaction failed: {tx_hash_hex}, reason: {reason}")
                
                # Record the failed transaction for future analysis
                try:
                    from database.operations import record_failed_transaction
                    record_failed_transaction(
                        token_address, 
                        token_symbol, 
                        "sell", 
                        amount_tokens, 
                        tx_hash_hex, 
                        reason
                    )
                except ImportError:
                    logger.warning("Failed to record failed transaction: record_failed_transaction function not available")
                
                # If gas usage is near 100%, likely out of gas
                if gas_usage_percent > 95:
                    failure_reasons.append("OUT_OF_GAS")
                    logger.error(f"Transaction likely failed due to out of gas (used {gas_usage_percent:.2f}%)")
                
        except (TimeExhausted, BadFunctionCallOutput, TransactionNotFound) as e:
            error_message = str(e)
            failure_reasons.append(error_message)
            logger.warning(f"Transaction error during sell (attempt {attempt+1}/{max_retries}): {e}")
            
            # Add specific handling for known error patterns
            if "gas required exceeds allowance" in error_message:
                # Likely needs more gas, increase gas limit more aggressively next time
                failure_reasons.append("EXCEEDED_MAXIMUM")
            elif "always failing transaction" in error_message:
                # Token might have selling restrictions
                failure_reasons.append("ALWAYS_FAILING")
            elif "execution reverted" in error_message:
                failure_reasons.append("EXECUTION_REVERTED")
            
            # Try to record the failed transaction 
            try:
                from database.operations import record_failed_transaction
                record_failed_transaction(
                    token_address, 
                    token_symbol, 
                    "sell", 
                    amount_tokens, 
                    None,  # No tx hash in this case
                    error_message
                )
            except ImportError:
                logger.warning("Failed to record failed transaction: record_failed_transaction function not available")
                
        except Exception as e:
            error_message = str(e)
            failure_reasons.append(error_message)
            logger.error(f"Error executing sell (attempt {attempt+1}/{max_retries}): {e}")
            
            # Try to record the failed transaction
            try:
                from database.operations import record_failed_transaction
                record_failed_transaction(
                    token_address, 
                    token_symbol, 
                    "sell", 
                    amount_tokens, 
                    None,  # No tx hash in this case
                    error_message
                )
            except ImportError:
                logger.warning("Failed to record failed transaction: record_failed_transaction function not available")
            
        # Exponential backoff with larger delay
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1) * 2
            logger.info(f"Retrying sell in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    logger.error(f"Failed to execute sell for {token_address} after {max_retries} attempts")
    
    # If we've exhausted all retries, check if we should queue this token for gradual selling
    if len(failure_reasons) >= 3 and any(reason in ["ALWAYS_FAILING", "EXECUTION_REVERTED"] for reason in failure_reasons):
        logger.info(f"Token {token_symbol} appears to have selling restrictions, queuing for gradual selling")
        try:
            from database.operations import add_to_sell_queue
            # Create a queue entry in the database for gradual selling
            sell_schedule = [
                {"percent": 5, "delay_minutes": 5},   # Try 5% after 5 minutes
                {"percent": 10, "delay_minutes": 15}, # Try 10% after 15 minutes
                {"percent": 15, "delay_minutes": 30}, # Try 15% after 30 minutes
                {"percent": 20, "delay_minutes": 60}, # Try 20% after 1 hour
                {"percent": 50, "delay_minutes": 120} # Try 50% after 2 hours
            ]
            
            for schedule in sell_schedule:
                sell_amount = amount_tokens * (schedule["percent"] / 100)
                scheduled_time = datetime.now() + timedelta(minutes=schedule["delay_minutes"])
                
                add_to_sell_queue(
                    token_address,
                    token_symbol,
                    token_decimals,
                    sell_amount,
                    scheduled_time
                )
            
            logger.info(f"Queued {token_symbol} for gradual selling over time")
        except ImportError:
            logger.warning("Failed to queue token for gradual selling: add_to_sell_queue function not available")
    
    return {
        "status": "failed",
        "reasons": failure_reasons,
        "token_address": token_address,
        "token_symbol": token_symbol
    }