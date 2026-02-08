"""
NETRA Utility Functions
=======================
Helper functions for text processing, logging, and console formatting.
"""

import sys
import logging
import datetime
from typing import Optional, Set

# =============================================================================
# TEXT PROCESSING
# =============================================================================

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate Jaccard similarity between two text strings.
    
    Args:
        text1: First string.
        text2: Second string.
        
    Returns:
        float: Similarity score between 0.0 and 1.0.
    """
    if not text1 or not text2:
        return 0.0
        
    # Normalize: lower case and split into words
    s1: Set[str] = set(text1.lower().split())
    s2: Set[str] = set(text2.lower().split())
    
    if not s1 or not s2:
        return 0.0
        
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    
    return intersection / union


def format_distance_speech(meters: float) -> str:
    """
    Convert a numeric distance into natural speech text.
    
    Args:
        meters: Distance in meters.
        
    Returns:
        str: Human-readable distance string (e.g., "50 centimeters", "2.1 meters").
    """
    if meters < 1.0:
        cm = int(meters * 100)
        return f"{cm} centimeters"
    elif meters < 10.0:
        return f"{meters:.1f} meters"
    else:
        return f"{int(meters)} meters"


def extract_semantic_key(subject: str, direction: str, category: str) -> str:
    """
    Create a semantic key to identify unique object occurrences.
    Ignores common adjectives to group similar objects together.
    
    Args:
        subject: The object name (e.g., "large grey door").
        direction: Relative direction.
        category: Object category.
        
    Returns:
        str: Normalized key (e.g., "door|ahead|navigation").
    """
    # Normalize subject
    subject_normalized = subject.lower().strip()
    
    # Adjectives to strip out for core identity matching
    ignore_words = {
        "grey", "gray", "white", "black", "brown", "red", "blue", "green",
        "open", "closed", "small", "large", "big", "little", "tiny", "huge",
        "old", "new", "patterned", "textured", "wooden", "metal"
    }
    
    words = subject_normalized.split()
    filtered_words = [w for w in words if w not in ignore_words]
    
    # If we stripped everything, revert to original to avoid empty string
    core_subject = " ".join(filtered_words) if filtered_words else subject_normalized
    
    return f"{core_subject}|{direction}|{category}"


# =============================================================================
# CONSOLE LOGGING
# =============================================================================

class Console:
    """
    Styled console output for CLI visibility.
    Handles color codes and icon mapping.
    """
    
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'grey': '\033[90m',
        'reset': '\033[0m',
        'bold': '\033[1m',
    }

    ICONS = {
        'critical': '🚨', 'high': '⚠️ ', 'medium': '📍', 'low': '✅', 'info': 'ℹ️ ',
        'human': '🧑', 'animal': '🐕', 'vehicle': '🚗', 'furniture': '🪑',
        'door': '🚪', 'stairs': '🪜', 'speak': '🔊', 'silent': '🔇',
        'network': '📶', 'connect': '🔗', 'disconnect': '⛓️ '
    }

    @classmethod
    def _color(cls, text: str, color: str) -> str:
        """Apply ANSI color codes if supported."""
        return f"{cls.COLORS.get(color, '')}{text}{cls.COLORS['reset']}"

    @classmethod
    def timestamp(cls) -> str:
        """Return formatted current timestamp."""
        return cls._color(datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], 'grey')

    @classmethod
    def header(cls) -> None:
        """Print the application startup banner."""
        banner = """
======================================================================
  NETRA - Advanced Visual Navigation Assistant
======================================================================
  Comprehensive detection • Smart frame handling • Precise guidance
======================================================================
"""
        print(cls._color(banner, 'cyan'))

    @classmethod
    def log(cls, icon_key: str, message: str, color: str = 'white', details: str = "") -> None:
        """
        Print a formatted log line.
        
        Args:
            icon_key: Key for the icon dictionary.
            message: Main log message.
            color: Color for the main message.
            details: Optional extra details (will be grey).
        """
        try:
            icon = cls.ICONS.get(icon_key, '•')
            colored_msg = cls._color(message, color)
            line = f"{cls.timestamp()} {icon} {colored_msg}"
            if details:
                line += cls._color(f" │ {details}", 'grey')
            print(line)
        except UnicodeEncodeError:
            # Fallback for systems with poor unicode support
            print(f"[LOG] {message} {details}")

    @classmethod
    def detection(cls, priority: str, scene: str, distance: float, speech: str, 
                  speak: bool, proc_time: int, skip_reason: str = "") -> None:
        """
        Print a detailed detection block.
        """
        prio_color = {
            'critical': 'red', 'high': 'yellow', 'medium': 'cyan', 'low': 'green'
        }.get(priority, 'white')
        
        icon = cls.ICONS.get(priority, '•')
        
        # Color code distance
        if distance < 0.5:
            dist_color = 'red'
        elif distance < 1.0:
            dist_color = 'yellow'
        else:
            dist_color = 'green'
        
        dist_str = cls._color(f"{distance:.1f}m", dist_color)
        status_icon = cls.ICONS['speak'] if speak else cls.ICONS['silent']
        status_text = cls._color("SPEAKING", 'green') if speak else cls._color(f"SKIP ({skip_reason})", 'grey')
        
        # Truncate speech for display if too long
        display_speech = (speech[:75] + '...') if len(speech) > 75 else speech
        
        try:
            print(f"\n{cls.timestamp()} {'─'*60}")
            print(f"  {icon} {cls._color(priority.upper(), prio_color)} │ {scene}")
            print(f"  📏 Dist: {dist_str} │ ⏱️ {proc_time}ms │ {status_icon} {status_text}")
            if display_speech:
                print(f"  💬 {cls._color(display_speech, 'white')}")
            print(f"{'─'*67}")
        except UnicodeEncodeError:
            print(f"\n[DETECTION] {priority.upper()} - {scene}")
            print(f"Dist: {distance:.1f}m | Time: {proc_time}ms | Speak: {speak}")
