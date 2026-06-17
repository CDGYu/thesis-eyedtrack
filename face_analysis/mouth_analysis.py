"""Mouth analysis module for driver monitoring"""

import numpy as np
import logging
from .ear_mar import mouth_aspect_ratio as mar_calculator

logger = logging.getLogger(__name__)

def mouth_aspect_ratio(mouth_points):
    """Calculate mouth aspect ratio from mouth landmark points"""
    return mar_calculator(mouth_points)

def get_mouth_state(mar, threshold_closed=0.35, threshold_open=0.65):
    """Determine mouth state from mouth aspect ratio"""
    try:
        if mar is None:
            return "UNKNOWN", 0.0
            
        if mar <= threshold_closed:
            confidence = 1.0 - (mar / threshold_closed)
            return "CLOSED", min(1.0, max(0.0, confidence))
        elif mar >= threshold_open:
            confidence = (mar - threshold_open) / (threshold_open * 0.5)  # Scale confidence
            return "WIDE OPEN", min(1.0, max(0.0, confidence))
        else:
            # Partially open - calculate confidence based on distance from thresholds
            mid_point = (threshold_closed + threshold_open) / 2
            if mar < mid_point:
                confidence = (mar - threshold_closed) / (mid_point - threshold_closed)
            else:
                confidence = (threshold_open - mar) / (threshold_open - mid_point)
            return "PARTIALLY OPEN", min(1.0, max(0.0, confidence))
            
    except Exception as e:
        logger.error(f"Error determining mouth state: {e}")
        return "UNKNOWN", 0.0 