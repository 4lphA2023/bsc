"""
Singleton Web3 instance to ensure consistent usage across modules
"""
import time
from web3 import Web3
from web3.exceptions import TimeExhausted, BadFunctionCallOutput

from utils.logging_setup import logger
import config

class Web3Singleton:
    _instance = None
    
    @classmethod
    def get_instance(cls, force_reconnect=False):
        """Get the singleton Web3 instance, connecting if needed"""
        if cls._instance is None or force_reconnect:
            cls._instance = cls._connect()
        return cls._instance
    
    @classmethod
    def _connect(cls):
        """Connect to BSC with fallback RPC endpoints"""
        for rpc_attempt in range(len(config.BSC_RPC_ENDPOINTS)):
            rpc = config.BSC_RPC_ENDPOINTS[rpc_attempt]
            logger.info(f"Attempting to connect to BSC via {rpc}")
            
            for attempt in range(config.MAX_RETRIES):
                try:
                    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={
                        'timeout': config.CONNECTION_TIMEOUT,
                        'headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                    }))
                    
                    if w3.is_connected():
                        logger.info(f"Connected to BSC Mainnet via {rpc} (attempt {attempt+1})")
                        return w3
                        
                    logger.warning(f"Failed to connect to {rpc} - endpoint responded but connection test failed")
                except Exception as e:
                    backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
                    logger.warning(f"Connection to {rpc} failed (attempt {attempt+1}/{config.MAX_RETRIES}): {str(e)}")
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
        
        # If we get here, all RPC endpoints failed
        raise ConnectionError("Failed to connect to any BSC Mainnet RPC endpoint after multiple attempts")
    
    @classmethod
    def to_checksum_address(cls, address):
        """Convert address to checksum format"""
        try:
            w3 = cls.get_instance()
            if not w3.is_connected():
                logger.warning("Web3 connection lost during address checksum conversion, reconnecting...")
                w3 = cls.get_instance(force_reconnect=True)
                
            return w3.to_checksum_address(address)
        except Exception as e:
            logger.error(f"Invalid address format: {e}")
            return None
    
    @classmethod
    def get_gas_price(cls, max_retries=3):
        """Get current gas price with safety margin and retry logic"""
        for attempt in range(max_retries):
            try:
                w3 = cls.get_instance()
                if not w3.is_connected():
                    logger.warning("Web3 connection lost during gas price check, reconnecting...")
                    w3 = cls.get_instance(force_reconnect=True)
                    
                base_gas = w3.eth.gas_price
                return int(base_gas * config.GAS_MULTIPLIER)
            except Exception as e:
                logger.warning(f"Error getting gas price (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    backoff_time = config.RETRY_DELAY_BASE * (attempt + 1)
                    time.sleep(backoff_time)
        
        # If all retries fail, use a fallback gas price
        logger.warning("Using fallback gas price of 5 gwei")
        w3 = cls.get_instance()
        return w3.to_wei(5, 'gwei')

# Initialize web3 addresses with checksum format
def initialize_web3_addresses():
    """Initialize web3 addresses with checksum format"""
    # Make sure we have a web3 instance
    w3 = Web3Singleton.get_instance()
    
    # Initialize checksum addresses
    config.WBNB_ADDRESS = Web3Singleton.to_checksum_address(config.WBNB_ADDRESS)
    config.BUSD_ADDRESS = Web3Singleton.to_checksum_address(config.BUSD_ADDRESS)
    config.PANCAKE_FACTORY_ADDRESS = Web3Singleton.to_checksum_address(config.PANCAKE_FACTORY_ADDRESS)
    config.PANCAKE_ROUTER_ADDRESS = Web3Singleton.to_checksum_address(config.PANCAKE_ROUTER_ADDRESS)
    
    return w3