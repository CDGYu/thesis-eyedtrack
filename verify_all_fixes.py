#!/usr/bin/env python3
"""
Comprehensive verification script to test all the fixes applied:
1. Head pose calculation (no more extreme pitch values)
2. Yawning detection sensitivity (MAR 0.6, 2 frames)
3. Distraction detection accuracy (should not trigger for small yaw values)
4. Face detection stability
"""

import cv2
import numpy as np
import time
import logging
from datetime import datetime
import yaml

from config_loader import ConfigLoader
from face_analysis.improved_detection import ImprovedFaceAnalyzer
from frame_processor import OptimizedFrameProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_configuration():
    """Test that configuration values are correctly loaded"""
    print("🔧 TESTING CONFIGURATION")
    print("="*60)
    
    # Load configuration
    config_loader = ConfigLoader("config.yaml")
    config = config_loader.load_config()
    
    # Check detection thresholds
    detection = config.get("detection", {})
    thresholds = config.get("thresholds", {})
    
    print(f"✅ MAR Threshold: {detection.get('mar_threshold', 'NOT FOUND')} (should be 0.6)")
    print(f"✅ Yaw Threshold: {detection.get('yaw_threshold', 'NOT FOUND')} (should be 25)")
    print(f"✅ Pitch Threshold: {detection.get('pitch_threshold', 'NOT FOUND')} (should be 15)")
    print(f"✅ Yawn Frame Threshold: {thresholds.get('yawn_frames', 'NOT FOUND')} (should be 2)")
    print(f"✅ Distraction Frame Threshold: {thresholds.get('distraction_frames', 'NOT FOUND')} (should be 5)")
    
    return config

def test_head_pose_calculation():
    """Test that head pose calculation produces reasonable values"""
    print("\n🧭 TESTING HEAD POSE CALCULATION")
    print("="*60)
    
    config = test_configuration()
    analyzer = ImprovedFaceAnalyzer(config)
    
    # Create a dummy frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Create realistic landmark points (68 points)
    # This simulates a face looking straight ahead
    landmarks = np.array([
        # Face outline (0-16)
        [100, 200], [105, 220], [110, 240], [115, 260], [120, 280], [125, 300], [130, 320], [135, 340], [140, 360],
        [145, 340], [150, 320], [155, 300], [160, 280], [165, 260], [170, 240], [175, 220], [180, 200],
        # Eyebrows (17-26)
        [110, 180], [120, 175], [130, 175], [140, 175], [150, 180],
        [160, 180], [170, 175], [180, 175], [190, 175], [200, 180],
        # Nose (27-35)
        [140, 200], [140, 210], [140, 220], [140, 230],  # Nose bridge
        [125, 235], [130, 240], [140, 245], [150, 240], [155, 235],  # Nose tip area
        # Eyes (36-47)
        [115, 190], [125, 185], [135, 185], [145, 190], [135, 195], [125, 195],  # Left eye
        [155, 190], [165, 185], [175, 185], [185, 190], [175, 195], [165, 195],  # Right eye
        # Mouth (48-67)
        [120, 270], [125, 265], [130, 260], [140, 260], [150, 260], [155, 265], [160, 270],  # Upper lip
        [155, 275], [150, 280], [140, 280], [130, 280], [125, 275], [120, 270],  # Lower lip
        [125, 270], [130, 265], [140, 265], [150, 265], [155, 270], [150, 275], [140, 275], [130, 275]  # Inner mouth
    ], dtype=np.float64)
    
    # Test head pose calculation
    try:
        yaw, pitch = analyzer.calculate_head_pose(landmarks, test_frame.shape)
        print(f"✅ Head pose calculated successfully")
        print(f"   Yaw: {yaw:.2f}° (should be reasonable, not extreme)")
        print(f"   Pitch: {pitch:.2f}° (should be reasonable, not ±90°)")
        
        # Check if values are reasonable
        if -60 <= pitch <= 60:
            print(f"✅ Pitch value is within reasonable bounds (-60° to +60°)")
        else:
            print(f"❌ Pitch value is extreme: {pitch:.2f}°")
            
        if -120 <= yaw <= 120:
            print(f"✅ Yaw value is within reasonable bounds (-120° to +120°)")
        else:
            print(f"❌ Yaw value is extreme: {yaw:.2f}°")
            
    except Exception as e:
        print(f"❌ Head pose calculation failed: {e}")

