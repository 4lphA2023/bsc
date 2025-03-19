"""
This file provides backward compatibility with the old connections module.
It redirects all calls to the new Web3Singleton class.
"""
from utils.web3_singleton import Web3Singleton, initialize_web3_addresses

# For backward compatibility
def get_web3_connection(max_retries=None, retry_delay=None):
    """Get web3 connection using singleton"""
    return Web3Singleton.get_instance()

def to_checksum_address(address):
    """Convert address to checksum format"""
    return Web3Singleton.to_checksum_address(address)

def get_gas_price(max_retries=3):
    """Get current gas price with safety margin and retry logic"""
    return Web3Singleton.get_gas_price(max_retries)

def initialize_connections():
    """Initialize web3 connection and set up checksum addresses"""
    web3 = Web3Singleton.get_instance()
    initialize_web3_addresses()
    return web3

# Access to the web3 instance for backward compatibility
web3 = None
def update_web3_reference():
    """Update the web3 reference for backward compatibility"""
    global web3
    web3 = Web3Singleton.get_instance()

# Initialize web3 reference
update_web3_reference()