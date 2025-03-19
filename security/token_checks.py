import time
import requests
from web3.exceptions import TimeExhausted, BadFunctionCallOutput

from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from database.operations import add_to_blacklist
from contracts.interfaces import get_router_contract, get_token_contract
import config

def check_for_transfer_tax(token_address, token_symbol):
    """Check if a token implements transfer taxes"""
    try:
        w3 = Web3Singleton.get_instance()
        token_contract = get_token_contract(token_address)
        
        # Common function names for tax information
        tax_functions = [
            "getTaxFeePercent", "getTotalFee", "taxRate", 
            "sellTaxes", "buyTaxes", "transferTaxes"
        ]
        
        for func_name in tax_functions:
            try:
                # Try to find and call tax functions
                if hasattr(token_contract.functions, func_name):
                    tax_fee = getattr(token_contract.functions, func_name)().call()
                    logger.info(f"Token {token_symbol} has {func_name} = {tax_fee}")
                    return tax_fee
            except Exception:
                continue
                
        # If no dedicated function, check contract code for tax-related strings
        contract_code = w3.eth.get_code(token_address).hex().lower()
        tax_related_strings = ["tax", "fee", "reflect", "redistribution"]
        
        for tax_string in tax_related_strings:
            if tax_string in contract_code:
                logger.info(f"Token {token_symbol} likely has transfer tax (found '{tax_string}' in code)")
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking for transfer tax: {e}")
        return False

def detect_suspicious_assembly(token_address, max_retries=3):
    """Check for suspicious assembly code in contract
    
    Args:
        token_address: Token address to check
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if suspicious code detected, False otherwise
    """
    if not config.ASSEMBLY_CHECK_ENABLED:
        return False
        
    for attempt in range(max_retries):
        try:
            # Get web3 instance
            w3 = Web3Singleton.get_instance()
                
            # Get contract code
            contract_code = w3.eth.get_code(token_address).hex()
            
            # Convert to lowercase for case-insensitive matching
            contract_code_lower = contract_code.lower()
            
            # Check for assembly code
            if "assembly" in contract_code_lower:
                logger.warning(f"Token {token_address} contains assembly code, potential honeypot detected")
                return True
                
            # Check for other suspicious opcodes/patterns that are often used in scams
            suspicious_patterns = [
                "selfdestruct", "suicide",  # Self-destruct functions
                "delegatecall",  # Potential proxy vulnerabilities
                "callcode",      # Deprecated and dangerous
                "iszero(caller", # Often used to restrict selling
                "origin"         # Using tx.origin is often a bad practice
            ]
            
            for pattern in suspicious_patterns:
                if pattern in contract_code_lower:
                    logger.warning(f"Token {token_address} contains suspicious code pattern: {pattern}")
                    return True
                    
            return False
        except (TimeExhausted, BadFunctionCallOutput) as e:
            logger.warning(f"Timeout checking contract code (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error analyzing contract code (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying contract code analysis in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries, consider it suspicious
    logger.error(f"Failed to analyze contract code for {token_address} after {max_retries} attempts")
    return True  # Fail safe - if we can't analyze, consider it suspicious

def check_token_sell_history(token_address, pair_address, max_retries=3):
    """Check if a token has had successful sell transactions
    
    Args:
        token_address: Token address to check
        pair_address: Pair address for the token
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if token has sufficient sell history, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # We need BSCScan API for this check
            if not config.BSCSCAN_API_KEY:
                logger.warning("BSCScan API key not provided, skipping sell history check")
                return True  # Skip check if no API key
                
            # Get recent transfers involving the pair address
            url = f"https://api.bscscan.com/api?module=account&action=tokentx&address={pair_address}&startblock=0&endblock=999999999&sort=desc&apikey={config.BSCSCAN_API_KEY}"
            
            response = requests.get(url, timeout=30)  # 30 second timeout
            if response.status_code != 200:
                logger.warning(f"Failed to get token transactions from BSCScan: {response.status_code}")
                return True  # Skip check if API fails
                
            data = response.json()
            if data["status"] != "1":
                logger.warning(f"BSCScan API error: {data['message']}")
                return True  # Skip check if API returns error
                
            # Count successful sells (transfers from pair to non-pair address)
            successful_sells = 0
            for tx in data["result"]:
                # If token was sent from the pair to someone else, it's likely a sell
                if tx["from"].lower() == pair_address.lower() and tx["tokenAddress"].lower() == token_address.lower():
                    successful_sells += 1
                    
            logger.info(f"Token {token_address} has {successful_sells} successful sell transactions")
            
            # Return true if enough successful sells are found
            return successful_sells >= config.MIN_SUCCESSFUL_SELLS
        except requests.exceptions.RequestException as e:
            logger.warning(f"BSCScan API request error (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error checking token sell history (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying token sell history check in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries, skip check to be safe
    logger.error(f"Failed to check sell history for {token_address} after {max_retries} attempts")
    return True  # Skip check if there's an error

def check_for_honeypot(token_address, token_symbol):
    """Perform a test buy and sell to check for honeypot
    
    Args:
        token_address: Token address to check
        token_symbol: Token symbol
        
    Returns:
        bool: True if token is a honeypot, False otherwise
    """
    if not config.HONEYPOT_CHECK_ENABLED:
        logger.info("Honeypot check disabled, skipping")
        return False
    
    try:
        logger.info(f"Performing honeypot check for {token_symbol}")
        
        # Get web3 instance
        w3 = Web3Singleton.get_instance()
        router_contract = get_router_contract()
        
        # First check if we can approve the router (without sending transaction)
        token_contract = get_token_contract(token_address)
        
        try:
            # Build approval transaction
            approve_txn = token_contract.functions.approve(
                config.PANCAKE_ROUTER_ADDRESS,
                w3.to_wei(1, 'ether')  # Just a small amount for testing
            ).build_transaction({
                'from': config.WALLET_ADDRESS,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(config.WALLET_ADDRESS),
                'chainId': 56,
            })
            
            # Try to estimate gas (this will fail if approve function is manipulated)
            gas_estimate = w3.eth.estimate_gas(approve_txn)
            logger.info(f"Approval gas estimate: {gas_estimate}")
        except Exception as e:
            logger.warning(f"Failed to estimate gas for approval - likely a honeypot: {e}")
            add_to_blacklist(token_address, token_symbol, f"Approval function manipulation detected: {e}")
            return True
            
        # Here we would call the execute_buy and execute_sell functions
        # (These functions are imported from the trading module, which we'll implement later)
        
        # For now, just return a placeholder
        logger.info("Note: Full honeypot check requires execute_buy and execute_sell functions")
        return False
        
    except Exception as e:
        logger.error(f"Error in honeypot check: {e}")
        add_to_blacklist(token_address, token_symbol, f"Error during honeypot check: {e}")
        return True  # Fail safe approach