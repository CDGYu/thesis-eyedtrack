"""
Eye and mouth aspect ratio calculations for driver monitoring.
"""

import numpy as np
import logging
from collections import deque

# Configure module-level logger
logger = logging.getLogger(__name__)

# Global variables for EAR/MAR normalization
_ear_lower = 0.15  # Lowered from 0.18 to better detect closed eyes
_ear_upper = 0.35  # Lowered from 0.45 as values above 0.35 are anatomically unlikely
_mar_lower = 0.20
_mar_upper = 0.70  # Increased from 0.65 to allow for wider yawns

# Smoothing buffers
_ear_buffer = deque(maxlen=10)
_mar_buffer = deque(maxlen=10)

def configure_thresholds(ear_lower=0.15, ear_upper=0.35, mar_lower=0.20, mar_upper=0.70):
    """Configure the thresholds for EAR and MAR normalization"""
    global _ear_lower, _ear_upper, _mar_lower, _mar_upper
    _ear_lower = ear_lower
    _ear_upper = ear_upper
    _mar_lower = mar_lower
    _mar_upper = mar_upper

def weighted_temporal_smoothing(new_value, history, alpha=0.3):
    """
    Apply weighted smoothing with more weight on recent values
    
    Args:
        new_value: The newest measurement
        history: List of previous measurements
        alpha: Weight factor for new value (0.3 provides good balance)
        
    Returns:
        Smoothed value
    """
    if not history:
        return new_value
    
    smoothed = alpha * new_value + (1 - alpha) * history[-1]
    return float(smoothed)

def get_point_coordinates(points, index):
    """
    Extract point coordinates from various landmark formats.
    Works with dlib landmarks, numpy arrays, and lists of (x,y) tuples.
    """
    try:
        # For dlib landmarks with part() method
        if hasattr(points, 'part'):
            pt = points.part(index)
            return (pt.x, pt.y)
        # For numpy array
        elif isinstance(points, np.ndarray):
            if len(points.shape) == 2 and points.shape[1] >= 2:
                return (points[index, 0], points[index, 1])
        # For list/tuple of (x,y) coordinates
        elif isinstance(points, (list, tuple)) and index < len(points):
            pt = points[index]
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                return (pt[0], pt[1])
    except Exception as e:
        logger.error(f"Error getting point coordinates at index {index}: {e}")
    
    # Return (0,0) if we can't get the coordinates
    return (0, 0)

def eye_aspect_ratio(eye_points):
    """
    Calculate the eye aspect ratio for a single eye.
    
    Args:
        eye_points: List of 6 points representing the eye landmarks,
                   or a dlib.full_object_detection object.
    
    Returns:
        float: The eye aspect ratio, or None if calculation fails
    """
    try:
        # Validate input
        if eye_points is None:
            return None

        # Extract points with validation
        points = []
        for i in range(6):
            pt = get_point_coordinates(eye_points, i)
            if pt is None:
                return None
            points.append(pt)

        # Convert points to numpy arrays
        points = np.array(points, dtype=np.float64)
        if not np.all(np.isfinite(points)):
            return None

        # Calculate distances
        # Vertical distances
        A = np.linalg.norm(points[1] - points[5])
        B = np.linalg.norm(points[2] - points[4])
        # Horizontal distance
        C = np.linalg.norm(points[0] - points[3])

        # Validate distances
        if not all(np.isfinite([A, B, C])) or C <= 0:
            return None

        # Compute EAR
        ear = (A + B) / (2.0 * C)
        
        # Validate EAR is within anatomically possible range
        if not (0.05 <= ear <= 0.45):  # More lenient anatomical range
            return None

        return float(ear)

    except Exception as e:
        logger.error(f"Error in eye_aspect_ratio: {e}")
        return None

def mouth_aspect_ratio(mouth_points):
    """
    Calculate the mouth aspect ratio.
    
    Args:
        mouth_points: List of 6 points representing the mouth landmarks,
                     or a dlib.full_object_detection object.
    
    Returns:
        float: The mouth aspect ratio, or None if calculation fails
    """
    try:
        # Validate input
        if mouth_points is None:
            return None

        # Extract points with validation
        points = []
        
        # Check if this is a dlib object or numpy array
        if hasattr(mouth_points, 'part'):
            # dlib landmarks - use original indices for mouth region
            indices = [48, 50, 52, 54, 56, 58]
        else:
            # For numpy array of mouth points, use indices based on array size
            if isinstance(mouth_points, np.ndarray) and len(mouth_points) >= 6:
                # Use first 6 points in a pattern that makes sense for MAR calculation
                indices = [0, 1, 2, 3, 4, 5]  # Use all 6 points we have
            else:
                logger.debug(f"Invalid mouth_points format: {type(mouth_points)}, length: {len(mouth_points) if hasattr(mouth_points, '__len__') else 'unknown'}")
                return None
        
        for idx in indices:
            pt = get_point_coordinates(mouth_points, idx)
            if pt is None:
                return None
            points.append(pt)

        # Convert points to numpy arrays
        points = np.array(points, dtype=np.float64)
        if not np.all(np.isfinite(points)):
            return None

        # Calculate distances for MAR
        # For 6 points, we'll use a different approach:
        # Points 0,3 = horizontal distance (left-right corners)
        # Points 1,4 = first vertical distance 
        # Points 2,5 = second vertical distance
        A = np.linalg.norm(points[1] - points[4])  # First vertical distance
        B = np.linalg.norm(points[2] - points[5])  # Second vertical distance
        C = np.linalg.norm(points[0] - points[3])  # Horizontal distance

        # Validate distances
        if not all(np.isfinite([A, B, C])) or C <= 0:
            return None

        # Compute MAR
        mar = (A + B) / (2.0 * C)
        
        # Validate MAR is within anatomically possible range
        if not (0.05 <= mar <= 1.5):  # More lenient range for mouth
            return None

        return float(mar)

    except Exception as e:
        logger.error(f"Error in mouth_aspect_ratio: {e}")
        return None

