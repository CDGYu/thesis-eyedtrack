"""
Frame grabbing module for driver monitoring system.
"""

import cv2
import time
import queue
import logging
import threading
import numpy as np
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class OptimizedFrameGrabber(threading.Thread):
    """Thread dedicated to capturing frames from camera with optimizations"""
    
    def __init__(self, config, frame_queue, stop_event):
        super().__init__()
        self.config = config
        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self.daemon = True
        self.fps_counter = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.failed_frames = 0
        self.max_failed_frames = 10
        
    def run(self):
        # Initialize camera with optimized settings
        try:
            cap = cv2.VideoCapture(self.config["camera"]["device_id"])
            
            # Configure camera properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["camera"]["width"])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["camera"]["height"])
            cap.set(cv2.CAP_PROP_FPS, self.config["camera"]["fps"])
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
            
            # Try setting MJPG format if available
            try:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            except Exception as e:
                logger.warning(f"Failed to set MJPG format: {e}")
            
            # Verify camera is opened
            if not cap.isOpened():
                logger.error("Failed to open camera")
                self.stop_event.set()
                return
                
            # Verify we can read at least one frame
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                logger.error("Failed to read initial frame from camera")
                self.stop_event.set()
                return
                
            # Log camera properties
            actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            logger.info(f"Camera initialized: {actual_width}x{actual_height} @ {actual_fps}fps")
            
            try:
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            except Exception as e:
                logger.warning(f"Failed to set camera focus/exposure: {e}")
            
            frame_index = 0
            
            # Main capture loop
            while not self.stop_event.is_set():
                # Calculate FPS
                self.fps_counter += 1
                current_time = time.time()
                if current_time - self.last_fps_time >= 1.0:
                    self.fps = self.fps_counter / (current_time - self.last_fps_time)
                    self.fps_counter = 0
                    self.last_fps_time = current_time
                
                # Capture frame
                try:
                    ret, frame = cap.read()
                    
                    # Check if frame is valid
                    if not ret or frame is None or frame.size == 0:
                        self.failed_frames += 1
                        logger.warning(f"Failed to capture frame ({self.failed_frames}/{self.max_failed_frames})")
                        
                        # If too many consecutive failures, reset camera
                        if self.failed_frames >= self.max_failed_frames:
                            logger.error("Too many consecutive frame capture failures, resetting camera")
                            cap.release()
                            time.sleep(1)
                            cap = cv2.VideoCapture(self.config["camera"]["device_id"])
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["camera"]["width"])
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["camera"]["height"])
                            cap.set(cv2.CAP_PROP_FPS, self.config["camera"]["fps"])
                            self.failed_frames = 0
                        
                        # Skip this iteration
                        time.sleep(0.01)
                        continue
                    
                    # Reset failure counter on successful frame
                    self.failed_frames = 0
                    
                    # Ensure frame is in the correct format (8-bit BGR)
                    if frame.dtype != np.uint8:
                        frame = np.asarray(frame, dtype=np.uint8)
                    
                    # Resize if configured
                    if self.config["performance"]["resize_factor"] != 1.0:
                        h, w = frame.shape[:2]
                        new_h = int(h * self.config["performance"]["resize_factor"])
                        new_w = int(w * self.config["performance"]["resize_factor"])
                        frame = cv2.resize(frame, (new_w, new_h))
                    
                    # Add to queue, drop if full
                    try:
                        self.frame_queue.put(frame, block=False)
                        frame_index += 1
                    except queue.Full:
                        pass
                        
                except Exception as e:
                    logger.error(f"Error capturing frame: {e}", exc_info=True)
                    time.sleep(0.1)  # Avoid tight loop on error
                
        except Exception as e:
            logger.error(f"Error in frame grabber: {e}", exc_info=True)
        finally:
            if 'cap' in locals() and cap.isOpened():
                cap.release()
            logger.info("Frame grabber stopped") 