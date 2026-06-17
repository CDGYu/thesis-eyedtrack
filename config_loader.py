"""
Configuration Loader Module

This module provides centralized configuration management for the EyeDTrack system.
"""

import os
import yaml
import logging
import copy
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Get the directory of the current file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(CURRENT_DIR, 'config.yaml')

# Default configuration with expanded settings for accuracy improvements
DEFAULT_CONFIG = {
    "camera": {
        "device_id": 0,
        "width": 640,
        "height": 480,
        "fps": 30
    },
    "face_detection": {
        "use_cnn": False,
        "use_media_pipe": True,
        "use_media_pipe_mesh": True,
        "min_face_size": [50, 50],
        "scale_factor": 1.05,
        "min_neighbors": 5
    },
    "clahe": {
        "enabled": True,
        "clip_limit": 2.5,
        "base_tile_grid_size": [8, 8],
        "do_gamma": False,
        "do_homomorphic": False,
        "homomorphic_sigma": 30.0,
        "homomorphic_low_gain": 0.7,
        "homomorphic_high_gain": 1.5
    },
    "thresholds": {
        "ear_lower": 0.15,
        "ear_upper": 0.30,
        "mar_lower": 0.4,
        "mar_upper": 0.9,
        "drowsy_frames": 10,
        "yawn_frames": 8,
        "distraction_frames": 12,
        "yaw_threshold": 30,
        "pitch_threshold": 20,
        "roll_threshold": 15
    },
    "behavior": {
        "model_dir": "driver_behavior_model",
        "only_alert_on_risk": True,
        "top_k": 3,
        "temporal_smoothing": True,
        "smoothing_window": 5,
        "confidence_threshold": 0.5,
        "use_llava": False,
        "behavior_categories": [
            "drowsy driver with eyes closing",
            "distracted driver looking away from road",
            "yawning driver showing fatigue"
        ]
    },
    "logging": {
        "level": "INFO",
        "log_dir": "driver_monitoring_logs",
        "log_data": True,
        "log_events": True
    },
    "display": {
        "show_fps": True,
        "only_show_status_on_risk": False,
        "show_landmarks": False,
        "show_head_pose": False,
        "show_alerts": True,
        "show_status_panel": True,
        "alert_duration": 3.0
    },
    "performance": {
        "skip_frames": 0,
        "max_queue_size": 2,
        "resize_factor": 1.0,
        "use_threading": True,
        "max_workers": 2,
        "enable_gpu": False,
        "camera_buffer_size": 1,
        "batch_size": 1,
        "profile_performance": False,
        "track_memory": False
    },
    "integration": {
        "api": {
            "enabled": False,
            "base_url": "http://localhost:8000/api/",
            "api_key": ""
        },
        "mqtt": {
            "enabled": False,
            "broker": "localhost",
            "port": 1883,
            "topic": "driver_monitoring"
        }
    },
    "gui": {
        "enabled": False
    },
    "head_pose": {
        "use_kalman_filter": False,
        "stabilization_window": 5,
        "confidence_threshold": 0.5
    },
    "robustness": {
        "lighting_adaptation": True,
        "error_recovery": True,
        "fallback_modes": True,
        "automatic_recalibration": False
    }
}

def update_config(base_config, update_dict):
    """Update configuration dictionary recursively"""
    for key, value in update_dict.items():
        if key in base_config:
            if isinstance(value, dict) and isinstance(base_config[key], dict):
                update_config(base_config[key], value)
            else:
                base_config[key] = value
        else:
            base_config[key] = value