def normalize_value(value, lower, upper):
    """Normalize a value between 0 and 1 based on lower and upper bounds"""
    try:
        if value is None:
            return None
            
        # Clip the value to the bounds
        clipped = max(lower, min(upper, value))
        
        # Normalize to 0-1 range
        normalized = (clipped - lower) / (upper - lower)
        
        return normalized
    except Exception as e:
        logger.error(f"Error normalizing value: {e}")
        return None

def get_eye_state(ear):
    """Determine eye state based on eye aspect ratio with confidence score"""
    try:
        # Validate input
        if not isinstance(ear, (int, float)) or not np.isfinite(ear):
            logger.warning(f"Invalid EAR value: {ear}")
            return "UNKNOWN", 0.5

        # Normalize EAR value
        normalized_ear = normalize_value(ear, _ear_lower, _ear_upper)
        
        # Invert so that 0 = eyes open, 1 = eyes closed
        normalized_ear = 1.0 - normalized_ear
        
        # Calculate confidence based on distance from thresholds
        if normalized_ear < 0.2:
            confidence = 1.0 - (normalized_ear / 0.2)  # Higher confidence when closer to 0
            return "OPEN", min(1.0, max(0.0, confidence))
        elif normalized_ear < 0.7:
            # Lower confidence in the middle range
            confidence = 0.5
            return "PARTIALLY_CLOSED", confidence
        else:
            confidence = (normalized_ear - 0.7) / 0.3  # Higher confidence when closer to 1
            return "CLOSED", min(1.0, max(0.0, confidence))
    except Exception as e:
        logger.error(f"Error determining eye state: {e}")
        return "UNKNOWN", 0.5

def get_mouth_state(mar):
    """Determine mouth state based on mouth aspect ratio with confidence score"""
    try:
        # Validate input
        if not isinstance(mar, (int, float)) or not np.isfinite(mar):
            logger.warning(f"Invalid MAR value: {mar}")
            return "UNKNOWN", 0.5

        # Normalize MAR value
        normalized_mar = normalize_value(mar, _mar_lower, _mar_upper)
        
        # Calculate confidence based on distance from thresholds
        if normalized_mar < 0.3:
            confidence = 1.0 - (normalized_mar / 0.3)  # Higher confidence when closer to 0
            return "CLOSED", min(1.0, max(0.0, confidence))
        elif normalized_mar < 0.7:
            # Lower confidence in the middle range
            confidence = 0.5
            return "PARTIALLY_OPEN", confidence
        else:
            confidence = (normalized_mar - 0.7) / 0.3  # Higher confidence when closer to 1
            return "WIDE OPEN", min(1.0, max(0.0, confidence))
    except Exception as e:
        logger.error(f"Error determining mouth state: {e}")
        return "UNKNOWN", 0.5

def get_facial_state(right_ear, left_ear, mar, use_smoothing=True):
    """Get the facial state including normalized EAR and MAR values with optional smoothing and confidence scores"""
    try:
        # Handle None values
        if right_ear is None or left_ear is None:
            return {
                "right_ear": None,
                "left_ear": None,
                "avg_ear": None,
                "mar": mar,
                "normalized_ear": None,
                "normalized_mar": normalize_value(mar, _mar_lower, _mar_upper) if mar is not None else None,
                "ear_confidence": 0.0,
                "mar_confidence": 0.5 if mar is not None else 0.0
            }

        # Calculate average EAR
        avg_ear = (right_ear + left_ear) / 2.0
        
        # Apply temporal smoothing if enabled
        if use_smoothing and avg_ear is not None and mar is not None:
            _ear_buffer.append(avg_ear)
            _mar_buffer.append(mar)
            
            avg_ear = weighted_temporal_smoothing(avg_ear, _ear_buffer)
            mar = weighted_temporal_smoothing(mar, _mar_buffer)

        # Normalize values
        normalized_ear = normalize_value(avg_ear, _ear_lower, _ear_upper) if avg_ear is not None else None
        normalized_mar = normalize_value(mar, _mar_lower, _mar_upper) if mar is not None else None
        
        # Calculate confidence scores
        ear_confidence = 1.0 - abs(normalized_ear - 0.5) * 2 if normalized_ear is not None else 0.0
        mar_confidence = 1.0 - abs(normalized_mar - 0.5) * 2 if normalized_mar is not None else 0.0
        
        return {
            "right_ear": right_ear,
            "left_ear": left_ear,
            "avg_ear": avg_ear,
            "mar": mar,
            "normalized_ear": normalized_ear,
            "normalized_mar": normalized_mar,
            "ear_confidence": ear_confidence,
            "mar_confidence": mar_confidence
        }

    except Exception as e:
        logger.error(f"Error in get_facial_state: {e}")
        return {
            "right_ear": right_ear,
            "left_ear": left_ear,
            "avg_ear": None,
            "mar": None,
            "normalized_ear": None,
            "normalized_mar": None,
            "ear_confidence": 0.0,
            "mar_confidence": 0.0
        }
