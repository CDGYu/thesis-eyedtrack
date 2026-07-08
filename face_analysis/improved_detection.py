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

        # Cache the last frame rotation that found a face (phone frames arrive rotated);
        # steady-state detection then tries that orientation first. _dbg_count throttles
        # the debug-frame dump used to inspect exactly what the phone sends.
        self._last_rot_idx = 0
        self._dbg_count = 0

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

    def _oriented_face(self, frame: np.ndarray):
        """
        Orientation-robust face detection. Phone frames often arrive rotated 90/180/270,
        and dlib's frontal detector only finds UPRIGHT faces — the #1 reason a mobile
        client sees "no face detected". Try each rotation (starting with the last that
        worked, for speed), upsampling once for smaller/farther faces, and return the
        UPRIGHT (oriented_frame, face) for the first hit so all downstream landmark/
        EAR/MAR/head-pose math runs on a correctly-oriented image.
        """
        rots = [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]
        order = [self._last_rot_idx] + [i for i in range(4) if i != self._last_rot_idx]
        for idx in order:
            oriented = frame if rots[idx] is None else cv2.rotate(frame, rots[idx])
            try:
                gray = cv2.cvtColor(oriented, cv2.COLOR_BGR2GRAY)
                faces = self.detector(gray, 1)  # upsample=1 → detect smaller faces
            except Exception as e:
                logger.error(f"❌ Error detecting at rotation {idx}: {e}")
                continue
            if len(faces) > 0:
                self._last_rot_idx = idx
                if idx != 0:
                    logger.debug(f"✅ Face found after rotating (rot idx {idx})")
                return oriented, faces[0]
        return frame, None

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
        Estimate head pose (yaw, pitch) in degrees with cv2.solvePnP on six facial landmarks.

        yaw  = left/right head rotation (drives distraction detection)
        pitch = up/down head tilt
        A forward-facing head returns values near 0; results are clamped to a sane range.

        Args:
            landmarks: 68-point facial landmarks (pixel coordinates)
            frame_shape: (height, width) of the frame

        Returns:
            Tuple of (yaw, pitch) in degrees
        """
        try:
            pts = np.asarray(landmarks, dtype=np.float64)
            if pts.shape != (68, 2) or not np.all(np.isfinite(pts)):
                logger.debug("Head pose: invalid landmarks")
                return 0.0, 0.0

            height, width = frame_shape
            if height <= 0 or width <= 0:
                logger.debug(f"Head pose: invalid frame dimensions: {width}x{height}")
                return 0.0, 0.0

            # Generic 3D head model (mm) for the six landmarks below.
            model_points = np.array([
                (0.0, 0.0, 0.0),           # nose tip          (idx 30)
                (0.0, -330.0, -65.0),      # chin              (idx 8)
                (-225.0, 170.0, -135.0),   # left eye, l corner (idx 36)
                (225.0, 170.0, -135.0),    # right eye, r corner(idx 45)
                (-150.0, -150.0, -125.0),  # left mouth corner (idx 48)
                (150.0, -150.0, -125.0),   # right mouth corner(idx 54)
            ], dtype=np.float64)
            image_points = np.array(
                [pts[30], pts[8], pts[36], pts[45], pts[48], pts[54]], dtype=np.float64
            )

            # Approximate pinhole camera (focal length ~ image width, principal point at center).
            focal = float(width)
            camera_matrix = np.array([
                [focal, 0.0, width / 2.0],
                [0.0, focal, height / 2.0],
                [0.0, 0.0, 1.0],
            ], dtype=np.float64)
            dist_coeffs = np.zeros((4, 1))

            ok, rotation_vec, _ = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            if not ok:
                return 0.0, 0.0

            # Rotation matrix -> Euler angles (degrees).
            rmat, _ = cv2.Rodrigues(rotation_vec)
            sy = float(np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2))
            if sy > 1e-6:
                pitch = np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2]))
            else:
                pitch = np.degrees(np.arctan2(-rmat[1, 2], rmat[1, 1]))
            yaw = np.degrees(np.arctan2(-rmat[2, 0], sy))

            # The 3D model is Y-up while image coords are Y-down, so a forward-facing head
            # lands near +/-180 on pitch. Fold into [-90, 90] so "looking straight" reads ~0.
            if pitch > 90.0:
                pitch -= 180.0
            elif pitch < -90.0:
                pitch += 180.0

            if not (np.isfinite(yaw) and np.isfinite(pitch)):
                return 0.0, 0.0

            yaw = float(np.clip(yaw, -90.0, 90.0))
            pitch = float(np.clip(pitch, -90.0, 90.0))
            logger.debug(f"Head pose (solvePnP): yaw={yaw:.2f}°, pitch={pitch:.2f}°")
            return yaw, pitch

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
            
            # Step 1: Detect face — orientation-robust (rotate the frame to upright).
            frame, face = self._oriented_face(frame)
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