def load_config(config_path=None):
    """Load configuration from YAML file"""
    try:
        # Load default configuration
        default_config = {
            "camera": {
                "device_id": 0,
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "face_detection": {
                "use_cnn": False,
                "use_media_pipe": True,
                "use_media_pipe_mesh": True,
                "min_face_size": [50, 50],
                "scale_factor": 1.05,
                "min_neighbors": 5
            },
            "thresholds": {
                "ear_lower": 0.15,
                "ear_upper": 0.30,
                "mar_lower": 0.4,
                "mar_upper": 0.9,
                "drowsy_frames": 10,
                "yawn_frames": 8,
                "distraction_frames": 12,
                "yaw_threshold": 30,
                "pitch_threshold": 20,
                "roll_threshold": 15
            },
            "performance": {
                "skip_frames": 0,
                "max_queue_size": 2,
                "resize_factor": 1.0,
                "use_threading": True,
                "max_workers": 2,
                "enable_gpu": False,
                "camera_buffer_size": 1,
                "batch_size": 1,
                "profile_performance": False,
                "track_memory": False
            },
            "logging": {
                "level": "INFO",
                "log_dir": "driver_monitoring_logs",
                "log_data": True,
                "log_events": True
            },
            "integration": {
                "api": {
                    "enabled": True,
                    "host": "0.0.0.0",
                    "port": 5000,
                    "base_url": "http://localhost:5000/api/",
                    "cors_origins": ["*"]
                }
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    update_config(default_config, yaml_config)
                    logger.info(f"Configuration loaded from {config_path}")
        elif os.path.exists('config.yaml'):
            # Try to load from config.yaml in current directory
            with open('config.yaml', 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    update_config(default_config, yaml_config)
                    logger.info("Configuration loaded from config.yaml")
        else:
            logger.warning("Using default configuration")

        # Legacy thresholds (maintain backwards compatibility)
        default_config["thresholds"] = {
            "drowsy_frames": default_config["thresholds"].get("drowsy_frames", 8),
            "yawn_frames": default_config["thresholds"].get("yawn_frames", 3), 
            "distraction_frames": default_config["thresholds"].get("distraction_frames", 6)
        }
        
        # Merge detection config with thresholds for backwards compatibility
        if "detection" in default_config:
            # Use detection section frame thresholds if available, otherwise use thresholds section
            detection = default_config["detection"]
            detection["drowsy_frames_threshold"] = detection.get("drowsy_frames_threshold", default_config["thresholds"]["drowsy_frames"])
            detection["yawn_frames_threshold"] = detection.get("yawn_frames_threshold", default_config["thresholds"]["yawn_frames"])
            detection["distraction_frames_threshold"] = detection.get("distraction_frames_threshold", default_config["thresholds"]["distraction_frames"])

        return default_config

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        logger.warning("Using default configuration")
        return DEFAULT_CONFIG

def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate critical configuration settings and set to default if invalid.
    
    Args:
        config: Configuration dictionary to validate
    """
    # Validate camera settings
    try:
        camera = config.get("camera", {})
        if not isinstance(camera.get("device_id"), int) or camera.get("device_id") < 0:
            logger.warning("Invalid camera device_id, using default")
            camera["device_id"] = DEFAULT_CONFIG["camera"]["device_id"]
        if not isinstance(camera.get("width"), int) or camera.get("width") <= 0:
            logger.warning("Invalid camera width, using default")
            camera["width"] = DEFAULT_CONFIG["camera"]["width"]
        if not isinstance(camera.get("height"), int) or camera.get("height") <= 0:
            logger.warning("Invalid camera height, using default")
            camera["height"] = DEFAULT_CONFIG["camera"]["height"]
    except Exception as e:
        logger.error(f"Error validating camera settings: {e}")
        config["camera"] = DEFAULT_CONFIG["camera"]

    # Validate thresholds
    try:
        thresholds = config.get("thresholds", {})
        for key in ["ear_lower", "ear_upper", "mar_lower", "mar_upper"]:
            value = thresholds.get(key)
            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"Invalid threshold for {key}, using default")
                thresholds[key] = DEFAULT_CONFIG["thresholds"][key]
        
        for key in ["drowsy_frames", "yawn_frames", "distraction_frames"]:
            value = thresholds.get(key)
            if not isinstance(value, int) or value < 1:
                logger.warning(f"Invalid threshold for {key}, using default")
                thresholds[key] = DEFAULT_CONFIG["thresholds"][key]
                
        for key in ["yaw_threshold", "pitch_threshold", "roll_threshold"]:
            value = thresholds.get(key)
            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"Invalid threshold for {key}, using default")
                thresholds[key] = DEFAULT_CONFIG["thresholds"][key]
    except Exception as e:
        logger.error(f"Error validating thresholds: {e}")
        config["thresholds"] = DEFAULT_CONFIG["thresholds"]

    # Validate head pose settings
    if "head_pose" not in config:
        config["head_pose"] = DEFAULT_CONFIG["head_pose"]
    
    # Validate robustness settings
    if "robustness" not in config:
        config["robustness"] = DEFAULT_CONFIG["robustness"]

def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get a value from a nested configuration dictionary using a dot-separated path.
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated path (e.g., "camera.width")
        default: Default value if key is not found
        
    Returns:
        Value from the configuration or default if not found
    """
    try:
        keys = key_path.split('.')
        value = config
        for key in keys:
            value = value.get(key, {})
        
        # Check if we've reached a leaf node or found nothing
        if value == {} and len(keys) > 0:
            return default
        return value
    except Exception as e:
        logger.error(f"Error getting config value for {key_path}: {e}")
        return default

def save_config(config: Dict[str, Any], config_path: str = DEFAULT_CONFIG_PATH) -> bool:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration dictionary to save
        config_path: Path to save the configuration file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        logger.info(f"Saved configuration to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False


class ConfigLoader:
    """
    Configuration loader class for the EyeDTrack system.
    Provides easy access to configuration settings.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        return load_config(self.config_path)
    
    def get_config(self) -> Dict[str, Any]:
        """Get the loaded configuration"""
        return self.config
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value by key path"""
        return get_config_value(self.config, key_path, default)
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self.config = self.load_config()
    
    def save(self) -> bool:
        """Save current configuration to file"""
        return save_config(self.config, self.config_path) 