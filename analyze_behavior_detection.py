#!/usr/bin/env python3
"""
Comprehensive analysis and testing script for the driver monitoring system.
This script helps understand how the 3 behaviors are detected and identifies accuracy issues.
"""

import cv2
import numpy as np
import time
import logging
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque

from config_loader import ConfigLoader
from frame_processor import OptimizedFrameProcessor
from face_analysis import eye_aspect_ratio, mouth_aspect_ratio
from face_analysis.face_detection import FaceDetector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BehaviorDetectionAnalyzer:
    """Analyzes and tests the behavior detection system"""
    
    def __init__(self, config_path="config.yaml"):
        """Initialize the analyzer"""
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.get_config()
        
        # Initialize frame processor
        self.frame_processor = OptimizedFrameProcessor(self.config)
        
        # Initialize face detector for standalone testing
        self.face_detector = FaceDetector(self.config)
        
        # Detection thresholds from config
        detection_config = self.config.get("detection", self.config.get("thresholds", {}))
        self.ear_threshold = detection_config.get("ear_threshold", 0.25)
        self.mar_threshold = detection_config.get("mar_threshold", 0.5)
        self.yaw_threshold = detection_config.get("yaw_threshold", 45)
        self.pitch_threshold = detection_config.get("pitch_threshold", 30)
        self.drowsy_frames_threshold = detection_config.get("drowsy_frames_threshold", 15)
        self.yawn_frames_threshold = detection_config.get("yawn_frames_threshold", 20)
        self.distraction_frames_threshold = detection_config.get("distraction_frames_threshold", 15)
        
        # Data collection for analysis
        self.metrics_history = {
            'ear': deque(maxlen=1000),
            'mar': deque(maxlen=1000),
            'yaw': deque(maxlen=1000),
            'pitch': deque(maxlen=1000),
            'roll': deque(maxlen=1000)
        }
        
        print("🔍 Behavior Detection Analyzer Initialized")
        print(f"📊 Current Thresholds:")
        print(f"   EAR (Eye Aspect Ratio): {self.ear_threshold}")
        print(f"   MAR (Mouth Aspect Ratio): {self.mar_threshold}")
        print(f"   Yaw Threshold: {self.yaw_threshold}°")
        print(f"   Pitch Threshold: {self.pitch_threshold}°")
        print(f"   Frame Thresholds: Drowsy={self.drowsy_frames_threshold}, Yawn={self.yawn_frames_threshold}, Distraction={self.distraction_frames_threshold}")

    def analyze_detection_system(self):
        """Comprehensive analysis of the detection system"""
        print("\n" + "="*80)
        print("🔍 DRIVER MONITORING SYSTEM ANALYSIS")
        print("="*80)
        
        print("\n📋 BEHAVIOR DETECTION METHODS:")
        print("-" * 50)
        
        print("\n1️⃣ DROWSINESS DETECTION:")
        print("   Method: Eye Aspect Ratio (EAR)")
        print("   Formula: EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)")
        print("   Where p1-p6 are the 6 eye landmark points")
        print(f"   Threshold: EAR < {self.ear_threshold}")
        print(f"   Frame requirement: {self.drowsy_frames_threshold} consecutive frames")
        print("   Logic: Lower EAR = more closed eyes = drowsiness")
        
        print("\n2️⃣ YAWNING DETECTION:")
        print("   Method: Mouth Aspect Ratio (MAR)")
        print("   Formula: MAR = (|p2-p5| + |p3-p4|) / (2 * |p1-p6|)")
        print("   Where p1-p6 are mouth landmark points")
        print(f"   Threshold: MAR < {self.mar_threshold}")
        print(f"   Frame requirement: {self.yawn_frames_threshold} consecutive frames")
        print("   Logic: Lower MAR = more open mouth = yawning")
        print("   ⚠️  NOTE: This logic seems INVERTED - typically higher MAR = open mouth")
        
        print("\n3️⃣ DISTRACTION DETECTION:")
        print("   Method: Head Pose Estimation (Yaw & Pitch)")
        print("   Calculation: Using solvePnP with 3D face model")
        print(f"   Thresholds: |Yaw| > {self.yaw_threshold}° OR |Pitch| > {self.pitch_threshold}°")
        print(f"   Frame requirement: {self.distraction_frames_threshold} consecutive frames")
        print("   Logic: Large head rotation = looking away = distraction")
        
        print("\n🚨 POTENTIAL ACCURACY ISSUES IDENTIFIED:")
        print("-" * 50)
        
        issues = []
        
        # Issue 1: MAR logic seems inverted
        issues.append({
            'severity': 'HIGH',
            'component': 'Yawning Detection',
            'issue': 'MAR threshold logic appears inverted',
            'description': 'Code checks MAR < threshold for yawning, but typically open mouth = higher MAR',
            'location': 'frame_processor.py line ~304'
        })
        
        # Issue 2: MediaPipe landmark indices
        issues.append({
            'severity': 'MEDIUM',
            'component': 'Landmark Extraction',
            'issue': 'MediaPipe landmark indices may be incorrect',
            'description': 'Using hardcoded indices for MediaPipe (468 points) vs dlib (68 points)',
            'location': 'frame_processor.py lines 190-200'
        })
        
        # Issue 3: Head pose calculation simplification
        issues.append({
            'severity': 'MEDIUM',
            'component': 'Head Pose Estimation',
            'issue': 'Simplified head pose calculation for MediaPipe',
            'description': 'Using geometric approximation instead of proper solvePnP for MediaPipe landmarks',
            'location': 'frame_processor.py lines 320-340'
        })
        
        # Issue 4: Threshold sensitivity
        issues.append({
            'severity': 'LOW',
            'component': 'Thresholds',
            'issue': 'Thresholds may not be person-specific',
            'description': 'Fixed thresholds may not work well for all face shapes/sizes',
            'location': 'config.yaml detection section'
        })
        
        for i, issue in enumerate(issues, 1):
            print(f"\n{i}. [{issue['severity']}] {issue['component']}")
            print(f"   Issue: {issue['issue']}")
            print(f"   Details: {issue['description']}")
            print(f"   Location: {issue['location']}")
        
        return issues

    def test_camera_feed_analysis(self, duration=30):
        """Test the system with live camera feed"""
        print(f"\n🎥 TESTING WITH LIVE CAMERA FEED ({duration} seconds)")
        print("-" * 50)
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Error: Could not open camera")
            return
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['camera']['width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['camera']['height'])
        cap.set(cv2.CAP_PROP_FPS, self.config['camera']['fps'])
        
        start_time = time.time()
        frame_count = 0
        
        print("📊 Real-time metrics (press 'q' to quit early):")
        print("EAR=Eye Aspect Ratio, MAR=Mouth Aspect Ratio, Y=Yaw, P=Pitch")
        
        try:
            while time.time() - start_time < duration:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Process frame
                result = self.frame_processor.process_frame(frame)
                
                if result['success']:
                    metrics = result['metrics']
                    behaviors = result['behavior_category']
                    
                    # Store metrics
                    if metrics['ear'] > 0:
                        self.metrics_history['ear'].append(metrics['ear'])
                    if metrics['mar'] > 0:
                        self.metrics_history['mar'].append(metrics['mar'])
                    if metrics['head_pose'] is not None and len(metrics['head_pose']) >= 3:
                        self.metrics_history['pitch'].append(metrics['head_pose'][0])
                        self.metrics_history['yaw'].append(metrics['head_pose'][1])
                        self.metrics_history['roll'].append(metrics['head_pose'][2])
                    
                    # Display current metrics
                    if frame_count % 10 == 0:  # Every 10 frames
                        ear = metrics.get('ear', 0)
                        mar = metrics.get('mar', 0)
                        head_pose = metrics.get('head_pose', [0, 0, 0])
                        yaw = head_pose[1] if len(head_pose) > 1 else 0
                        pitch = head_pose[0] if len(head_pose) > 0 else 0
                        
                        status = []
                        if behaviors['is_drowsy']:
                            status.append("😴DROWSY")
                        if behaviors['is_yawning']:
                            status.append("🥱YAWNING")
                        if behaviors['is_distracted']:
                            status.append("👀DISTRACTED")
                        
                        status_str = " | ".join(status) if status else "✅NORMAL"
                        
                        print(f"Frame {frame_count:4d}: EAR={ear:.3f} MAR={mar:.3f} Y={yaw:+5.1f}° P={pitch:+5.1f}° | {status_str}")
                
                # Show frame with annotations
                self._annotate_frame(frame, result)
                cv2.imshow('Behavior Analysis', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except KeyboardInterrupt:
            print("\n⏹️ Analysis interrupted by user")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            
        print(f"\n📈 Analysis complete: {frame_count} frames processed")
        self._generate_analysis_report()

    def _annotate_frame(self, frame, result):
        """Add annotations to frame for visualization"""
        if not result['success']:
            return
            
        metrics = result['metrics']
        behaviors = result['behavior_category']
        
        # Draw face box if detected
        if result['face_box']:
            x, y, w, h = result['face_box']
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Display metrics
        y_offset = 30
        cv2.putText(frame, f"EAR: {metrics.get('ear', 0):.3f} (thresh: {self.ear_threshold})", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += 25
        
        cv2.putText(frame, f"MAR: {metrics.get('mar', 0):.3f} (thresh: {self.mar_threshold})", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += 25
        
        if metrics.get('head_pose') is not None and len(metrics['head_pose']) >= 2:
            yaw, pitch = metrics['head_pose'][1], metrics['head_pose'][0]
            cv2.putText(frame, f"Yaw: {yaw:+5.1f}° (thresh: ±{self.yaw_threshold}°)", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 25
            cv2.putText(frame, f"Pitch: {pitch:+5.1f}° (thresh: ±{self.pitch_threshold}°)", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Display behavior status
        y_offset = frame.shape[0] - 80
        if behaviors['is_drowsy']:
            cv2.putText(frame, "DROWSY DETECTED", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            y_offset += 25
        if behaviors['is_yawning']:
            cv2.putText(frame, "YAWNING DETECTED", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
            y_offset += 25
        if behaviors['is_distracted']:
            cv2.putText(frame, "DISTRACTED", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    def _generate_analysis_report(self):
        """Generate analysis report from collected data"""
        print("\n📊 ANALYSIS REPORT")
        print("-" * 50)
        
        if len(self.metrics_history['ear']) > 0:
            ear_data = list(self.metrics_history['ear'])
            print(f"EAR Statistics:")
            print(f"  Mean: {np.mean(ear_data):.4f}")
            print(f"  Std:  {np.std(ear_data):.4f}")
            print(f"  Min:  {np.min(ear_data):.4f}")
            print(f"  Max:  {np.max(ear_data):.4f}")
            print(f"  Below threshold ({self.ear_threshold}): {np.sum(np.array(ear_data) < self.ear_threshold)}/{len(ear_data)} frames")
        
        if len(self.metrics_history['mar']) > 0:
            mar_data = list(self.metrics_history['mar'])
            print(f"\nMAR Statistics:")
            print(f"  Mean: {np.mean(mar_data):.4f}")
            print(f"  Std:  {np.std(mar_data):.4f}")
            print(f"  Min:  {np.min(mar_data):.4f}")
            print(f"  Max:  {np.max(mar_data):.4f}")
            print(f"  Below threshold ({self.mar_threshold}): {np.sum(np.array(mar_data) < self.mar_threshold)}/{len(mar_data)} frames")
        
        if len(self.metrics_history['yaw']) > 0:
            yaw_data = list(self.metrics_history['yaw'])
            print(f"\nYaw Statistics:")
            print(f"  Mean: {np.mean(yaw_data):+6.2f}°")
            print(f"  Std:  {np.std(yaw_data):6.2f}°")
            print(f"  Min:  {np.min(yaw_data):+6.2f}°")
            print(f"  Max:  {np.max(yaw_data):+6.2f}°")
            print(f"  Beyond threshold (±{self.yaw_threshold}°): {np.sum(np.abs(yaw_data) > self.yaw_threshold)}/{len(yaw_data)} frames")

def main():
    """Main function to run the analysis"""
    analyzer = BehaviorDetectionAnalyzer()
    
    while True:
        print("\n" + "="*60)
        print("🔍 BEHAVIOR DETECTION ANALYZER")
        print("="*60)
        print("1. Analyze Detection System")
        print("2. Test with Live Camera (30s)")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            analyzer.analyze_detection_system()
        elif choice == '2':
            analyzer.test_camera_feed_analysis()
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 1-3.")

if __name__ == "__main__":
    main() 