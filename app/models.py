"""
NETRA Data Models
=================
Defines the core data structures used throughout the application.
Uses dataclasses for internal state and Pydantic for API data where applicable.
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from collections import deque


# =============================================================================
# TRACKING & OBJECT MODELS
# =============================================================================

@dataclass
class TrackedObject:
    """
    Represents a visually tracked object with smoothed spatial data.
    
    Attributes:
        name: Common name of the object.
        category: Object category (e.g., 'furniture', 'person').
        confidence: Detection confidence score (0-100).
        distance: Smoothed distance in meters.
        direction: Direction relative to user (e.g., 'ahead', 'left').
        last_seen: Timestamp of last detection.
    """
    name: str
    category: str
    confidence: float
    
    # Raw values from the latest single-frame detection
    raw_distance: float
    raw_direction: str
    
    # Smoothed/filtered values for stable UI/Audio
    distance: float
    direction: str
    
    # Tracking metadata
    last_seen: float
    frames_detected: int
    is_stable: bool = False  # Becomes true after persistence check

    def update(self, new_dist: float, new_dir: str, new_conf: float) -> None:
        """
        Update the object's state with new data using a weighted average for smoothing.
        
        Args:
            new_dist: Detected distance in meters.
            new_dir: Detected direction string.
            new_conf: Detection confidence score.
        """
        self.last_seen = time.time()
        self.frames_detected += 1
        
        # Update raw values
        self.raw_distance = new_dist
        self.raw_direction = new_dir
        self.confidence = new_conf

        # Weighted average for smoothing: 70% retention, 30% new value
        # This acts as a Low-Pass Filter (LPF) to reduce jitter.
        self.distance = (self.distance * 0.7) + (new_dist * 0.3)
        
        # Direction is discrete/categorical, so we update it directly
        self.direction = new_dir
        
        # Mark as stable after consecutive detections
        if self.frames_detected >= 2:
            self.is_stable = True


# =============================================================================
# MEMORY MODELS
# =============================================================================

@dataclass
class MemoryEntry:
    """Represents a short-term memory of an object."""
    timestamp: float
    direction: str
    distance: float
    category: str


# =============================================================================
# TASK & PLANNING MODELS
# =============================================================================

@dataclass
class TaskStep:
    """A single step in a high-level task plan."""
    step_id: int
    instruction: str
    items: List[str]
    completed: bool


@dataclass
class TaskState:
    """
    Current execution state of an interactive task.
    """
    is_active: bool = False
    plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step_index: int = 0
    waiting_for_user: bool = False

    @property
    def current_step(self) -> Optional[Dict[str, Any]]:
        """Return the current step dict or None if invalid."""
        if self.is_active and self.plan and self.current_step_index < len(self.plan):
            return self.plan[self.current_step_index]
        return None


@dataclass
class GlobalTaskState:
    """
    Persistent task state that survives WebSocket disconnects.
    """
    is_active: bool = False
    plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step_index: int = 0
    task_name: str = ""
    last_updated: float = 0.0
    
    def to_task_state(self) -> TaskState:
        """Convert global state to a session-specific TaskState."""
        return TaskState(
            is_active=self.is_active,
            plan=self.plan,
            current_step_index=self.current_step_index
        )
    
    def update_from(self, task_state: TaskState, task_name: str = "") -> None:
        """Update global state based on the current session state."""
        self.is_active = task_state.is_active
        self.plan = task_state.plan
        self.current_step_index = task_state.current_step_index
        if task_name:
            self.task_name = task_name
        self.last_updated = time.time()
    
    def is_valid(self) -> bool:
        """
        Check if the task state is valid and fresh.
        Expires after 5 minutes of inactivity.
        """
        return self.is_active and (time.time() - self.last_updated) < 300


# =============================================================================
# SESSION STATE
# =============================================================================

@dataclass
class SessionState:
    """
    Maintains the state for a single WebSocket connection.
    Includes memory, current mode, and processing buffers.
    """
    # Speech & Context History
    recent_speeches: deque = field(default_factory=lambda: deque(maxlen=5))
    last_speech_time: float = 0.0
    last_distance: float = 999.0
    smoothed_distance: float = 999.0
    last_direction: str = ""
    last_priority: str = "low"
    last_subject: str = ""
    
    # Social/Environmental Context
    social_context: deque = field(default_factory=lambda: deque(maxlen=5))
    
    # Frame Counters
    frame_count: int = 0
    frames_received: int = 0
    frames_processed: int = 0
    frames_skipped: int = 0
    
    # Navigation Mode State
    current_goal: Optional[str] = None
    micro_target: Optional[str] = None
    mode: str = "nav"  # "nav" | "micro" | "task"
    
    # Object Memory (Short-term)
    object_memory: Dict[str, MemoryEntry] = field(default_factory=dict)
    
    # Active Task
    task_state: TaskState = field(default_factory=TaskState)
    
    # Processing Flags
    latest_frame: Optional[Dict[str, Any]] = None
    is_processing: bool = False
    
    # Service Caches (Lazy Loaded)
    _tracker: Optional[Any] = None
    _speech_manager: Optional[Any] = None
    
    @property
    def tracker(self):
        """Lazy load the visual tracker to avoid circular imports."""
        if self._tracker is None:
            # pylint: disable=import-outside-toplevel
            from .services.tracking import VisualTracker
            self._tracker = VisualTracker()
        return self._tracker
    
    @property
    def speech_manager(self):
        """Lazy load the speech manager."""
        if self._speech_manager is None:
            # pylint: disable=import-outside-toplevel
            from .services.speech import SpeechManager
            self._speech_manager = SpeechManager()
        return self._speech_manager
    
    def prune_memory(self, retention_window: float = 30.0) -> None:
        """Remove objects not seen in the last `retention_window` seconds."""
        now = time.time()
        self.object_memory = {
            k: v for k, v in self.object_memory.items()
            if now - v.timestamp < retention_window
        }
        
    def get_memory_context(self) -> str:
        """Generate a natural language summary of currently visible objects."""
        if not self.object_memory:
            return "No objects in memory."
        
        parts = []
        for name, entry in self.object_memory.items():
            age = int(time.time() - entry.timestamp)
            parts.append(f"{name} ({entry.direction}, {entry.distance:.1f}m, {age}s ago)")
        return "Objects in memory: " + ", ".join(parts)
    
    def update_memory(self, subject: str, direction: str, distance: float, category: str) -> None:
        """Add or update an object in short-term memory."""
        self.object_memory[subject.lower()] = MemoryEntry(
            timestamp=time.time(),
            direction=direction,
            distance=distance,
            category=category
        )
        self.prune_memory()
        
    def add_speech(self, speech: str, priority: str, distance: float) -> None:
        """Log a spoken message to history."""
        self.recent_speeches.append(speech)
        self.last_speech_time = time.time()
        self.last_priority = priority
        self.last_distance = distance
