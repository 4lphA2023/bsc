import logging
from datetime import datetime

def setup_logging():
    """Configure and set up logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"sniper_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger()
    return logger

# Create a global logger instance
logger = setup_logging()