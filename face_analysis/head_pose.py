'''
head_pose.py

Enhanced Head Pose Estimation module for real-time driver attention monitoring.
Provides utilities to estimate head pose (pitch, yaw, roll) from 2D facial landmarks
and draw 3D axes on frames for visualization.
'''

import cv2
import numpy as np
from typing import Tuple, Optional, Sequence, Union, List, Deque
from dataclasses import dataclass
import logging
from collections import deque

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Default 3D model points (mm) for solvePnP
DEFAULT_MODEL_POINTS = np.array([
    (0.0,    0.0,    0.0),     # Nose tip
    (0.0,  -330.0,  -65.0),    # Chin
    (-225.0, 170.0, -135.0),   # Left eye left corner
    (225.0,  170.0, -135.0),   # Right eye right corner
    (-150.0,-150.0, -125.0),   # Left mouth corner
    (150.0, -150.0, -125.0)    # Right mouth corner
], dtype=np.float64)
# Corresponding landmark indices
DEFAULT_LANDMARK_IDX = [30, 8, 36, 45, 48, 54]

# Default axis colors (BGR)
AXIS_COLORS = {
    'x': (0, 0, 255),  # Red
    'y': (0, 255, 0),  # Green
    'z': (255, 0, 0),  # Blue
}

@dataclass(frozen=True)
class HeadPoseResult:
    rotation_vector: np.ndarray    # (3,1)
    translation_vector: np.ndarray  # (3,1)
    euler_angles: Tuple[float, float, float]  # (pitch, yaw, roll) in degrees
    confidence: float = 1.0  # Confidence score (0.0 to 1.0)

def stabilize_angles(new_angles: Tuple[float, float, float], 
                    angle_history: Deque[Tuple[float, float, float]],
                    window_size: int = 5,
                    alpha: float = 0.3) -> Tuple[float, float, float]:
    """
    Stabilize head pose angles using weighted smoothing.
    
    Args:
        new_angles: New (pitch, yaw, roll) angles
        angle_history: History of previous angles
        window_size: Maximum size of history buffer
        alpha: Weight factor for new angles (0.3 provides good balance)
        
    Returns:
        Stabilized (pitch, yaw, roll) angles
    """
    if not angle_history:
        return new_angles
        
    # Use weighted smoothing
    pitch, yaw, roll = new_angles
    prev_pitch, prev_yaw, prev_roll = angle_history[-1]
    
    # Apply smoothing to each angle
    smoothed_pitch = alpha * pitch + (1 - alpha) * prev_pitch
    smoothed_yaw = alpha * yaw + (1 - alpha) * prev_yaw
    smoothed_roll = alpha * roll + (1 - alpha) * prev_roll
    
    return (smoothed_pitch, smoothed_yaw, smoothed_roll)

