import time
import argparse
import sys

# Initialize logger first
from utils.logging_setup import logger

# Import other modules
from utils.web3_singleton import Web3Singleton, initialize_web3_addresses
from utils.helpers import print_banner, get_portfolio_summary, get_transaction_history, calculate_total_profits
from contracts.interfaces import initialize_contracts
from database.models import initialize_database
from portfolio.management import start_portfolio_monitoring
# Change 'token' to 'tokendata' in these imports
from tokendata.analysis import analyze_token  
from tokendata.discovery import start_pair_listener, scan_recent_blocks
from trading.buy import execute_buy

def initialize_system():
    """Initialize the system components"""
    print_banner()
    
    logger.info("Initializing BSC Token Sniper...")
    
    # Initialize database
    if not initialize_database():
        logger.error("Failed to initialize database")
        return False
        
    # Initialize Web3 connection and addresses - This must be done first
    try:
        # Get web3 instance from singleton and initialize addresses
        w3 = Web3Singleton.get_instance()
        initialize_web3_addresses()
        
        if not w3.is_connected():
            logger.error("Failed to connect to BSC network")
            return False
            
        logger.info("Web3 connection established and addresses initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Web3 connection: {e}")
        return False
        
    # Initialize contracts after Web3 is connected
    if not initialize_contracts():
        logger.error("Failed to initialize contracts")
        return False
        
    logger.info("System initialization complete")
    return True

def run_token_sniper(token_address=None, bnb_amount=None, scan_blocks=None, auto_mode=False):
    """Run the token sniper
    
    Args:
        token_address: Specific token address to analyze/buy
        bnb_amount: BNB amount to spend
        scan_blocks: Number of blocks to scan for recent pairs
        auto_mode: Whether to enable automatic discovery mode
    """
    # Start portfolio monitoring
    monitoring_thread = start_portfolio_monitoring()
    
    if token_address:
        # Single token mode
        logger.info(f"Analyzing token: {token_address}")
        
        token_analysis = analyze_token(token_address)
        
        if token_analysis:
            logger.info(f"Token analysis successful: {token_analysis['symbol']} ({token_analysis['name']})")
            
            if bnb_amount:
                # Execute buy if BNB amount specified
                logger.info(f"Executing buy for {token_analysis['symbol']}: {bnb_amount} BNB")
                
                buy_result = execute_buy(token_address, bnb_amount)
                
                if buy_result and buy_result['status'] == 'success':
                    logger.info(f"Buy successful: {buy_result['token_balance']} {token_analysis['symbol']} for {buy_result['bnb_spent']} BNB")
                else:
                    logger.error(f"Buy failed for {token_analysis['symbol']}")
            else:
                logger.info(f"Analysis only mode - no buy executed for {token_analysis['symbol']}")
        else:
            logger.error(f"Token analysis failed for {token_address}")
    elif scan_blocks:
        # Scan recent blocks mode
        logger.info(f"Scanning {scan_blocks} recent blocks for new pairs")
        processed_pairs = scan_recent_blocks(scan_blocks)
        logger.info(f"Processed {len(processed_pairs)} pairs from recent blocks")
        
        # Continue with auto mode if enabled
        if auto_mode:
            # Start pair listener
            listener_thread = start_pair_listener()
            
            try:
                # Keep main thread alive
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                sys.exit(0)
    elif auto_mode:
        # Automatic discovery mode
        logger.info("Starting automatic discovery mode")
        
        # Start pair listener
        listener_thread = start_pair_listener()
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)
    else:
        # Monitoring mode only
        logger.info("No token address specified. Running in monitoring mode only.")
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='BSC Token Sniper')
    parser.add_argument('--token', '-t', help='Token address to analyze/buy')
    parser.add_argument('--amount', '-a', type=float, help='BNB amount to spend')
    parser.add_argument('--scan', '-s', type=int, help='Scan recent blocks for new pairs')
    parser.add_argument('--auto', action='store_true', help='Enable automatic discovery mode')
    parser.add_argument('--portfolio', '-p', action='store_true', help='Show portfolio summary')
    parser.add_argument('--transactions', action='store_true', help='Show transaction history')
    parser.add_argument('--profits', action='store_true', help='Show profit summary')
    
    args = parser.parse_args()
    
    # Initialize system
    if not initialize_system():
        logger.error("System initialization failed")
        return
    
    # Show portfolio if requested
    if args.portfolio:
        portfolio = get_portfolio_summary()
        if portfolio is not None:
            print("\n=== PORTFOLIO SUMMARY ===")
            print(portfolio.to_string(index=False))
            print()
        
    # Show transaction history if requested
    if args.transactions:
        transactions = get_transaction_history()
        if transactions is not None:
            print("\n=== TRANSACTION HISTORY ===")
            print(transactions.to_string(index=False))
            print()
        
    # Show profits if requested
    if args.profits:
        total_profits = calculate_total_profits()
        print(f"\n=== PROFIT SUMMARY ===")
        print(f"Total Profits: {total_profits:.6f} BNB")
        print()
        
    # If only reporting was requested, don't run the sniper
    if args.portfolio or args.transactions or args.profits:
        if not (args.token or args.scan or args.auto):
            return
        
    # Run token sniper
    run_token_sniper(
        token_address=args.token, 
        bnb_amount=args.amount,
        scan_blocks=args.scan,
        auto_mode=args.auto
    )

if __name__ == '__main__':
    main()