"""
Video recording module for driver monitoring system.
"""

import cv2
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

class VideoRecorder:
    def __init__(self, output_dir: str = "driver_monitoring_logs/videos"):
        """
        Initialize video recorder.
        
        Args:
            output_dir: Directory to save recorded videos
        """
        self.output_dir = output_dir
        self.writer: Optional[cv2.VideoWriter] = None
        self.is_recording = False
        self.recording_start_time = None
        self.last_risky_time = None
        self.current_filename = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Video output directory: {os.path.abspath(output_dir)}")
        
        # Recording settings
        self.fps = 30
        # Try different codecs in order of preference
        self.codec_options = [
            ('mp4v', '.mp4'),
            ('XVID', '.avi'),
            ('MJPG', '.avi'),
            ('X264', '.mp4')
        ]
        self.current_codec = None
        self.current_ext = None
        self.buffer_after_risky = 3.0  # 3 seconds after last risky behavior
        
        # Buffer to store frames before risky behavior is detected
        self.frame_buffer = deque(maxlen=self.fps * 2)  # Store 2 seconds of frames
        self.frame_buffer_times = deque(maxlen=self.fps * 2)
        
        # Performance tracking
        self.frame_write_errors = 0
        self.max_frame_write_errors = 5
        
    def _try_codec(self, frame: np.ndarray, codec: str, ext: str) -> bool:
        """Try to initialize a codec and write a test frame"""
        try:
            height, width = frame.shape[:2]
            test_filename = os.path.join(self.output_dir, f"test_{int(time.time())}{ext}")
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_writer = cv2.VideoWriter(test_filename, fourcc, self.fps, (width, height))
            
            if test_writer.isOpened():
                test_writer.write(frame)
                test_writer.release()
                if os.path.exists(test_filename) and os.path.getsize(test_filename) > 0:
                    os.remove(test_filename)
                    self.current_codec = codec
                    self.current_ext = ext
                    logger.info(f"Successfully initialized codec {codec}")
                    return True
            return False
        except Exception as e:
            logger.debug(f"Codec {codec} failed: {str(e)}")
            return False
        
    def start_recording(self, frame: Any, behavior_data: Dict[str, Any]) -> bool:
        """
        Start recording video when risky behavior is detected.
        
        Args:
            frame: Current frame to determine video dimensions
            behavior_data: Dictionary containing behavior information
            
        Returns:
            bool: True if recording started successfully
        """
        if self.is_recording:
            return True
            
        try:
            # Validate frame
            if not isinstance(frame, np.ndarray) or len(frame.shape) != 3:
                logger.error("Invalid frame format for video recording")
                return False
                
            # Get frame dimensions
            height, width = frame.shape[:2]
            
            # If codec not initialized, try to find a working one
            if self.current_codec is None:
                for codec, ext in self.codec_options:
                    if self._try_codec(frame, codec, ext):
                        break
                if self.current_codec is None:
                    logger.error("No working video codec found")
                    return False
            
            # Create filename with timestamp and behavior info
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            behavior = behavior_data.get("behavior", "unknown")
            filename = f"risky_behavior_{timestamp}_{behavior}{self.current_ext}"
            self.current_filename = os.path.join(self.output_dir, filename)
            
            logger.info(f"Starting recording to {self.current_filename}")
            
            # Initialize video writer
            self.writer = cv2.VideoWriter(
                self.current_filename,
                cv2.VideoWriter_fourcc(*self.current_codec),
                self.fps,
                (width, height)
            )
            
            if not self.writer.isOpened():
                logger.error(f"Failed to open video writer for {self.current_filename}")
                return False
                
            # Write buffered frames first (if any)
            frames_written = 0
            for buffered_frame in self.frame_buffer:
                if buffered_frame is not None:
                    self.writer.write(buffered_frame)
                    frames_written += 1
            logger.info(f"Wrote {frames_written} buffered frames")
                
            self.is_recording = True
            self.recording_start_time = time.time()
            self.last_risky_time = time.time()
            logger.info(f"Started recording risky behavior: {behavior}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting video recording: {str(e)}")
            self.cleanup()
            return False
            
    def write_frame(self, frame: Any, is_risky: bool = False) -> bool:
        """
        Write a frame to the current video recording.
        
        Args:
            frame: Frame to write
            is_risky: Whether the current frame shows risky behavior
            
        Returns:
            bool: True if frame was written successfully
        """
        try:
            # Validate frame
            if not isinstance(frame, np.ndarray) or len(frame.shape) != 3:
                logger.error("Invalid frame format for video recording")
                return False
                
            current_time = time.time()
            
            # Always store frame in buffer
            if frame.shape[2] == 4:  # If frame has alpha channel
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            self.frame_buffer.append(frame.copy())
            self.frame_buffer_times.append(current_time)
            
            # Start recording if risky behavior detected and not already recording
            if is_risky and not self.is_recording:
                logger.info("Risky behavior detected, starting recording")
                return self.start_recording(frame, {"behavior": "risky_behavior"})
            
            if not self.is_recording or self.writer is None:
                return False
                
            # Update last risky time if risky behavior is detected
            if is_risky:
                self.last_risky_time = current_time
                logger.debug("Risky behavior detected, extending recording")
            
            # Check if we've exceeded buffer time after last risky behavior
            if self.last_risky_time and current_time - self.last_risky_time > self.buffer_after_risky:
                logger.info(f"No risky behavior detected for {self.buffer_after_risky} seconds, stopping recording")
                self.stop_recording()
                return False
                
            # Write frame to video
            self.writer.write(frame)
            return True
            
        except Exception as e:
            logger.error(f"Error in write_frame: {str(e)}")
            self.cleanup()
            return False
            
    def stop_recording(self) -> bool:
        """
        Stop the current video recording.
        
        Returns:
            bool: True if recording was stopped successfully
        """
        if not self.is_recording or self.writer is None:
            return False
            
        try:
            self.writer.release()
            if os.path.exists(self.current_filename):
                file_size = os.path.getsize(self.current_filename)
                logger.info(f"Video saved: {self.current_filename} (size: {file_size} bytes)")
            else:
                logger.error(f"Video file not found after recording: {self.current_filename}")
            self.cleanup()
            return True
            
        except Exception as e:
            logger.error(f"Error stopping video recording: {str(e)}")
            self.cleanup()
            return False
            
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.writer is not None:
                self.writer.release()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            self.writer = None
            self.is_recording = False
            self.recording_start_time = None
            self.last_risky_time = None
            self.current_filename = None 