class HeadPoseEstimator:
    """
    Estimates head pose from 2D landmarks using solvePnP and provides visualization utilities.
    """

    def __init__(self, config):
        """Initialize the head pose estimator"""
        # Get frame size from config
        self.frame_width = config["camera"]["width"]
        self.frame_height = config["camera"]["height"]
        
        # Initialize 3D model points
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ]) / 4.5

        # Camera internals
        self.camera_matrix = np.array([
            [self.frame_width, 0, self.frame_width/2],
            [0, self.frame_width, self.frame_height/2],
            [0, 0, 1]
        ], dtype=np.float32)

        # Assuming no lens distortion
        self.dist_coeffs = np.zeros((4, 1))

        # Initialize Kalman filter if enabled
        self.use_kalman = config.get("head_pose", {}).get("use_kalman_filter", False)
        if self.use_kalman:
            self.kalman = cv2.KalmanFilter(6, 3)  # 6 states (x,y,z,pitch,yaw,roll), 3 measurements
            self.kalman.measurementMatrix = np.array([[1, 0, 0, 0, 0, 0],
                                                     [0, 1, 0, 0, 0, 0],
                                                     [0, 0, 1, 0, 0, 0]], np.float32)
            self.kalman.transitionMatrix = np.eye(6, dtype=np.float32)
            self.kalman.processNoiseCov = np.eye(6, dtype=np.float32) * 0.03
            
        # Initialize stabilization window
        self.stabilization_window = config.get("head_pose", {}).get("stabilization_window", 5)
        self.pose_history = []
        
    def estimate(self, frame, landmarks):
        """Estimate head pose from facial landmarks"""
        try:
            if landmarks is None:
                return None
                
            # Get image points from landmarks
            image_points = np.array([
                landmarks[30],    # Nose tip
                landmarks[8],     # Chin
                landmarks[36],    # Left eye left corner
                landmarks[45],    # Right eye right corner
                landmarks[48],    # Left mouth corner
                landmarks[54]     # Right mouth corner
            ], dtype=np.float32)
            
            # Solve PnP
            success, rotation_vec, translation_vec = cv2.solvePnP(
                self.model_points,
                image_points,
                self.camera_matrix,
                self.dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if not success:
                return None
                
            # Convert rotation vector to Euler angles
            rotation_mat, _ = cv2.Rodrigues(rotation_vec)
            pose_mat = cv2.hconcat([rotation_mat, translation_vec])
            _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(pose_mat)
            
            pitch, yaw, roll = [float(angle) for angle in euler_angles]
            
            # Normalize angles to reasonable ranges [-180, 180]
            def normalize_angle(angle):
                while angle > 180:
                    angle -= 360
                while angle < -180:
                    angle += 360
                return angle
                
            yaw = normalize_angle(yaw)
            pitch = normalize_angle(pitch)
            roll = normalize_angle(roll)
            
            # Apply Kalman filtering if enabled
            if self.use_kalman:
                measurement = np.array([[pitch], [yaw], [roll]], np.float32)
                self.kalman.correct(measurement)
                prediction = self.kalman.predict()
                pitch, yaw, roll = prediction[:3, 0]
                
            # Apply stabilization
            current_pose = (pitch, yaw, roll)
            self.pose_history.append(current_pose)
            if len(self.pose_history) > self.stabilization_window:
                self.pose_history.pop(0)
                
            # Calculate stabilized pose
            stabilized_pose = np.mean(self.pose_history, axis=0)
            
            return stabilized_pose
            
        except Exception as e:
            logger.error(f"Error estimating head pose: {e}")
            return None

    def draw_axes(
        self, 
        frame: np.ndarray, 
        head_pose_result: HeadPoseResult, 
        nose_tip: Union[Tuple[int, int], 'dlib.point'], 
        scale: int = 50, 
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw 3D axes on the face to visualize head orientation.
        
        Parameters:
        -----------
        frame : numpy.ndarray
            Input image to draw on
        head_pose_result : HeadPoseResult
            Head pose estimation result
        nose_tip : tuple or dlib.point
            (x, y) coordinates of the nose tip
        scale : int, optional
            Scale factor for the axes
        thickness : int, optional
            Line thickness
            
        Returns:
        --------
        numpy.ndarray
            Image with axes drawn
        """
        try:
            # Make sure nose_tip is a tuple of integers
            if not isinstance(nose_tip, tuple) and hasattr(nose_tip, 'x') and hasattr(nose_tip, 'y'):
                # Convert dlib point to tuple
                nose_tip = (int(nose_tip.x), int(nose_tip.y))
            else:
                # Ensure values are integers
                nose_tip = (int(nose_tip[0]), int(nose_tip[1]))
            
            # Get rotation and translation vectors
            rotation_vector = head_pose_result.rotation_vector
            translation_vector = head_pose_result.translation_vector
            
            # Define axis points in 3D space
            axis_points = np.float32([
                [0, 0, 0],      # Origin
                [scale, 0, 0],  # X-axis
                [0, scale, 0],  # Y-axis
                [0, 0, scale]   # Z-axis
            ])
            
            # Project 3D points to image plane
            imgpts, jac = cv2.projectPoints(
                axis_points, 
                rotation_vector, 
                translation_vector, 
                self.camera_matrix, 
                self.dist_coeffs
            )
            
            # Convert to integer points
            imgpts = [tuple(map(int, point[0])) for point in imgpts]
            
            # Draw axes using the AXIS_COLORS dictionary
            frame = cv2.line(frame, nose_tip, imgpts[1], AXIS_COLORS['x'], thickness)  # X-axis (red)
            frame = cv2.line(frame, nose_tip, imgpts[2], AXIS_COLORS['y'], thickness)  # Y-axis (green)
            frame = cv2.line(frame, nose_tip, imgpts[3], AXIS_COLORS['z'], thickness)  # Z-axis (blue)
            
            return frame
        except Exception as e:
            logger.error(f"Error in drawing axes: {e}")
            return frame

    def draw_pose_info(
        self, 
        frame: np.ndarray, 
        head_pose_result: HeadPoseResult, 
        position: Tuple[int, int] = (30, 30),
        font_scale: float = 0.5,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 1
    ) -> np.ndarray:
        """
        Draw pose information (pitch, yaw, roll) on the frame.
        
        Parameters:
        -----------
        frame : numpy.ndarray
            Input image to draw on
        head_pose_result : HeadPoseResult
            Head pose estimation result
        position : tuple, optional
            (x, y) coordinates for text position
        font_scale : float, optional
            Font scale
        color : tuple, optional
            Text color (BGR)
        thickness : int, optional
            Text thickness
            
        Returns:
        --------
        numpy.ndarray
            Image with pose information drawn
        """
        try:
            pitch, yaw, roll = head_pose_result.euler_angles
            confidence = head_pose_result.confidence
            
            # Draw text
            cv2.putText(frame, f"Pitch: {pitch:.1f}°", 
                        (position[0], position[1]), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            cv2.putText(frame, f"Yaw: {yaw:.1f}°", 
                        (position[0], position[1] + 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            cv2.putText(frame, f"Roll: {roll:.1f}°", 
                        (position[0], position[1] + 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            cv2.putText(frame, f"Conf: {confidence:.2f}", 
                        (position[0], position[1] + 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            
            return frame
        except Exception as e:
            logger.error(f"Error in drawing pose info: {e}")
            return frame

    @classmethod
    def from_calibration_file(
        cls, 
        calibration_file: str, 
        frame_size: Tuple[int, int],
        pnp_method: int = cv2.SOLVEPNP_ITERATIVE
    ) -> 'HeadPoseEstimator':
        """
        Create a HeadPoseEstimator from a camera calibration file.
        
        Parameters:
        -----------
        calibration_file : str
            Path to the camera calibration file (numpy .npz format)
        frame_size : tuple
            (width, height) of the frames that will be processed
        pnp_method : int, optional
            PnP method to use
            
        Returns:
        --------
        HeadPoseEstimator
            Initialized estimator with calibration data
        """
        try:
            # Load calibration data
            calib_data = np.load(calibration_file)
            camera_matrix = calib_data['camera_matrix']
            dist_coeffs = calib_data['dist_coeffs']
            
            # Create estimator with frame size
            estimator = cls(
                frame_size=frame_size,
                dist_coeffs=dist_coeffs,
                pnp_method=pnp_method
            )
            
            # Override camera matrix
            estimator.camera_matrix = camera_matrix
            
            logger.info(f"Created HeadPoseEstimator from calibration file: {calibration_file}")
            return estimator
        except Exception as e:
            logger.error(f"Error loading calibration file: {e}")
            raise ValueError(f"Failed to load calibration from {calibration_file}: {e}")