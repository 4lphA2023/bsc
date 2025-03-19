from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from contracts.abis import TOKEN_ABI, PAIR_ABI, FACTORY_ABI, ROUTER_ABI
import config

# Global contract instances
factory_contract = None
router_contract = None

def initialize_contracts():
    """Initialize contract instances using web3 connection"""
    global factory_contract, router_contract
    
    try:
        # Get web3 instance from singleton
        w3 = Web3Singleton.get_instance()
        
        # Create contract instances
        factory_contract = w3.eth.contract(
            address=config.PANCAKE_FACTORY_ADDRESS, 
            abi=FACTORY_ABI
        )
        
        router_contract = w3.eth.contract(
            address=config.PANCAKE_ROUTER_ADDRESS, 
            abi=ROUTER_ABI
        )
        
        # Test the contracts to ensure they work
        try:
            factory_test = factory_contract.functions.getPair(
                config.WBNB_ADDRESS, 
                config.BUSD_ADDRESS
            ).call()
            
            logger.info(f"Factory contract test: WBNB-BUSD pair = {factory_test}")
        except Exception as e:
            logger.error(f"Factory contract test failed: {e}")
            return False
        
        logger.info("Contracts initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing contracts: {e}")
        return False

def get_token_contract(token_address):
    """Get token contract instance"""
    try:
        w3 = Web3Singleton.get_instance()
        return w3.eth.contract(address=token_address, abi=TOKEN_ABI)
    except Exception as e:
        logger.error(f"Error getting token contract: {e}")
        return None

def get_pair_contract(pair_address):
    """Get pair contract instance"""
    try:
        w3 = Web3Singleton.get_instance()
        return w3.eth.contract(address=pair_address, abi=PAIR_ABI)
    except Exception as e:
        logger.error(f"Error getting pair contract: {e}")
        return None

def get_factory_contract():
    """Get factory contract instance"""
    global factory_contract
    
    if factory_contract is None:
        initialize_contracts()
        
    return factory_contract

def get_router_contract():
    """Get router contract instance"""
    global router_contract
    
    if router_contract is None:
        initialize_contracts()
        
    return router_contract