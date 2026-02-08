"""
NETRA Speech Management Service
===============================
Manages Text-to-Speech (TTS) rules to prevent repetitive announcements
while ensuring critical alerts are always delivered.
"""

import time
from typing import Dict, List, Tuple

from ..utils import extract_semantic_key
from ..config import (
    CRITICAL_REPEAT_INTERVAL,
    HIGH_REPEAT_INTERVAL,
    MEDIUM_REPEAT_INTERVAL,
    LOW_REPEAT_INTERVAL
)


class SpeechManager:
    """
    Decides when to trigger speech output based on priority, context, and timing.
    """
    
    def __init__(self):
        self.current_speech_end_time: float = 0.0
        self.last_semantic_key: str = ""
        self.last_speech_time: float = 0.0
        self.last_distance: float = 999.0
        self.last_priority: str = "low"
        
        # subject -> last announce timestamp
        self.announced_subjects: Dict[str, float] = {}
        
        self.recent_speeches: List[str] = []
        
    def estimate_speech_duration(self, text: str) -> float:
        """
        Estimate duration of speech in seconds.
        Assumes ~150 wpm (2.5 words/sec) + 0.5s buffer.
        """
        word_count = len(text.split())
        return (word_count / 2.5) + 0.5
    
    def is_speaking(self) -> bool:
        """Check if the system is currently speaking."""
        return time.time() < self.current_speech_end_time
    
    def should_speak(self, priority: str, subject: str, direction: str, 
                     category: str, distance: float, speech_text: str) -> Tuple[bool, str]:
        """
        Determine if we should speak this update.
        
        Returns:
            Tuple[bool, str]: (Should Speak, Reason for decision)
        """
        now = time.time()
        semantic_key = extract_semantic_key(subject, direction, category)
        
        priority_map = {
            "critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0
        }
        current_prio_val = priority_map.get(priority, 0)
        last_prio_val = priority_map.get(self.last_priority, 0)
        
        # 1. CRITICAL PRIORITY: Always interrupt
        if priority == "critical":
            return True, "critical_alert"
        
        # 2. DO NOT INTERRUPT (unless scaling up priority significantly)
        if self.is_speaking():
            # Exception: Priority escalated AND object got closer
            if current_prio_val > last_prio_val and distance < (self.last_distance - 0.3):
                return True, "priority_escalation"
            return False, "speech_in_progress"
        
        # 3. SAME CONTEXT CHECK (Debounce)
        if semantic_key == self.last_semantic_key:
            return self._check_same_context(priority, now, distance)
            
        # 4. NEW CONTEXT CHECK
        return self._check_new_context(subject, now)

    def _check_same_context(self, priority: str, now: float, distance: float) -> Tuple[bool, str]:
        """Handle logic for when the object/context is mostly unchanged."""
        time_since_last = now - self.last_speech_time
        
        # Priority-based cooldowns
        cooldowns = {
            "critical": CRITICAL_REPEAT_INTERVAL,
            "high": HIGH_REPEAT_INTERVAL,
            "medium": MEDIUM_REPEAT_INTERVAL,
            "low": LOW_REPEAT_INTERVAL
        }
        min_interval = cooldowns.get(priority, MEDIUM_REPEAT_INTERVAL)
        
        distance_change = self.last_distance - distance
        
        # Speak if: moved significantly closer OR cooldown passed
        if distance_change > 0.5:
            return True, "distance_closed"
            
        if time_since_last < min_interval:
            remaining = int(min_interval - time_since_last)
            return False, f"same_context_cooldown ({remaining}s left)"
            
        return True, "interval_passed"

    def _check_new_context(self, subject: str, now: float) -> Tuple[bool, str]:
        """Handle logic for a new object/context."""
        # Global cooldown between ANY non-critical speech
        time_since_any = now - self.last_speech_time
        if time_since_any < 3.0:
            return False, "global_cooldown"

        # Subject-specific cooldown (don't repeat "Chair" every 5 seconds if looking around)
        last_announce = self.announced_subjects.get(subject.lower(), 0)
        if now - last_announce < 10.0:
            return False, "subject_recently_announced"
            
        return True, "new_context"
    
    def record_speech(self, speech_text: str, priority: str, subject: str, 
                      direction: str, category: str, distance: float) -> None:
        """Update state after deciding to speak."""
        now = time.time()
        duration = self.estimate_speech_duration(speech_text)
        
        self.current_speech_end_time = now + duration
        self.last_semantic_key = extract_semantic_key(subject, direction, category)
        self.last_speech_time = now
        self.last_distance = distance
        self.last_priority = priority
        self.announced_subjects[subject.lower()] = now
        
        # Maintain history buffer
        self.recent_speeches.append(speech_text)
        if len(self.recent_speeches) > 5:
            self.recent_speeches.pop(0)
        
        # Prune old announced subjects
        self.announced_subjects = {
            k: v for k, v in self.announced_subjects.items()
            if now - v < 60.0
        }
