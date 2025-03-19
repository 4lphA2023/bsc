import time
import threading
from web3.exceptions import LogTopicError, BlockNotFound

from utils.logging_setup import logger
from utils.web3_singleton import Web3Singleton
from contracts.interfaces import get_factory_contract
from tokendata.analysis import analyze_token
from trading.buy import execute_buy
import config

def handle_new_pair(token_address, pair_address):
    """Handle a newly created trading pair
    
    Args:
        token_address: Token address
        pair_address: Pair address
        
    Returns:
        bool: True if successfully handled, False otherwise
    """
    try:
        logger.info(f"New pair detected: {pair_address} - Token: {token_address}")
        
        # Analyze token
        token_analysis = analyze_token(token_address)
        
        if not token_analysis:
            logger.warning(f"Token analysis failed for {token_address}")
            return False
            
        logger.info(f"Token analysis successful: {token_analysis['symbol']} ({token_analysis['name']})")
        
        # Execute buy if all checks pass
        investment_amount = min(config.MAX_INVESTMENT_PER_TOKEN, token_analysis['liquidity_bnb'] / config.LIQUIDITY_SAFETY_MULTIPLIER)
        
        logger.info(f"Executing buy for {token_analysis['symbol']}: {investment_amount} BNB")
        
        buy_result = execute_buy(token_address, investment_amount)
        
        if buy_result and buy_result['status'] == 'success':
            logger.info(f"Buy successful: {buy_result['token_balance']} {token_analysis['symbol']} for {buy_result['bnb_spent']} BNB")
            return True
        else:
            logger.error(f"Buy failed for {token_analysis['symbol']}")
            return False
            
    except Exception as e:
        logger.error(f"Error handling new pair: {e}")
        return False

def process_pair_created_event(event_data):
    """Process a PairCreated event
    
    Args:
        event_data: PairCreated event data
        
    Returns:
        bool: True if successfully processed, False otherwise
    """
    try:
        # Extract event data - updated for web3.py 7.x
        token0 = event_data.args.token0
        token1 = event_data.args.token1
        pair_address = event_data.args.pair
        
        logger.info(f"PairCreated event: token0={token0}, token1={token1}, pair={pair_address}")
        
        # Determine which token is the one we're interested in (paired with WBNB)
        if token0.lower() == config.WBNB_ADDRESS.lower():
            target_token = token1
        elif token1.lower() == config.WBNB_ADDRESS.lower():
            target_token = token0
        else:
            # Neither token is WBNB, we're not interested
            logger.info(f"Skipping pair without WBNB: {pair_address}")
            return False
            
        # Handle the new token
        return handle_new_pair(target_token, pair_address)
        
    except Exception as e:
        logger.error(f"Error processing PairCreated event: {e}")
        return False

def scan_recent_blocks(blocks_to_scan=50):
    """Scan recent blocks for PairCreated events - reduced to work with rate limits
    
    Args:
        blocks_to_scan: Number of blocks to scan (reduced default to avoid rate limits)
        
    Returns:
        list: Processed pairs
    """
    try:
        # Check web3 connection
        w3 = Web3Singleton.get_instance()
        
        factory_contract = get_factory_contract()
        
        # Get current block number
        current_block = w3.eth.block_number
        from_block = max(1, current_block - blocks_to_scan)
        
        logger.info(f"Scanning for PairCreated events from block {from_block} to {current_block}")
        
        # Process in much smaller batches to avoid rate limits
        batch_size = 10  # Molto più piccoli batch per evitare limiti di frequenza
        processed_pairs = []
        
        # Più tempo tra le richieste iniziali
        time.sleep(5)
        
        for batch_start in range(from_block, current_block, batch_size):
            batch_end = min(batch_start + batch_size - 1, current_block)
            
            try:
                logger.info(f"Scanning blocks {batch_start} to {batch_end}")
                
                # Add delay between requests to avoid rate limits
                time.sleep(3)  # Aumentato da 1 a 3 secondi
                
                # Use the newer API for web3.py 7.x
                events = factory_contract.events.PairCreated.get_logs(from_block=batch_start, to_block=batch_end)
                
                for event in events:
                    if process_pair_created_event(event):
                        processed_pairs.append(event.args.pair)
                        
            except (LogTopicError, BlockNotFound) as e:
                logger.warning(f"Error scanning blocks {batch_start} to {batch_end}: {e}")
            except Exception as e:
                # Aggiungere backoff esponenziale quando si raggiungono i limiti
                if "limit exceeded" in str(e):
                    # Ritardo esponenziale quando si raggiunge il limite
                    backoff_time = 10 * ((batch_start - from_block) // batch_size + 1)
                    logger.warning(f"Limite di frequenza raggiunto, attendere {backoff_time} secondi...")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Unexpected error scanning blocks {batch_start} to {batch_end}: {e}")
                    # Add increasing delay on errors to respect rate limits
                    time.sleep(5)  # Aumentato da 3 a 5 secondi
                
        logger.info(f"Completed scanning {blocks_to_scan} blocks, processed {len(processed_pairs)} pairs")
        return processed_pairs
        
    except Exception as e:
        logger.error(f"Error scanning recent blocks: {e}")
        return []

def start_pair_listener():
    """Start listening for new pairs in a separate thread
    
    Returns:
        threading.Thread: Listener thread
    """
    def listener_thread():
       # # Scan recent blocks first to catch any pairs created while we were offline
       # try:
       #     # Scan only recent blocks to avoid rate limits
       #     scan_recent_blocks(50)  # Ridotto ulteriormente a 50 blocchi
       # except Exception as e:
       #     logger.error(f"Error scanning recent blocks: {e}")
       # 
        # Set up event filter
        factory_contract = get_factory_contract()
        
        while True:
            try:
                # Create event filter for latest blocks using web3.py 7.x approach
                # Only listen for new blocks, don't try to scan history
                event_filter = factory_contract.events.PairCreated.create_filter(from_block='latest')
                
                logger.info("Listening for new PairCreated events...")
                
                # Poll for new events
                last_check = time.time()
                
                while True:
                    try:
                        # Check for new entries
                        new_events = event_filter.get_new_entries()
                        
                        for event in new_events:
                            process_pair_created_event(event)
                            
                        # Log periodic updates with less frequency to avoid spamming the log
                        now = time.time()
                        if now - last_check > 300:  # Every 5 minutes
                            logger.info("Still listening for PairCreated events...")
                            last_check = now
                            
                        # Sleep to avoid too many requests (increased to respect rate limits)
                        time.sleep(5)  # Aumentato da 3 a 5 secondi
                        
                    except Exception as e:
                        logger.error(f"Error getting new entries: {e}")
                        # Recreate filter and continue
                        break
                        
            except Exception as e:
                logger.error(f"Error in listener thread: {e}")
                
            # Sleep before reconnecting (increased to respect rate limits)
            time.sleep(60)  # Aumentato da 30 a 60 secondi
    
    # Start listener thread
    thread = threading.Thread(target=listener_thread)
    thread.daemon = True
    thread.start()
    
    logger.info("Pair listener started")
    return thread