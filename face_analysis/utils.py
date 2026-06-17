"""Utility functions for face analysis"""

import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)

def weighted_temporal_smoothing(current_value, history, alpha=0.3):
    """Apply weighted temporal smoothing to a value using history"""
    try:
        if not history:
            return current_value
            
        # Convert history to numpy array
        values = np.array(history)
        
        # Calculate weights (more recent values have higher weights)
        weights = np.exp(alpha * np.arange(len(values)))
        weights = weights / np.sum(weights)
        
        # Calculate weighted average
        smoothed_value = np.sum(values * weights)
        
        return float(smoothed_value)
        
    except Exception as e:
        logger.error(f"Error in temporal smoothing: {e}")
        return current_value

def normalize_landmarks(landmarks, frame_size):
    """Normalize landmark coordinates to [0,1] range"""
    try:
        if landmarks is None:
            return None
            
        h, w = frame_size
        normalized = landmarks.copy()
        normalized[:, 0] = normalized[:, 0] / w
        normalized[:, 1] = normalized[:, 1] / h
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing landmarks: {e}")
        return None

def denormalize_landmarks(landmarks, frame_size):
    """Convert normalized landmarks back to pixel coordinates"""
    try:
        if landmarks is None:
            return None
            
        h, w = frame_size
        denormalized = landmarks.copy()
        denormalized[:, 0] = denormalized[:, 0] * w
        denormalized[:, 1] = denormalized[:, 1] * h
        return denormalized.astype(np.int32)
        
    except Exception as e:
        logger.error(f"Error denormalizing landmarks: {e}")
        return None 