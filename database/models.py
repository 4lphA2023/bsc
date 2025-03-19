import sqlite3
from utils.logging_setup import logger

def initialize_database():
    """Set up database tables if they don't exist"""
    try:
        conn = sqlite3.connect('portfolio.db')
        cursor = conn.cursor()
        
        # Create portfolio table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT NOT NULL,
            token_symbol TEXT NOT NULL,
            amount_tokens REAL NOT NULL,
            purchase_price_bnb REAL NOT NULL,
            investment_amount_bnb REAL NOT NULL,
            purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            take_profit_target REAL NOT NULL,
            stop_loss_target REAL NOT NULL,
            status TEXT DEFAULT 'active'
        )
        ''')
        
        # Create transactions table for history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT NOT NULL,
            token_symbol TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount_tokens REAL,
            amount_bnb REAL,
            transaction_hash TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            profit_loss_bnb REAL
        )
        ''')
        
        # Create blacklisted tokens table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklisted_tokens (
            token_address TEXT PRIMARY KEY,
            token_symbol TEXT,
            reason TEXT,
            blacklist_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def get_connection():
    """Get a database connection"""
    try:
        return sqlite3.connect('portfolio.db')
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None