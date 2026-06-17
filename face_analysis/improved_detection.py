"""
Improved face analysis module using dlib for more accurate behavior detection.
This module integrates the user's proven dlib-based detection logic.
"""

import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
import logging
import os
from typing import Tuple, Optional, List
from pathlib import Path
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Model paths
DEFAULT_MODELS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHAPE_PREDICTOR_PATH = os.path.join(DEFAULT_MODELS_DIR, 'shape_predictor_68_face_landmarks.dat')

class ImprovedFaceAnalyzer:
    """
    Improved face analyzer using dlib for accurate behavior detection.
    Based on proven dlib implementation with 68-point facial landmarks.
    """
    
    def __init__(self, config):
        """Initialize the improved face analyzer"""
        self.config = config
        
        # Initialize dlib detector and predictor
        self.detector = dlib.get_frontal_face_detector()
        
        # Load shape predictor
        if os.path.exists(SHAPE_PREDICTOR_PATH):
            self.predictor = dlib.shape_predictor(SHAPE_PREDICTOR_PATH)
            logger.info(f"✅ Shape predictor loaded from: {SHAPE_PREDICTOR_PATH}")
        else:
            logger.error(f"❌ Shape predictor not found at: {SHAPE_PREDICTOR_PATH}")
            raise FileNotFoundError(f"Shape predictor file not found: {SHAPE_PREDICTOR_PATH}")
        
        # Detection thresholds from config
        detection_config = config.get("detection", config.get("thresholds", {}))
        self.ear_threshold = detection_config.get("ear_threshold", 0.25)
        self.mar_threshold = detection_config.get("mar_threshold", 0.7)  # Fixed: should be higher for yawning
        self.yaw_threshold = detection_config.get("yaw_threshold", 25.0)
        self.pitch_threshold = detection_config.get("pitch_threshold", 15.0)
        
        logger.info(f"🎯 Improved detection thresholds: EAR={self.ear_threshold}, MAR={self.mar_threshold}, "
                   f"Yaw=±{self.yaw_threshold}°, Pitch=±{self.pitch_threshold}°")
        
    def detect_face(self, frame: np.ndarray) -> Optional[dlib.rectangle]:
        """
        Detect face using dlib detector
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            dlib.rectangle object or None if no face detected
        """
        try:
            if frame is None or frame.size == 0:
                logger.warning("⚠️ Invalid frame provided to detect_face")
                return None
                
            # Convert to grayscale for dlib
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.detector(gray, 0)
            
            if len(faces) > 0:
                # Return the first (largest) face
                face = faces[0]
                logger.debug(f"✅ Face detected: ({face.left()}, {face.top()}) - ({face.right()}, {face.bottom()})")
                return face
            else:
                logger.debug("❌ No face detected")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in face detection: {e}")
            return None
    
    def get_landmarks(self, frame: np.ndarray, face: dlib.rectangle) -> Optional[np.ndarray]:
        """
        Get 68-point facial landmarks using dlib
        
        Args:
            frame: Input frame (BGR format)
            face: dlib.rectangle face detection
            
        Returns:
            numpy array of shape (68, 2) with landmark coordinates or None
        """
        try:
            if frame is None or face is None:
                logger.warning("⚠️ Invalid frame or face provided to get_landmarks")
                return None
                
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Get landmarks
            shape = self.predictor(gray, face)
            
            # Convert to numpy array
            landmarks = np.array([[p.x, p.y] for p in shape.parts()])
            
            logger.debug(f"✅ Extracted {len(landmarks)} landmarks")
            return landmarks
            
        except Exception as e:
            logger.error(f"❌ Error extracting landmarks: {e}")
            return None
    
    def calculate_ear(self, eye_landmarks: np.ndarray) -> float:
        """
        Calculate Eye Aspect Ratio (EAR) for drowsiness detection
        
        Args:
            eye_landmarks: Array of 6 eye landmark points
            
        Returns:
            EAR value (float)
        """
        try:
            if len(eye_landmarks) != 6:
                logger.warning(f"⚠️ Expected 6 eye landmarks, got {len(eye_landmarks)}")
                return 0.0
            
            # Vertical eye landmarks
            A = dist.euclidean(eye_landmarks[1], eye_landmarks[5])  # Top-bottom left
            B = dist.euclidean(eye_landmarks[2], eye_landmarks[4])  # Top-bottom right
            
            # Horizontal eye landmark
            C = dist.euclidean(eye_landmarks[0], eye_landmarks[3])  # Left-right corners
            
            if C == 0:
                logger.warning("⚠️ Horizontal eye distance is zero")
                return 0.0
            
            # Calculate EAR
            ear = (A + B) / (2.0 * C)
            
            logger.debug(f"📊 EAR calculation: A={A:.3f}, B={B:.3f}, C={C:.3f}, EAR={ear:.4f}")
            return ear
            
        except Exception as e:
            logger.error(f"❌ Error calculating EAR: {e}")
            return 0.0
    
    def calculate_mar(self, mouth_landmarks: np.ndarray) -> float:
        """
        Calculate Mouth Aspect Ratio (MAR) for yawning detection
        
        Args:
            mouth_landmarks: Array of 20 mouth landmark points (indices 48-67)
            
        Returns:
            MAR value (float)
        """
        try:
            if len(mouth_landmarks) != 20:
                logger.warning(f"⚠️ Expected 20 mouth landmarks, got {len(mouth_landmarks)}")
                return 0.0
            
            # Vertical mouth landmarks (using indices relative to mouth landmarks array)
            A = dist.euclidean(mouth_landmarks[13], mouth_landmarks[19])  # Top-bottom center
            B = dist.euclidean(mouth_landmarks[14], mouth_landmarks[18])  # Top-bottom left
            C = dist.euclidean(mouth_landmarks[15], mouth_landmarks[17])  # Top-bottom right
            
            # Horizontal mouth landmark
            D = dist.euclidean(mouth_landmarks[12], mouth_landmarks[16])  # Left-right corners
            
            if D == 0:
                logger.warning("⚠️ Horizontal mouth distance is zero")
                return 0.0
            
            # Calculate MAR
            mar = (A + B + C) / (3.0 * D)
            
            logger.debug(f"📊 MAR calculation: A={A:.3f}, B={B:.3f}, C={C:.3f}, D={D:.3f}, MAR={mar:.4f}")
            return mar
            
        except Exception as e:
            logger.error(f"❌ Error calculating MAR: {e}")
            return 0.0
    
    def calculate_head_pose(self, landmarks: np.ndarray, frame_shape: Tuple[int, int]) -> Tuple[float, float]:
        """
        Calculate head pose (yaw, pitch) using improved geometric approach
        Enhanced sensitivity for extreme head turns
        
        Args:
            landmarks: 68-point facial landmarks
            frame_shape: (height, width) of the frame
            
        Returns:
            Tuple of (yaw, pitch) in degrees
        """
        try:
            # Validate inputs
            if landmarks is None or landmarks.shape != (68, 2):
                logger.debug(f"Head pose: invalid landmarks shape: {landmarks.shape if landmarks is not None else None}")
                return 0.0, 0.0
            
            height, width = frame_shape
            if height <= 0 or width <= 0:
                logger.debug(f"Head pose: invalid frame dimensions: {width}x{height}")
                return 0.0, 0.0
            
            landmarks = np.array(landmarks, dtype=np.float64)
            
            # Check for invalid values
            if np.any(np.isnan(landmarks)) or np.any(np.isinf(landmarks)):
                logger.debug("Head pose: landmarks contain invalid values")
                return 0.0, 0.0
            
            # Extract key facial landmarks
            nose_tip = landmarks[30]        # Nose tip
            nose_bridge = landmarks[27]     # Nose bridge
            chin = landmarks[8]             # Chin
            left_eye_outer = landmarks[36]  # Left eye outer corner
            right_eye_outer = landmarks[45] # Right eye outer corner
            left_eye_inner = landmarks[39]  # Left eye inner corner
            right_eye_inner = landmarks[42] # Right eye inner corner
            left_mouth = landmarks[48]      # Left mouth corner
            right_mouth = landmarks[54]     # Right mouth corner
            left_jaw = landmarks[0]         # Left jawline
            right_jaw = landmarks[16]       # Right jawline
            
            # Calculate face center
            face_center_x = (left_eye_outer[0] + right_eye_outer[0]) / 2.0
            face_center_y = (left_eye_outer[1] + right_eye_outer[1]) / 2.0
            
            # SIMPLIFIED AND MORE AGGRESSIVE YAW CALCULATION
            # Focus on the most reliable indicators with much higher sensitivity
            
            # Primary cue: Nose displacement from eye center line
            eye_center_x = (left_eye_outer[0] + right_eye_outer[0]) / 2.0
            eye_distance = np.abs(right_eye_outer[0] - left_eye_outer[0])
            
            nose_displacement = 0.0
            if eye_distance > 0:
                nose_displacement = (nose_tip[0] - eye_center_x) / eye_distance
            
            # Secondary cue: Eye asymmetry (more aggressive calculation)
            left_eye_width = np.abs(left_eye_outer[0] - left_eye_inner[0])
            right_eye_width = np.abs(right_eye_outer[0] - right_eye_inner[0])
            
            eye_asymmetry = 0.0
            if left_eye_width + right_eye_width > 0:
                eye_asymmetry = (right_eye_width - left_eye_width) / (left_eye_width + right_eye_width)
            
            # Tertiary cue: Mouth displacement
            mouth_center_x = (left_mouth[0] + right_mouth[0]) / 2.0
            mouth_displacement = 0.0
            if eye_distance > 0:
                mouth_displacement = (mouth_center_x - eye_center_x) / eye_distance
            
            # Debug logging to see individual components
            logger.debug(f"Yaw components: nose_disp={nose_displacement:.4f}, eye_asym={eye_asymmetry:.4f}, mouth_disp={mouth_displacement:.4f}")
            
            # Simplified combination - focus more on direct measurements
            # Use higher weights and more aggressive scaling
            primary_displacement = nose_displacement * 0.6 + mouth_displacement * 0.4
            secondary_boost = eye_asymmetry * 0.3  # Additional boost from eye asymmetry
            
            total_displacement = primary_displacement + secondary_boost
            
            # MUCH MORE AGGRESSIVE SCALING
            # The issue is that facial displacements are inherently small (0.05-0.2 range)
            # We need to amplify these significantly for driver monitoring sensitivity
            
            abs_displacement = abs(total_displacement)
            
            if abs_displacement < 0.05:
                # Very small movements - minimal yaw
                yaw_magnitude = abs_displacement * 200.0  # 10x more aggressive than before
            elif abs_displacement < 0.15:
                # Moderate movements - linear scaling with high sensitivity  
                yaw_magnitude = 10.0 + (abs_displacement - 0.05) * 400.0  # Very aggressive
            else:
                # Large movements - extreme yaw values
                yaw_magnitude = 50.0 + (abs_displacement - 0.15) * 800.0  # Maximum sensitivity
            
            # Apply sign
            yaw = yaw_magnitude if total_displacement >= 0 else -yaw_magnitude
            
            logger.debug(f"Yaw calculation: total_disp={total_displacement:.4f}, abs_disp={abs_displacement:.4f}, final_yaw={yaw:.2f}°")
            
            # Method 2: Calculate pitch using nose-chin relationship (unchanged - working well)
            nose_chin_vertical = chin[1] - nose_tip[1]
            eye_nose_vertical = nose_tip[1] - face_center_y
            
            if nose_chin_vertical > 0:
                # Calculate pitch based on vertical proportions
                vertical_ratio = eye_nose_vertical / nose_chin_vertical
                # Convert to degrees (empirically tuned)
                # Positive pitch = looking up, negative pitch = looking down
                pitch = (vertical_ratio - 0.4) * 60.0  # Scale and offset for normal forward-looking pose
            else:
                pitch = 0.0
            
            # Apply reasonable bounds (wider range for yaw)
            yaw = np.clip(yaw, -90.0, 90.0)
            pitch = np.clip(pitch, -60.0, 60.0)
            
            # Final validation
            if np.isnan(yaw) or np.isnan(pitch) or np.isinf(yaw) or np.isinf(pitch):
                logger.debug("Head pose: invalid final values")
                return 0.0, 0.0
            
            logger.debug(f"Head pose calculated: yaw={yaw:.2f}° (displacement={total_displacement:.3f}), pitch={pitch:.2f}°")
            return float(yaw), float(pitch)
            
        except Exception as e:
            logger.error(f"Head pose calculation failed: {e}")
            return 0.0, 0.0
    
    def analyze_frame(self, frame: np.ndarray) -> dict:
        """
        Comprehensive frame analysis for behavior detection
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Dictionary with analysis results
        """
        result = {
            "success": False,
            "face_detected": False,
            "landmarks_detected": False,
            "metrics": {
                "ear": 0.0,
                "mar": 0.0,
                "yaw": 0.0,
                "pitch": 0.0
            },
            "behaviors": {
                "is_drowsy": False,
                "is_yawning": False,
                "is_distracted": False
            },
            "face_box": None,
            "debug_info": {}
        }
        
        try:
            if frame is None or frame.size == 0:
                result["debug_info"]["error"] = "Invalid frame"
                return result
            
            # Step 1: Detect face
            face = self.detect_face(frame)
            if face is None:
                result["debug_info"]["error"] = "No face detected"
                return result

            result["face_detected"] = True
            result["face_box"] = [face.left(), face.top(), face.width(), face.height()]
            
            # Step 2: Get landmarks
            landmarks = self.get_landmarks(frame, face)
            if landmarks is None:
                result["debug_info"]["error"] = "No landmarks detected"
                return result

            result["landmarks_detected"] = True
            
            # Step 3: Calculate EAR (Eye Aspect Ratio)
            left_eye = landmarks[42:48]   # Left eye landmarks (42-47)
            right_eye = landmarks[36:42]  # Right eye landmarks (36-41)
            
            left_ear = self.calculate_ear(left_eye)
            right_ear = self.calculate_ear(right_eye)
            ear = (left_ear + right_ear) / 2.0
            
            result["metrics"]["ear"] = ear
            result["debug_info"]["left_ear"] = left_ear
            result["debug_info"]["right_ear"] = right_ear
            
            # Step 4: Calculate MAR (Mouth Aspect Ratio)
            mouth = landmarks[48:68]  # Mouth landmarks (48-67)
            mar = self.calculate_mar(mouth)
            result["metrics"]["mar"] = mar
            
            # Step 5: Calculate head pose
            yaw, pitch = self.calculate_head_pose(landmarks, (frame.shape[0], frame.shape[1]))
            result["metrics"]["yaw"] = yaw
            result["metrics"]["pitch"] = pitch
            
            # Step 6: Behavior detection
            # Drowsiness: EAR below threshold
            if ear < self.ear_threshold:
                result["behaviors"]["is_drowsy"] = True
                result["debug_info"]["drowsy_reason"] = f"EAR {ear:.4f} < {self.ear_threshold}"
            
            # Yawning: MAR above threshold (CORRECTED LOGIC)
            if mar > self.mar_threshold:
                result["behaviors"]["is_yawning"] = True
                result["debug_info"]["yawning_reason"] = f"MAR {mar:.4f} > {self.mar_threshold}"
            
            # Distraction: Head pose beyond thresholds
            if abs(yaw) > self.yaw_threshold or abs(pitch) > self.pitch_threshold:
                result["behaviors"]["is_distracted"] = True
                result["debug_info"]["distraction_reason"] = f"Yaw {yaw:.1f} or Pitch {pitch:.1f} beyond thresholds"
            
            result["success"] = True
            
            # Debug logging
            logger.info(f"Frame Analysis: EAR={ear:.4f}, MAR={mar:.4f}, Yaw={yaw:.1f}, Pitch={pitch:.1f}")
            
            behaviors_detected = []
            if result["behaviors"]["is_drowsy"]:
                behaviors_detected.append("DROWSY")
            if result["behaviors"]["is_yawning"]:
                behaviors_detected.append("YAWNING")
            if result["behaviors"]["is_distracted"]:
                behaviors_detected.append("DISTRACTED")
            
            if behaviors_detected:
                logger.warning(f"BEHAVIORS DETECTED: {', '.join(behaviors_detected)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in frame analysis: {e}")
            result["debug_info"]["error"] = str(e)
            return result
    
    def draw_debug_info(self, frame: np.ndarray, result: dict) -> np.ndarray:
        """
        Draw debug information on frame
        
        Args:
            frame: Input frame
            result: Analysis result from analyze_frame
            
        Returns:
            Frame with debug information drawn
        """
        try:
            if not result["success"]:
                cv2.putText(frame, f"ERROR: {result['debug_info'].get('error', 'Unknown')}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                return frame
            
            # Draw face box
            if result["face_box"]:
                x, y, w, h = result["face_box"]
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Draw metrics
            metrics = result["metrics"]
            y_offset = 30
            
            # EAR
            ear_color = (0, 0, 255) if result["behaviors"]["is_drowsy"] else (255, 255, 255)
            cv2.putText(frame, f"EAR: {metrics['ear']:.4f} (thresh: {self.ear_threshold})", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ear_color, 2)
            y_offset += 25
            
            # MAR
            mar_color = (0, 165, 255) if result["behaviors"]["is_yawning"] else (255, 255, 255)
            cv2.putText(frame, f"MAR: {metrics['mar']:.4f} (thresh: {self.mar_threshold})", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mar_color, 2)
            y_offset += 25
            
            # Head pose
            pose_color = (255, 0, 0) if result["behaviors"]["is_distracted"] else (255, 255, 255)
            cv2.putText(frame, f"Yaw: {metrics['yaw']:+5.1f}° (thresh: ±{self.yaw_threshold}°)", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, pose_color, 2)
            y_offset += 25
            cv2.putText(frame, f"Pitch: {metrics['pitch']:+5.1f}° (thresh: ±{self.pitch_threshold}°)", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, pose_color, 2)
            
            # Draw behavior alerts
            y_offset = frame.shape[0] - 100
            if result["behaviors"]["is_drowsy"]:
                cv2.putText(frame, "DROWSINESS ALERT", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                y_offset += 30
            if result["behaviors"]["is_yawning"]:
                cv2.putText(frame, "YAWNING ALERT", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                y_offset += 30
            if result["behaviors"]["is_distracted"]:
                cv2.putText(frame, "DISTRACTION ALERT", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
            
            return frame
            
        except Exception as e:
            logger.error(f"❌ Error drawing debug info: {e}")
            return frame 