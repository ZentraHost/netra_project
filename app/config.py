"""
NETRA Configuration Module

This module consolidates all configuration constants, environment variables,
and settings for the NETRA application. It uses a robust pattern for
environment variable loading and provides typed constants for use throughout
the application.
"""

import os
import logging
from typing import Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# =============================================================================
# PATH CONFIGURATION
# =============================================================================
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DEBUG_DIR: Path = Path(os.getenv('DEBUG_DIR', 'debug'))
STATIC_DIR: Path = BASE_DIR / "static"
TEMPLATES_DIR: Path = BASE_DIR / "templates"

# Create debug directory if it doesn't exist
try:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create debug directory at {DEBUG_DIR}: {e}")

# =============================================================================
# IMAGE PROCESSING SETTINGS
# =============================================================================
# Dimensions for image resizing (width, height)
IMAGE_SIZE: Tuple[int, int] = (224, 160)
MODEL_NAME: str = "gemini-3-flash-preview"  # Updated to latest stable flash model
MODEL_TIMEOUT: float = float(os.getenv('MODEL_TIMEOUT', '8.0'))

# =============================================================================
# SPEECH TIMING SETTINGS (in seconds)
# =============================================================================
# Minimum interval between repetitions of the same speech
CRITICAL_REPEAT_INTERVAL: float = 1.0
HIGH_REPEAT_INTERVAL: float = 2.0
MEDIUM_REPEAT_INTERVAL: float = 4.0
LOW_REPEAT_INTERVAL: float = 8.0

# =============================================================================
# DISTANCE THRESHOLDS (in meters)
# =============================================================================
CRITICAL_DISTANCE: float = 0.5
DANGER_DISTANCE: float = 1.0
CAUTION_DISTANCE: float = 2.0

# =============================================================================
# ANTI-REPETITION & LOGIC SETTINGS
# =============================================================================
SIMILARITY_THRESHOLD: float = 0.65
RECENT_MESSAGES_COUNT: int = 5

# =============================================================================
# API KEYS & SECURITY
# =============================================================================
GEMINI_KEY: Optional[str] = os.getenv("GEMINI_KEY")

if not GEMINI_KEY:
    logging.warning("GEMINI_KEY is not set in environment variables. AI features will fail.")
