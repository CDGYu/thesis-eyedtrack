"""
Event logging module for driver monitoring system.
"""

import json
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

def round_to_4dp(value):
    """Round a value to 4 decimal places"""
    try:
        return round(float(value), 4)
    except (ValueError, TypeError):
        return 0.0

def get_event_type(event_data: Dict[str, Any]) -> str:
    """Determine the event type based on behavior categories"""
    if not event_data.get("face_box"):
        return "no_face"
    
    # Get behavior category from nested structure
    behavior_category = event_data.get("behavior_category", {})
    
    if behavior_category.get("is_drowsy", False):
        return "drowsy"
    elif behavior_category.get("is_yawning", False):
        return "yawning"
    elif behavior_category.get("is_distracted", False):
        return "distracted"
    else:
        return "normal"

def log_event(log_dir: Path, event_type: str, event_data: Dict[str, Any]) -> None:
    """Log all events to a single JSON file"""
    try:
        # Create the directory if it doesn't exist
        if not isinstance(log_dir, Path):
            log_dir = Path(str(log_dir))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a single fixed filename for all events
        events_file = log_dir / 'driver_monitoring.json'
        
        # Extract required data from event_data
        timestamp = event_data.get("timestamp", datetime.now().isoformat())
        
        # Get behavior category from nested structure
        behavior_category = event_data.get("behavior_category", {
            "is_drowsy": False,
            "is_yawning": False,
            "is_distracted": False
        })
        
        # Get metrics from nested structure
        metrics = event_data.get("metrics", {})
        mar = round_to_4dp(metrics.get("mar", 0.0))
        ear = round_to_4dp(metrics.get("ear", 0.0))
        
        # Get head pose angles from metrics - rounded to 4 decimal places
        head_pose = metrics.get("head_pose", [0, 0, 0])
        if isinstance(head_pose, (list, tuple, np.ndarray)) and len(head_pose) >= 2:
            yaw, pitch = head_pose[0], head_pose[1]  # Note: yaw is first in head_pose array
        else:
            pitch, yaw = 0.0, 0.0
            
        pitch = round_to_4dp(float(pitch))
        yaw = round_to_4dp(float(yaw))
        
        # Get behavior confidence - rounded to 4 decimal places
        behavior_confidence = round_to_4dp(event_data.get("behavior_confidence", 0.0))
        
        # Determine behavior output
        if not event_data.get("face_box"):
            behavior_output = "NO FACE DETECTED"
        elif any(behavior_category.values()):
            behavior_output = "RISKY BEHAVIOR DETECTED"
        else:
            behavior_output = "NO RISKY BEHAVIOR DETECTED"
            
        # Create and log the event
        event = {
            "timestamp": timestamp,
            "behavior_category": behavior_category,
            "behavior_output": behavior_output,
            "mar": mar,
            "ear": ear,
            "pitch": pitch,
            "yaw": yaw,
            "behavior_confidence": behavior_confidence
        }
        
        try:
            # Append event as a single line to the log file
            with open(events_file, 'a', encoding='utf-8') as f:
                json_str = json.dumps(event)
                f.write(json_str + "\n")
                f.flush()
                os.fsync(f.fileno())
                
        except Exception as e:
            logger.error(f"Failed to log event: {str(e)}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Failed to process event data: {str(e)}", exc_info=True) 