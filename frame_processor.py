"""
Frame processor module for driver monitoring system.
Uses only the ImprovedFaceAnalyzer for comprehensive behavior detection.
"""

import cv2
import numpy as np
import time
import logging
import threading
import queue
import os
import traceback
from typing import Dict, Any, Optional, Tuple, List, Deque
from collections import deque
import concurrent.futures
from pathlib import Path
from datetime import datetime

# Import the standalone improved detection module
from face_analysis.improved_detection import ImprovedFaceAnalyzer
from video_recorder import VideoRecorder
from behavior_categories import BEHAVIOR_CATEGORIES
from event_logger import log_event, get_event_type

logger = logging.getLogger(__name__)

def normalize_angle(angle):
    """Normalize angle to [-180, 180] range"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle

class OptimizedFrameProcessor:
    def __init__(self, config):
        """Initialize the frame processor with configuration"""
        self.config = config
        
        # Initialize the standalone ImprovedFaceAnalyzer (only detection method)
        try:
            self.standalone_analyzer = ImprovedFaceAnalyzer(config)
            logger.info("✅ ImprovedFaceAnalyzer initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ImprovedFaceAnalyzer: {e}")
            raise
        
        # Initialize state tracking with configurable thresholds
        self._drowsy_frames = 0
        self._yawn_frames = 0
        self._distraction_frames = 0
        self._last_behavior = BEHAVIOR_CATEGORIES["NO_BEHAVIOR"]
        
        # Get thresholds from config - use new detection section with proper fallbacks
        detection_config = config.get("detection", {})
        
        # FIXED: Use proper fallback values that actually exist or provide defaults
        self.ear_threshold = detection_config.get("ear_threshold", 0.25)  # Default EAR threshold
        self.mar_threshold = detection_config.get("mar_threshold", 0.7)   # Default MAR threshold
        self.drowsy_frames_threshold = detection_config.get("drowsy_frames_threshold", config.get("thresholds", {}).get("drowsy_frames", 8))
        self.yawn_frames_threshold = detection_config.get("yawn_frames_threshold", config.get("thresholds", {}).get("yawn_frames", 3))
        self.distraction_frames_threshold = detection_config.get("distraction_frames_threshold", config.get("thresholds", {}).get("distraction_frames", 6))
        
        # Head pose thresholds with proper fallbacks
        self.yaw_threshold = detection_config.get("yaw_threshold", 25)    # Default yaw threshold
        self.pitch_threshold = detection_config.get("pitch_threshold", 15) # Default pitch threshold
        
        # Performance optimizations
        self.use_threading = config["performance"]["use_threading"]
        self.max_workers = config["performance"]["max_workers"]
        self.resize_factor = config["performance"]["resize_factor"]
        self.use_roi = config["performance"]["use_roi"]
        self.roi_margin = config["performance"]["roi_margin"]
        
        if self.use_threading:
            self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        
        # ROI tracking
        self.last_face_roi = None
        self.tracking_failures = 0
        self.max_tracking_failures = config["face_detection"]["max_tracking_failures"]
        
        # Initialize video recorder
        video_output_dir = os.path.join(config["logging"]["log_dir"], "videos")
        self.video_recorder = VideoRecorder(video_output_dir)
        
        # Temporal smoothing
        self.ear_history = deque(maxlen=5)
        self.mar_history = deque(maxlen=5)
        self.head_pose_history = deque(maxlen=5)
        self.smoothing_alpha = config["head_pose"]["smoothing_alpha"]
        
        # Event logging
        self.log_dir = Path(config["logging"]["log_dir"])
        
        logger.info(f"Using detection thresholds: EAR={self.ear_threshold}, MAR={self.mar_threshold}, "
                   f"Yaw={self.yaw_threshold}, Pitch={self.pitch_threshold}, "
                   f"Frames: drowsy={self.drowsy_frames_threshold}, yawn={self.yawn_frames_threshold}, distraction={self.distraction_frames_threshold}")
        
        logger.info("Optimized frame processor initialized")
    
    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process a single frame using ImprovedFaceAnalyzer"""
        try:
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                return {
                    "success": False,
                    "error": "Invalid input frame",
                    "face_box": None,
                    "behavior_category": {
                        "is_drowsy": False,
                        "is_yawning": False,
                        "is_distracted": False
                    },
                    "behavior_confidence": 0.0,
                    "metrics": {
                        "ear": 0.0,
                        "mar": 0.0,
                        "head_pose": None
                    },
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                }

            # Preprocess frame
            processed_frame = self.preprocess_frame(frame)
            
            # Use ImprovedFaceAnalyzer for complete analysis
            logger.debug("🎯 Using ImprovedFaceAnalyzer for frame analysis")
            analysis_result = self.standalone_analyzer.analyze_frame(processed_frame)
            
            if analysis_result["success"]:
                # Extract metrics
                ear = analysis_result["metrics"]["ear"]
                mar = analysis_result["metrics"]["mar"]
                yaw = analysis_result["metrics"]["yaw"]
                pitch = analysis_result["metrics"]["pitch"]
                head_pose = [yaw, pitch, 0.0]
                
                # Extract behaviors (ImprovedFaceAnalyzer already handles thresholds)
                is_drowsy = analysis_result["behaviors"]["is_drowsy"]
                is_yawning = analysis_result["behaviors"]["is_yawning"]
                is_distracted = analysis_result["behaviors"]["is_distracted"]
                
                logger.info(f"✅ Analysis: EAR={ear:.4f}, MAR={mar:.4f}, Yaw={yaw:.2f}°, Pitch={pitch:.2f}°")
                
                if is_drowsy or is_yawning or is_distracted:
                    behaviors = []
                    if is_drowsy: behaviors.append("DROWSY")
                    if is_yawning: behaviors.append("YAWNING") 
                    if is_distracted: behaviors.append("DISTRACTED")
                    logger.warning(f"⚠️ BEHAVIORS DETECTED: {', '.join(behaviors)}")
                
                # Apply frame counting for consistent behavior detection
                if is_drowsy:
                    self._drowsy_frames += 1
                else:
                    self._drowsy_frames = 0
                    
                if is_yawning:
                    self._yawn_frames += 1
                else:
                    self._yawn_frames = 0
                    
                if is_distracted:
                    self._distraction_frames += 1
                else:
                    self._distraction_frames = 0
                
                # Determine final behavior based on frame thresholds
                final_drowsy = self._drowsy_frames >= self.drowsy_frames_threshold
                final_yawning = self._yawn_frames >= self.yawn_frames_threshold
                final_distracted = self._distraction_frames >= self.distraction_frames_threshold
                
                # Calculate confidence based on consistency
                confidence = 0.0
                if final_drowsy or final_yawning or final_distracted:
                    confidence = 0.8  # High confidence when behavior persists
                elif is_drowsy or is_yawning or is_distracted:
                    confidence = 0.5  # Medium confidence for single frame detection
                
                result = {
                    "success": True,
                    "face_box": analysis_result["face_box"],
                    "behavior_category": {
                        "is_drowsy": final_drowsy,
                        "is_yawning": final_yawning,
                        "is_distracted": final_distracted
                    },
                    "behavior_confidence": confidence,
                    "metrics": {
                        "ear": ear,
                        "mar": mar,
                        "head_pose": head_pose
                    },
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                }
                
            else:
                logger.warning(f"❌ Face analysis failed: {analysis_result.get('debug_info', {}).get('error', 'Unknown error')}")
                result = {
                    "success": False,
                    "error": "Face analysis failed",
                    "face_box": None,
                    "behavior_category": {
                        "is_drowsy": False,
                        "is_yawning": False,
                        "is_distracted": False
                    },
                    "behavior_confidence": 0.0,
                    "metrics": {
                        "ear": 0.0,
                        "mar": 0.0,
                        "head_pose": None
                    },
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                }
            
            # Log all events (not just when behaviors are detected) for continuous monitoring
            try:
                event_type = get_event_type(result)
                log_event(self.log_dir, event_type, result)
            except Exception as e:
                logger.error(f"Error logging event: {str(e)}")

            return result
            
        except Exception as e:
            logger.error(f"❌ Error in frame processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "face_box": None,
                "behavior_category": {
                    "is_drowsy": False,
                    "is_yawning": False,
                    "is_distracted": False
                },
                "behavior_confidence": 0.0,
                "metrics": {
                    "ear": 0.0,
                    "mar": 0.0,
                    "head_pose": None
                },
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            }
        
    def preprocess_frame(self, frame):
        """Preprocess frame for better detection"""
        if self.resize_factor != 1.0:
            frame = cv2.resize(frame, None, fx=self.resize_factor, fy=self.resize_factor)
        
        if self.config["clahe"]["enabled"]:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            frame = cv2.cvtColor(cv2.merge((cl,a,b)), cv2.COLOR_LAB2BGR)
            
        return frame
        
    def get_face_roi(self, frame, face_box):
        """Get region of interest around face"""
        if face_box is None:
            return None
            
        x, y, w, h = face_box
        margin = self.roi_margin
        
        # Add margin around face
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(frame.shape[1], x + w + margin)
        y2 = min(frame.shape[0], y + h + margin)
        
        return (x1, y1, x2-x1, y2-y1)

    def run(self):
        """Run the frame processor (if needed for standalone operation)"""
        logger.info("Frame processor running...")
        # Implementation would depend on specific requirements
        pass 