import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up BSC Mainnet connection (with expanded fallback RPCs)
BSC_RPC_ENDPOINTS = [
    os.getenv('BSC_MAINNET_RPC_1', 'https://bsc-dataseed.binance.org/'),
    os.getenv('BSC_MAINNET_RPC_2', 'https://bsc-dataseed1.defibit.io/'),
    os.getenv('BSC_MAINNET_RPC_3', 'https://bsc-dataseed1.ninicoin.io/'),
    'https://bsc-dataseed2.defibit.io/',
    'https://bsc-dataseed3.defibit.io/',
    'https://bsc-dataseed4.defibit.io/',
    'https://bsc-dataseed2.ninicoin.io/',
    'https://bsc-dataseed3.ninicoin.io/',
    'https://bsc-dataseed4.ninicoin.io/',
    'https://bsc-dataseed1.binance.org/',
    'https://bsc-dataseed2.binance.org/',
    'https://bsc-dataseed3.binance.org/',
    'https://bsc-dataseed4.binance.org/'
]

# Security-critical variables
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
if not PRIVATE_KEY:
    raise ValueError("PRIVATE_KEY environment variable is required")

WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
if not WALLET_ADDRESS:
    raise ValueError("WALLET_ADDRESS environment variable is required")

# Optional BSCScan API key for additional checks
BSCSCAN_API_KEY = os.getenv('BSCSCAN_API_KEY', '')

# Config variables with defaults
MAX_INVESTMENT_PER_TOKEN = float(os.getenv('MAX_INVESTMENT_PER_TOKEN', '0.05'))  # in BNB
MIN_LIQUIDITY = float(os.getenv('MIN_LIQUIDITY', '5'))  # in BNB
SLIPPAGE = float(os.getenv('SLIPPAGE', '10'))  # in percent
GAS_MULTIPLIER = float(os.getenv('GAS_MULTIPLIER', '1.2'))  # multiply recommended gas

# Anti-scam settings
TEST_BUY_AMOUNT = float(os.getenv('TEST_BUY_AMOUNT', '0.005'))  # in BNB for test buys
MIN_SUCCESSFUL_SELLS = int(os.getenv('MIN_SUCCESSFUL_SELLS', '3'))  # Minimum number of sell transactions to consider token safe
HONEYPOT_CHECK_ENABLED = os.getenv('HONEYPOT_CHECK_ENABLED', 'true').lower() == 'true'
ASSEMBLY_CHECK_ENABLED = os.getenv('ASSEMBLY_CHECK_ENABLED', 'true').lower() == 'true'
LIQUIDITY_SAFETY_MULTIPLIER = float(os.getenv('LIQUIDITY_SAFETY_MULTIPLIER', '1.5'))  # Minimum liquidity safety multiplier

# Profit-taking settings
TAKE_PROFIT_PERCENTAGE = float(os.getenv('TAKE_PROFIT_PERCENTAGE', '20'))  # Sell when profit reaches 20%
STOP_LOSS_PERCENTAGE = float(os.getenv('STOP_LOSS_PERCENTAGE', '10'))  # Sell when loss reaches 10%
MAX_HOLDING_TIME = float(os.getenv('MAX_HOLDING_TIME', '24'))  # Maximum holding time in hours
MONITORING_INTERVAL = float(os.getenv('MONITORING_INTERVAL', '60'))  # Check portfolio every 60 seconds

# Connection retry settings
MAX_RETRIES = 5
RETRY_DELAY_BASE = 2
CONNECTION_TIMEOUT = 30

# Blacklisted token patterns (for security)
BLACKLISTED_PATTERNS = [
    "test", "scam", "fake", "honey", "pot", "honeypot", "rug", "pull", "rugpull",
    "moon", "safe", "gem", "100x", "1000x", "fair", "presale", "pre-sale", "ico"
]

# Contract addresses on Mainnet - these will be properly initialized with checksum format
# by initialize_connections() function
WBNB_ADDRESS = os.getenv('WBNB_ADDRESS', '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c')
BUSD_ADDRESS = os.getenv('BUSD_ADDRESS', '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56')
PANCAKE_FACTORY_ADDRESS = os.getenv('PANCAKE_FACTORY_ADDRESS', '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73')
PANCAKE_ROUTER_ADDRESS = os.getenv('PANCAKE_ROUTER_ADDRESS', '0x10ED43C718714eb63d5aA57B78B54704E256024E')