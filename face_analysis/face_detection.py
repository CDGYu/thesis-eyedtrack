import cv2
import dlib
import numpy as np
import os
import logging
from typing import List, Optional, Tuple, Union
from pathlib import Path

# Attempt to import MediaPipe
try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default model paths - using absolute paths with environment variable fallback
DEFAULT_MODELS_DIR = os.environ.get('FACE_MODELS_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHAPE_PREDICTOR_PATH = os.path.join(DEFAULT_MODELS_DIR, 'shape_predictor_68_face_landmarks.dat')
CNN_FACE_DETECTOR_PATH = os.path.join(DEFAULT_MODELS_DIR, 'mmod_human_face_detector.dat')
HAAR_CASCADE_PATH = os.path.join(DEFAULT_MODELS_DIR, 'haarcascade_frontalface_default.xml')


class FaceDetector:
    """
    Enhanced FaceDetector providing multiple detection and landmark options:
      - MediaPipe Face Detection and Face Mesh (468 landmarks)
      - OpenCV Haar Cascade
      - dlib CNN and HOG detectors
      - dlib 68-point shape predictor

    Usage:
        # Basic usage with default settings
        with FaceDetector() as detector:
            faces = detector.detect_faces(frame)
            
        # Advanced usage with all features enabled
        with FaceDetector(use_cnn=True, use_media_pipe=True, mesh_confidence=0.5) as detector:
            output = detector.process_frame(frame, draw_boxes=True, show_landmarks=True)
            
        # Background blurring example
        with FaceDetector() as detector:
            faces = detector.detect_faces(frame)
            blurred_bg = detector.blur_background(frame, faces, blur_strength=25)
            
        # Face cropping example
        with FaceDetector() as detector:
            faces = detector.detect_faces(frame)
            if faces:
                face_img = detector.crop_face(frame, faces[0], padding=20)
    """

    def __init__(self, config):
        """Initialize face detector with configuration"""
        self.config = config
        
        # Load Haar Cascade classifier
        if os.path.exists(HAAR_CASCADE_PATH):
            self.haar_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
            logger.info("Haar Cascade loaded successfully.")
        else:
            logger.error(f"Haar Cascade file not found at {HAAR_CASCADE_PATH}")
            self.haar_cascade = None
            
        # Load CNN detector if enabled
        self.use_cnn = config["face_detection"].get("use_cnn", False)
        if self.use_cnn:
            if os.path.exists(CNN_FACE_DETECTOR_PATH):
                self.cnn_detector = dlib.cnn_face_detection_model_v1(CNN_FACE_DETECTOR_PATH)
                logger.info("CNN detector loaded successfully.")
            else:
                logger.warning(f"CNN detector file not found at {CNN_FACE_DETECTOR_PATH}")
                self.cnn_detector = None
                self.use_cnn = False
                
        # Load shape predictor for landmarks
        if os.path.exists(SHAPE_PREDICTOR_PATH):
            self.shape_predictor = dlib.shape_predictor(SHAPE_PREDICTOR_PATH)
            logger.info("Shape predictor loaded successfully.")
        else:
            logger.warning(f"Shape predictor file not found at {SHAPE_PREDICTOR_PATH}")
            self.shape_predictor = None
            
        # Initialize MediaPipe if enabled
        self.use_mediapipe = config["face_detection"].get("use_media_pipe", True)
        if self.use_mediapipe:
            try:
                import mediapipe as mp
                self.mp_face_mesh = mp.solutions.face_mesh
                self.face_mesh = self.mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                logger.info("MediaPipe Face Mesh initialized successfully.")
            except ImportError:
                logger.warning("MediaPipe not available, falling back to other detectors.")
                self.use_mediapipe = False
                
    def __enter__(self) -> 'FaceDetector':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Release MediaPipe resources
        if self.use_mediapipe:
            self.face_mesh.close()

    def detect(self, frame):
        """Detect faces in frame using available detectors"""
        if frame is None:
            return None
            
        # Try MediaPipe first if enabled
        if self.use_mediapipe:
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.face_mesh.process(frame_rgb)
                if results.multi_face_landmarks:
                    face_landmarks = results.multi_face_landmarks[0]
                    h, w = frame.shape[:2]
                    x_min = w
                    y_min = h
                    x_max = 0
                    y_max = 0
                    for landmark in face_landmarks.landmark:
                        x, y = int(landmark.x * w), int(landmark.y * h)
                        x_min = min(x_min, x)
                        y_min = min(y_min, y)
                        x_max = max(x_max, x)
                        y_max = max(y_max, y)
                    return [x_min, y_min, x_max - x_min, y_max - y_min]
            except Exception as e:
                logger.error(f"MediaPipe detection failed: {e}")
                
        # Try CNN detector if enabled
        if self.use_cnn and self.cnn_detector:
            try:
                dets = self.cnn_detector(frame)
                if len(dets) > 0:
                    d = dets[0].rect
                    return [d.left(), d.top(), d.width(), d.height()]
            except Exception as e:
                logger.error(f"CNN detection failed: {e}")
                
        # Fall back to Haar Cascade
        if self.haar_cascade:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.haar_cascade.detectMultiScale(
                    gray,
                    scaleFactor=self.config["face_detection"].get("scale_factor", 1.1),
                    minNeighbors=self.config["face_detection"].get("min_neighbors", 5),
                    minSize=tuple(self.config["face_detection"].get("min_face_size", [30, 30]))
                )
                if len(faces) > 0:
                    return faces[0]
            except Exception as e:
                logger.error(f"Haar Cascade detection failed: {e}")
                
        return None
        
    def get_landmarks(self, frame, face_box):
        """Get facial landmarks using available landmark detectors"""
        if frame is None or face_box is None:
            logger.warning("Invalid frame or face box provided")
            return None
            
        try:
            # Try MediaPipe landmarks if enabled
            if self.use_mediapipe:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = self.face_mesh.process(frame_rgb)
                    if results.multi_face_landmarks:
                        face_landmarks = results.multi_face_landmarks[0]
                        h, w = frame.shape[:2]
                        landmarks = []
                        for landmark in face_landmarks.landmark:
                            x, y = int(landmark.x * w), int(landmark.y * h)
                            landmarks.append((x, y))
                        if len(landmarks) > 0:
                            logger.debug("Successfully detected landmarks using MediaPipe")
                            return np.array(landmarks)
                        else:
                            logger.warning("MediaPipe detected no landmarks, falling back to dlib")
                except Exception as e:
                    logger.error(f"MediaPipe landmark detection failed: {e}")
                    
            # Try dlib shape predictor if available
            if self.shape_predictor:
                try:
                    x, y, w, h = face_box
                    rect = dlib.rectangle(x, y, x + w, y + h)
                    shape = self.shape_predictor(frame, rect)
                    landmarks = []
                    for i in range(68):
                        x = shape.part(i).x
                        y = shape.part(i).y
                        landmarks.append((x, y))
                    if len(landmarks) > 0:
                        logger.debug("Successfully detected landmarks using dlib")
                        return np.array(landmarks)
                    else:
                        logger.warning("dlib detected no landmarks")
                except Exception as e:
                    logger.error(f"dlib landmark detection failed: {e}")
                    
        except Exception as e:
            logger.error(f"Landmark detection failed: {e}")
            
        return None

    def draw_landmarks(
        self,
        frame: np.ndarray,
        landmarks: Union[dlib.full_object_detection, np.ndarray],
        color: Tuple[int, int, int] = (0, 255, 0),
        radius: int = 1
    ) -> np.ndarray:
        """Draw facial landmarks on the image."""
        if landmarks is None:
            return frame
            
        output = frame.copy()
        try:
            if isinstance(landmarks, np.ndarray):
                for (x, y) in landmarks:
                    cv2.circle(output, (x, y), radius, color, -1)
            elif hasattr(landmarks, 'part'):
                for i in range(landmarks.num_parts):
                    pt = landmarks.part(i)
                    cv2.circle(output, (pt.x, pt.y), radius, color, -1)
            return output
        except Exception as e:
            logger.error(f"Error drawing landmarks: {e}", exc_info=True)
            return frame

    def blur_background(
        self,
        frame: np.ndarray,
        face_boxes: List[Tuple[int, int, int, int]],
        blur_strength: int = 21
    ) -> np.ndarray:
        """Blur image background except face regions."""
        if not face_boxes:
            return frame
            
        try:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            for (x, y, bw, bh) in face_boxes:
                cv2.rectangle(mask, (x, y), (x + bw, y + bh), 255, -1)
            blurred = cv2.GaussianBlur(frame, (blur_strength, blur_strength), 0)
            return np.where(mask[:, :, None] == 255, frame, blurred)
        except Exception as e:
            logger.error(f"Error blurring background: {e}", exc_info=True)
            return frame

    def crop_face(
        self,
        frame: np.ndarray,
        face_box: Tuple[int, int, int, int],
        padding: int = 0
    ) -> np.ndarray:
        """Return an optionally padded crop of the face region."""
        if face_box is None:
            return frame
            
        try:
            x, y, bw, bh = face_box
            h, w = frame.shape[:2]
            x1, y1 = max(0, x - padding), max(0, y - padding)
            x2, y2 = min(w, x + bw + padding), min(h, y + bh + padding)
            return frame[y1:y2, x1:x2]
        except Exception as e:
            logger.error(f"Error cropping face: {e}", exc_info=True)
            return frame

    def process_frame(
        self,
        frame: np.ndarray,
        draw_boxes: bool = True,
        show_landmarks: bool = True,
        blur_bg: bool = False,
        blur_strength: int = 21
    ) -> np.ndarray:
        """
        Complete pipeline: detect faces, blur background, draw boxes and landmarks.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            logger.error("Invalid frame provided to process_frame")
            return np.zeros((300, 300, 3), dtype=np.uint8)  # Return empty frame
            
        try:
            faces = self.detect(frame)
            output = frame.copy()

            # Optional background blur
            if blur_bg and faces:
                output = self.blur_background(output, [faces], blur_strength)

            for box in faces:
                x, y, bw, bh = box
                if draw_boxes:
                    cv2.rectangle(output, (x, y), (x + bw, y + bh), (255, 0, 0), 2)
                if show_landmarks and self.shape_predictor:
                    lm = self.get_landmarks(frame, box)
                    if lm is not None:
                        output = self.draw_landmarks(output, lm)
            return output
        except Exception as e:
            logger.error(f"Error in process_frame: {e}", exc_info=True)
            return frame


if __name__ == '__main__':
    # Simple webcam example
    cap = cv2.VideoCapture(0)  # Use default camera
    
    # Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open camera.")
        exit()
    
    # Create face detector with all features enabled
    with FaceDetector() as fd:
        print(f"FaceDetector ready. MediaPipe: {HAS_MEDIAPIPE}, CNN: {fd.use_cnn}")
        
        while True:
            # Capture frame-by-frame
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture image")
                break
                
            # Process the frame
            processed = fd.process_frame(
                frame,
                draw_boxes=True,
                show_landmarks=True,
                blur_bg=False  # Set to True to blur background
            )
            
            # Display the resulting frame
            cv2.imshow('Face Detection', processed)
            
            # Press 'q' to exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    # Release resources
    cap.release()
    cv2.destroyAllWindows()