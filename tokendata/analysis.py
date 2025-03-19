import time
from web3.exceptions import TimeExhausted, BadFunctionCallOutput, TransactionNotFound

from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from contracts.interfaces import get_factory_contract, get_token_contract, get_pair_contract
from database.operations import add_to_blacklist, is_token_blacklisted
import config

def get_pair_address(token_address, max_retries=3):
    """Get the trading pair address for a token
    
    Args:
        token_address: Token address
        max_retries: Maximum number of retry attempts
        
    Returns:
        str: Pair address or None if not found
    """
    for attempt in range(max_retries):
        try:
            # Check web3 connection first
            w3 = Web3Singleton.get_instance()
                
            factory_contract = get_factory_contract()
                
            # Get pair address from PancakeSwap factory
            pair_address = factory_contract.functions.getPair(
                config.WBNB_ADDRESS, 
                token_address
            ).call()
            
            if pair_address == '0x0000000000000000000000000000000000000000':
                return None
            
            return pair_address
        except (TimeExhausted, BadFunctionCallOutput) as e:
            logger.warning(f"Timeout getting pair address (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error getting pair address (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying get_pair_address in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries
    logger.error(f"Failed to get pair address for {token_address} after {max_retries} attempts")
    return None

def fetch_token_data(token_address, max_retries=3):
    """Fetch token metadata using Web3
    
    Args:
        token_address: Token address
        max_retries: Maximum number of retry attempts
        
    Returns:
        dict: Token data or None if failed
    """
    for attempt in range(max_retries):
        try:
            # Get web3 instance
            w3 = Web3Singleton.get_instance()
                
            # Convert address to checksum format if needed
            if isinstance(token_address, str):
                token_address = w3.to_checksum_address(token_address)
                
            if not token_address:
                return None
            
            # Check if token is blacklisted
            if is_token_blacklisted(token_address):
                logger.warning(f"Token {token_address} is blacklisted, skipping")
                return None
            
            # Create token contract
            token_contract = get_token_contract(token_address)
            if not token_contract:
                logger.error(f"Failed to get token contract for {token_address}")
                return None
            
            # Get token details (Web3.py 7.x compatible - no timeout)
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            total_supply = token_contract.functions.totalSupply().call()

            # Check for blacklisted words in name/symbol
            name_lower = name.lower()
            symbol_lower = symbol.lower()
            for pattern in config.BLACKLISTED_PATTERNS:
                if pattern in name_lower or pattern in symbol_lower:
                    logger.warning(f"Token {symbol} contains blacklisted pattern: {pattern}")
                    add_to_blacklist(token_address, symbol, f"Contains blacklisted pattern: {pattern}")
                    return None

            logger.info(f"Token: {symbol} ({name}), Decimals: {decimals}, Total Supply: {total_supply}")
            return {
                "name": name,
                "symbol": symbol,
                "decimals": decimals,
                "total_supply": total_supply,
                "address": token_address
            }
        except (TimeExhausted, BadFunctionCallOutput) as e:
            # Specific web3 timeout errors
            logger.warning(f"Web3 timeout during token data fetch (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error fetching token data (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying fetch_token_data in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries
    logger.error(f"Failed to fetch token data for {token_address} after {max_retries} attempts")
    return None

def check_token_liquidity(token_address, pair_address, max_retries=3):
    """Check if a token has sufficient liquidity
    
    Args:
        token_address: Token address
        pair_address: Pair address for the token
        max_retries: Maximum number of retry attempts
        
    Returns:
        float: Liquidity in BNB or None if insufficient
    """
    for attempt in range(max_retries):
        try:
            w3 = Web3Singleton.get_instance()
                
            # Get pair contract
            pair_contract = get_pair_contract(pair_address)
            if not pair_contract:
                logger.error(f"Failed to get pair contract for {pair_address}")
                return None
                
            # Get reserves
            reserves = pair_contract.functions.getReserves().call()
            
            # Get token0 address to determine reserve order
            token0 = pair_contract.functions.token0().call()
            
            # Determine which reserve is BNB and which is the token
            if token0.lower() == config.WBNB_ADDRESS.lower():
                bnb_reserve = reserves[0]
                token_reserve = reserves[1]
            else:
                bnb_reserve = reserves[1]
                token_reserve = reserves[0]
                
            # Convert wei to BNB
            bnb_liquidity = w3.from_wei(bnb_reserve, 'ether')
            
            logger.info(f"Token {token_address} has {bnb_liquidity} BNB in liquidity")
            
            # Check if liquidity is sufficient
            if bnb_liquidity < config.MIN_LIQUIDITY:
                logger.warning(f"Insufficient liquidity: {bnb_liquidity} BNB (minimum: {config.MIN_LIQUIDITY} BNB)")
                return None
                
            return float(bnb_liquidity)
        except (TimeExhausted, BadFunctionCallOutput) as e:
            logger.warning(f"Timeout checking liquidity (attempt {attempt+1}/{max_retries}): {e}")
        except Exception as e:
            logger.error(f"Error checking liquidity (attempt {attempt+1}/{max_retries}): {e}")
            
        # Exponential backoff
        if attempt < max_retries - 1:
            backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
            logger.info(f"Retrying liquidity check in {backoff_time} seconds...")
            time.sleep(backoff_time)
    
    # If we've exhausted all retries
    logger.error(f"Failed to check liquidity for {token_address} after {max_retries} attempts")
    return None

def analyze_token(token_address):
    """Perform a comprehensive analysis of a token
    
    Args:
        token_address: Token address to analyze
        
    Returns:
        dict: Analysis results or None if token fails checks
    """
    # Get web3 instance
    w3 = Web3Singleton.get_instance()
    
    # Convert address to checksum format
    if isinstance(token_address, str):
        token_address = w3.to_checksum_address(token_address)
        
    if not token_address:
        logger.error(f"Invalid token address format")
        return None
        
    # Check if token is blacklisted
    if is_token_blacklisted(token_address):
        logger.warning(f"Token {token_address} is blacklisted, skipping analysis")
        return None
        
    # Fetch token data
    token_data = fetch_token_data(token_address)
    if not token_data:
        logger.warning(f"Failed to fetch token data for {token_address}")
        return None
        
    # Get pair address
    pair_address = get_pair_address(token_address)
    if not pair_address:
        logger.warning(f"No liquidity pair found for {token_data['symbol']} ({token_address})")
        return None
        
    # Check token liquidity
    liquidity = check_token_liquidity(token_address, pair_address)
    if not liquidity:
        logger.warning(f"Insufficient liquidity for {token_data['symbol']} ({token_address})")
        return None
        
    # Import security checks to avoid circular imports
    from security.token_checks import detect_suspicious_assembly, check_token_sell_history, check_for_honeypot
        
    # Perform security checks
    if detect_suspicious_assembly(token_address):
        logger.warning(f"Suspicious code detected in {token_data['symbol']} ({token_address})")
        add_to_blacklist(token_address, token_data['symbol'], "Suspicious assembly code detected")
        return None
        
    if not check_token_sell_history(token_address, pair_address):
        logger.warning(f"Insufficient sell history for {token_data['symbol']} ({token_address})")
        add_to_blacklist(token_address, token_data['symbol'], "Insufficient sell history")
        return None
        
    if check_for_honeypot(token_address, token_data['symbol']):
        logger.warning(f"Honeypot detected: {token_data['symbol']} ({token_address})")
        add_to_blacklist(token_address, token_data['symbol'], "Honeypot detected")
        return None
        
    # If all checks pass, return token analysis results
    analysis_result = {
        **token_data,
        "pair_address": pair_address,
        "liquidity_bnb": liquidity,
        "passed_security_checks": True
    }
    
    logger.info(f"Token {token_data['symbol']} ({token_address}) passed all security checks")
    return analysis_result