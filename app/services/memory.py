"""
NETRA Persistent Memory Service
===============================
Handles long-term storage of locations and object detection history.
Persists data to JSON to allow memory to survive application restarts.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..utils import Console
from ..config import BASE_DIR

MEMORY_FILE = BASE_DIR / "long_term_memory.json"


class PersistentMemory:
    """
    Manages reading and writing to the long-term memory file.
    """
    
    def __init__(self, filepath: Path = MEMORY_FILE):
        self.filepath = filepath
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load memory from disk, return empty structure if failed."""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"Error loading memory from {self.filepath}: {e}")
                return {"locations": {}, "history": []}
        return {"locations": {}, "history": []}

    def save(self) -> None:
        """Persist current memory state to disk."""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except OSError as e:
            logging.error(f"Error saving memory to {self.filepath}: {e}")

    def add_location(self, name: str, description: str) -> None:
        """
        Tag a specific location with a name and description.
        
        Args:
            name: unique name index (e.g. "My Desk").
            description: visual description.
        """
        if "locations" not in self.data:
            self.data["locations"] = {}
            
        self.data["locations"][name] = {
            "description": description,
            "timestamp": time.time()
        }
        self.save()
        Console.log('medium', f"📍 Location tagged: {name}", 'magenta')

    def get_locations(self) -> Dict[str, Any]:
        """Return all saved locations."""
        return self.data.get("locations", {})
        
    def get_location_summary(self) -> str:
        """Return a prompt-friendly string of known locations."""
        locs = self.get_locations()
        if not locs:
            return "No tagged locations yet."
        return ", ".join([f"'{k}': {v['description']}" for k, v in locs.items()])

    def log_object(self, object_name: str, location_tag: Optional[str], scene_desc: str) -> None:
        """
        Log an object sighting to history.
        
        Args:
            object_name: Name of the detected object.
            location_tag: Optional location tag (e.g. "Kitchen").
            scene_desc: Contextual description.
        """
        if not object_name or object_name.lower() in ["none", "unknown", "null"]:
            return
            
        entry = {
            "object": object_name,
            "location": location_tag,
            "scene": scene_desc,
            "timestamp": time.time()
        }
        
        # Initialize history if missing
        if "history" not in self.data:
            self.data["history"] = []
        
        # Avoid duplicate spam (same object detected within 10s)
        if self.data["history"]:
            last = self.data["history"][-1]
            if (last["object"] == object_name and 
                time.time() - last["timestamp"] < 10):
                return

        self.data["history"].append(entry)
        
        # Prune history (keep last 1000 entries)
        if len(self.data["history"]) > 1000:
            self.data["history"] = self.data["history"][-1000:]
            
        self.save()
        
    def get_history_context(self) -> str:
        """
        Returns recent object history formatted for the AI context window.
        """
        history = self.data.get("history", [])[-50:]  # Last 50 items
        if not history:
            return "No object history recorded."
            
        context = []
        for h in history:
            t_str = time.strftime('%H:%M', time.localtime(h['timestamp']))
            loc = f" at '{h['location']}'" if h.get('location') else ""
            context.append(f"[{t_str}] Saw {h['object']}{loc} ({h['scene']})")
        return "\n".join(context)


# Global instance
memory_store = PersistentMemory()
