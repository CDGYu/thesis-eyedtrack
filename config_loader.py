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
    "detection": {
        "use_improved_dlib": True,
        "use_standalone_analyzer": True,
        "ear_threshold": 0.25,
        "mar_threshold": 0.6,
        "yaw_threshold": 35,
        "pitch_threshold": 25
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
            "enabled": True,
            "host": "0.0.0.0",
            "port": 5000,
            "base_url": "http://localhost:5000/api/",
            "api_key": "",
            "cors_origins": ["*"]
        },
        "mqtt": {
            "enabled": False,
            "broker": "localhost",
            "port": 1883,
            "topic": "driver_monitoring"
        },
        "database": {
            "enabled": False,
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "eyedtrack_db",
            "username": "root",
            "password": "",
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600
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


def _load_dotenv(dotenv_path=None):
    """Minimal .env loader (no external dependency). For each ``KEY=VALUE`` line, set
    os.environ only if KEY is not already in the real environment (a real env var always
    wins). Looks for a .env next to this file by default; silently no-ops if it is missing
    or unreadable. Lets the DB password live in a gitignored .env instead of the shell."""
    path = dotenv_path or os.path.join(CURRENT_DIR, '.env')
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        logger.warning(f"Could not read .env file at {path}: {e}")


def load_config(config_path=None):
    """Load configuration: start from DEFAULT_CONFIG and deep-merge YAML overrides on top.

    Single source of truth is the module-level DEFAULT_CONFIG. The YAML file only needs to
    specify the keys it wants to override; everything else falls back to the defaults.
    """
    _load_dotenv()  # populate os.environ from a local .env (real env wins) before reading DB_* vars
    config = copy.deepcopy(DEFAULT_CONFIG)
    try:
        # Pick the config file: explicit path first, then ./config.yaml.
        path = None
        if config_path and os.path.exists(config_path):
            path = config_path
        elif os.path.exists('config.yaml'):
            path = 'config.yaml'

        if path:
            with open(path, 'r') as f:
                yaml_config = yaml.safe_load(f)
            if yaml_config:
                update_config(config, yaml_config)
                logger.info(f"Configuration loaded from {path}")
        else:
            logger.warning("No config file found; using default configuration")

        # Backfill the detection frame-count thresholds from the `thresholds` section
        # when not explicitly set, so both naming schemes resolve (non-destructive).
        detection = config.setdefault("detection", {})
        thresholds = config.get("thresholds", {})
        detection.setdefault("drowsy_frames_threshold", thresholds.get("drowsy_frames", 8))
        detection.setdefault("yawn_frames_threshold", thresholds.get("yawn_frames", 3))
        detection.setdefault("distraction_frames_threshold", thresholds.get("distraction_frames", 6))

        # Environment-variable overrides for the database connection. Lets the secret
        # (the password especially) stay OUT of the tracked config.yaml: any EYEDTRACK_DB_*
        # var that is set wins over the file value.
        database = config.setdefault("integration", {}).setdefault("database", {})
        db_env_overrides = {
            "EYEDTRACK_DB_HOST": "host",
            "EYEDTRACK_DB_PORT": "port",
            "EYEDTRACK_DB_NAME": "database",
            "EYEDTRACK_DB_USER": "username",
            "EYEDTRACK_DB_PASSWORD": "password",
        }
        for env_key, cfg_key in db_env_overrides.items():
            env_val = os.environ.get(env_key)
            if env_val not in (None, ""):
                database[cfg_key] = int(env_val) if cfg_key == "port" else env_val

        return config

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        logger.warning("Using default configuration")
        return copy.deepcopy(DEFAULT_CONFIG)

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