"""
NETRA Visual Tracking Service
=============================
Correlates object detections across frames to provide stable tracking info.
Prevents UI jitter/flashing by requiring persistence before confirmation.
"""

import time
from typing import List, Dict, Optional

from ..models import TrackedObject


class VisualTracker:
    """
    Manages the lifecycle of tracked objects.
    
    Attributes:
        confidence_threshold (int): Minimum confidence (0-100) to consider a detection.
        persistence_frames (int): Frames an object must be seen to be 'stable'.
        timeout (float): Seconds to keep an object in memory if lost.
    """
    
    def __init__(self, confidence_threshold: int = 75, persistence_frames: int = 2, timeout: float = 2.0):
        self.tracked_objects: Dict[str, TrackedObject] = {}
        self.confidence_threshold = confidence_threshold
        self.persistence_frames = persistence_frames
        self.timeout = timeout

    def process_detections(self, detections: List[Dict]) -> List[TrackedObject]:
        """
        Ingest a fresh list of raw detections from the AI model.
        Updates internal state and returns a list of *stable* objects for the UI.
        
        Args:
            detections: List of dicts with keys (name, confidence_score, distance, etc.)
            
        Returns:
            List[TrackedObject]: Objects that meet stability criteria.
        """
        now = time.time()
        
        # 1. Prune expired objects
        self.tracked_objects = {
            k: v for k, v in self.tracked_objects.items()
            if now - v.last_seen < self.timeout
        }

        # 2. Update/Create objects
        for det in detections:
            name = det.get("name")
            confidence = det.get("confidence_score", 100)
            
            # Skip low confidence or invalid detections
            if not name or confidence < self.confidence_threshold:
                continue

            # Keying by name is simplistic but effective for semantic grouping
            # (e.g. all "chair" detections group together)
            key = name.lower()
            
            dist = float(det.get("distance", 0.0))
            direction = det.get("direction", "ahead")
            category = det.get("category", "unknown")

            if key in self.tracked_objects:
                # Update existing
                self.tracked_objects[key].update(dist, direction, confidence)
            else:
                # Initialize new
                self.tracked_objects[key] = TrackedObject(
                    name=name,
                    category=category,
                    confidence=confidence,
                    raw_distance=dist,
                    raw_direction=direction,
                    distance=dist,
                    direction=direction,
                    last_seen=now,
                    frames_detected=1
                )
        
        # 3. Return only stable objects
        return [
            obj for obj in self.tracked_objects.values()
            if obj.is_stable
        ]

    def get_primary_target(self, stable_objects: List[TrackedObject]) -> Optional[TrackedObject]:
        """
        Identify the single most "important" object to highlight.
        Currently selects the closest stable object.
        """
        if not stable_objects:
            return None
        return min(stable_objects, key=lambda x: x.distance)