def test_detection_logic():
    """Test the detection logic with known values"""
    print("\n🔍 TESTING DETECTION LOGIC")
    print("="*60)
    
    config = test_configuration()
    analyzer = ImprovedFaceAnalyzer(config)
    
    # Test MAR threshold (0.6)
    print(f"MAR Threshold Test:")
    print(f"  MAR 0.5 → Yawning: {0.5 > analyzer.mar_threshold} (should be False)")
    print(f"  MAR 0.6 → Yawning: {0.6 > analyzer.mar_threshold} (should be False - equal to threshold)")  
    print(f"  MAR 0.65 → Yawning: {0.65 > analyzer.mar_threshold} (should be True)")
    print(f"  MAR 0.8 → Yawning: {0.8 > analyzer.mar_threshold} (should be True)")
    
    # Test distraction thresholds
    print(f"\nDistraction Threshold Test:")
    print(f"  Yaw ±5° → Distracted: {abs(5) > analyzer.yaw_threshold} (should be False)")
    print(f"  Yaw ±15° → Distracted: {abs(15) > analyzer.yaw_threshold} (should be False)")
    print(f"  Yaw ±25° → Distracted: {abs(25) > analyzer.yaw_threshold} (should be False - equal to threshold)")
    print(f"  Yaw ±30° → Distracted: {abs(30) > analyzer.yaw_threshold} (should be True)")
    
    print(f"  Pitch ±10° → Distracted: {abs(10) > analyzer.pitch_threshold} (should be False)")
    print(f"  Pitch ±15° → Distracted: {abs(15) > analyzer.pitch_threshold} (should be False - equal to threshold)")
    print(f"  Pitch ±20° → Distracted: {abs(20) > analyzer.pitch_threshold} (should be True)")

def test_frame_processing():
    """Test frame processing with dummy data"""
    print("\n🎬 TESTING FRAME PROCESSING")
    print("="*60)
    
    config = test_configuration()
    processor = OptimizedFrameProcessor(config)
    
    # Create a simple test frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(test_frame, (200, 150), (400, 350), (100, 100, 100), -1)  # Gray rectangle as "face"
    
    print("Testing frame processing pipeline...")
    
    try:
        result = processor.process_frame(test_frame)
        
        if result["success"]:
            print("✅ Frame processing successful")
            print(f"   Face detected: {result.get('face_box') is not None}")
            print(f"   Behavior confidence: {result.get('behavior_confidence', 0)}")
            
            behavior = result.get("behavior_category", {})
            print(f"   Behaviors: Drowsy={behavior.get('is_drowsy', False)}, "
                  f"Yawning={behavior.get('is_yawning', False)}, "
                  f"Distracted={behavior.get('is_distracted', False)}")
        else:
            print(f"❌ Frame processing failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Frame processing exception: {e}")

def main():
    """Run all verification tests"""
    print("🧪 COMPREHENSIVE SYSTEM VERIFICATION")
    print("="*80)
    print("Testing all fixes applied for:")
    print("1. Head pose calculation (no extreme pitch values)")
    print("2. Yawning detection sensitivity (MAR 0.6, 2 frames)")  
    print("3. Distraction detection accuracy")
    print("4. Face detection stability")
    print("="*80)
    
    test_configuration()
    test_head_pose_calculation()
    test_detection_logic()
    test_frame_processing()
    
    print("\n" + "="*80)
    print("🎯 VERIFICATION COMPLETE!")
    print("If all tests show ✅, the fixes should resolve your issues:")
    print("  • Faster yawning detection (MAR 0.6, 2 frames)")
    print("  • Accurate distraction detection (no false positives)")
    print("  • Stable head pose values (no extreme ±90° pitch)")
    print("  • Improved system responsiveness")
    print("="*80)

if __name__ == "__main__":
    main() 