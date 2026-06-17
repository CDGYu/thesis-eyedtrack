#!/usr/bin/env python3
"""
Simple validation script to test the improved detection system
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        import cv2
        print("✅ OpenCV imported successfully")
    except ImportError as e:
        print(f"❌ OpenCV import failed: {e}")
        return False
    
    try:
        import dlib
        try:
            version = dlib.DLIB_VERSION
        except AttributeError:
            version = "unknown"
        print(f"✅ dlib imported successfully (version: {version})")
    except ImportError as e:
        print(f"❌ dlib import failed: {e}")
        return False
    
    try:
        import numpy as np
        print("✅ NumPy imported successfully")
    except ImportError as e:
        print(f"❌ NumPy import failed: {e}")
        return False
    
    try:
        from scipy.spatial import distance
        print("✅ SciPy distance imported successfully")
    except ImportError as e:
        print(f"❌ SciPy import failed: {e}")
        return False
    
    return True

def test_shape_predictor():
    """Test if shape predictor file exists"""
    print("\n🔍 Testing shape predictor...")
    
    shape_predictor_path = "shape_predictor_68_face_landmarks.dat"
    if os.path.exists(shape_predictor_path):
        file_size = os.path.getsize(shape_predictor_path) / (1024 * 1024)  # MB
        print(f"✅ Shape predictor found: {shape_predictor_path} ({file_size:.1f} MB)")
        return True
    else:
        print(f"❌ Shape predictor not found: {shape_predictor_path}")
        return False

def test_config():
    """Test if configuration loads correctly"""
    print("\n🔍 Testing configuration...")
    
    try:
        from config_loader import ConfigLoader
        config_loader = ConfigLoader("config.yaml")
        config = config_loader.get_config()
        
        # Check if improved detection is enabled
        use_improved = config.get("detection", {}).get("use_improved_dlib", False)
        print(f"✅ Configuration loaded successfully")
        print(f"   Improved dlib detection: {'ENABLED' if use_improved else 'DISABLED'}")
        
        # Check thresholds
        detection_config = config.get("detection", {})
        print(f"   EAR threshold: {detection_config.get('ear_threshold', 'Not set')}")
        print(f"   MAR threshold: {detection_config.get('mar_threshold', 'Not set')}")
        print(f"   Yaw threshold: {detection_config.get('yaw_threshold', 'Not set')}")
        print(f"   Pitch threshold: {detection_config.get('pitch_threshold', 'Not set')}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_frame_processor():
    """Test if frame processor can be initialized"""
    print("\n🔍 Testing frame processor...")
    
    try:
        from config_loader import ConfigLoader
        from frame_processor import OptimizedFrameProcessor
        
        config_loader = ConfigLoader("config.yaml")
        config = config_loader.get_config()
        
        processor = OptimizedFrameProcessor(config)
        
        if hasattr(processor, 'use_improved_detection'):
            print(f"✅ Frame processor initialized successfully")
            print(f"   Improved detection: {'ENABLED' if processor.use_improved_detection else 'DISABLED'}")
            
            if processor.use_improved_detection:
                if hasattr(processor, 'dlib_detector') and hasattr(processor, 'dlib_predictor'):
                    print("✅ dlib detector and predictor initialized")
                else:
                    print("❌ dlib detector/predictor not properly initialized")
                    return False
        else:
            print("❌ Frame processor missing improved detection attribute")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Frame processor test failed: {e}")
        return False

def test_calculations():
    """Test the improved calculation methods"""
    print("\n🔍 Testing calculation methods...")
    
    try:
        from config_loader import ConfigLoader
        from frame_processor import OptimizedFrameProcessor
        import numpy as np
        
        config_loader = ConfigLoader("config.yaml")
        config = config_loader.get_config()
        processor = OptimizedFrameProcessor(config)
        
        # Test EAR calculation with dummy data
        dummy_eye = np.array([[0, 0], [0, 5], [0, 10], [20, 5], [0, 10], [0, 0]])  # 6 points
        ear = processor.calculate_ear_improved(dummy_eye)
        print(f"✅ EAR calculation test: {ear:.4f}")
        
        # Test MAR calculation with dummy data
        dummy_mouth = np.zeros((20, 2))  # 20 points
        dummy_mouth[12] = [0, 0]   # Left corner
        dummy_mouth[16] = [20, 0]  # Right corner
        dummy_mouth[13] = [10, 5]  # Top center
        dummy_mouth[19] = [10, 0]  # Bottom center
        dummy_mouth[14] = [5, 3]   # Top left
        dummy_mouth[18] = [5, 0]   # Bottom left
        dummy_mouth[15] = [15, 3]  # Top right
        dummy_mouth[17] = [15, 0]  # Bottom right
        
        mar = processor.calculate_mar_improved(dummy_mouth)
        print(f"✅ MAR calculation test: {mar:.4f}")
        
        # Test head pose calculation with dummy landmarks
        dummy_landmarks = np.zeros((68, 2))
        dummy_landmarks[30] = [320, 240]  # Nose tip
        dummy_landmarks[8] = [320, 400]   # Chin
        dummy_landmarks[36] = [280, 220]  # Left eye left corner
        dummy_landmarks[45] = [360, 220]  # Right eye right corner
        dummy_landmarks[48] = [300, 320]  # Left mouth corner
        dummy_landmarks[54] = [340, 320]  # Right mouth corner
        
        yaw, pitch = processor.calculate_head_pose_improved(dummy_landmarks, (480, 640))
        print(f"✅ Head pose calculation test: Yaw={yaw:.2f}°, Pitch={pitch:.2f}°")
        
        return True
    except Exception as e:
        print(f"❌ Calculation methods test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🚀 IMPROVED DETECTION SYSTEM VALIDATION")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Shape Predictor", test_shape_predictor),
        ("Configuration", test_config),
        ("Frame Processor", test_frame_processor),
        ("Calculation Methods", test_calculations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} test PASSED")
        else:
            print(f"❌ {test_name} test FAILED")
    
    print(f"\n{'='*50}")
    print(f"📊 VALIDATION SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The improved detection system is ready to use.")
        print("\n🚀 Next steps:")
        print("1. Start the backend: python main.py")
        print("2. Test with frontend or run: python test_improved_detection.py")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 