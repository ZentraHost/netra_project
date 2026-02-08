"""
NETRA - Advanced Visual Navigation Assistant
Main Entry Point

This script serves as the entry point for the NETRA application.
It initializes the environment and launches the Uvicorn server.
"""

import os
import sys
import logging
import uvicorn
from contextlib import suppress

# Ensure the app directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import LOG_LEVEL

def main():
    """Run the NETRA application server."""
    # Enable colors on Windows consoles
    if os.name == 'nt':
        with suppress(Exception):
            os.system('color')

    logging.info("Starting NETRA Application...")

    try:
        uvicorn.run(
            "app:create_app",
            host="0.0.0.0",
            port=5000,
            reload=True,
            factory=True,
            log_level=LOG_LEVEL.lower(),
            ws_ping_interval=30,  # Keepalive ping every 30s
            ws_ping_timeout=60    # Allow 60s for response (handling long AI tasks)
        )
    except KeyboardInterrupt:
        logging.info("NETRA Application stopped by user.")
    except Exception as e:
        logging.critical(f"Failed to start NETRA Application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
