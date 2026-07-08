#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EyeDTrack: Real-Time Driver Attention Monitoring System Backend API
"""

import cv2
import numpy as np
import time
import os
import logging
import base64
from datetime import datetime
from pathlib import Path
import sys
import traceback
import atexit
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import json
from flask_compress import Compress
from typing import Dict, Any, Optional

# Import project modules
from frame_processor import OptimizedFrameProcessor
from event_logger import log_event, get_event_type
from config_loader import load_config, DEFAULT_CONFIG_PATH
from database_integration import db_bp, attach_database
# ImprovedFaceAnalyzer is imported by frame_processor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Configure CORS with all methods and headers allowed
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "User-Agent"],
        "expose_headers": ["Content-Type", "Authorization"],
        
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Add response compression
Compress(app)

# Register the MySQL-backed mobile/dashboard endpoints (/api/db/*). The blueprint is always
# registered; it returns 503 until attach_database() wires in a live DatabaseManager.
app.register_blueprint(db_bp)

# Optional MySQL persistence — initialized in initialize_system() only if
# integration.database.enabled is true. Left as None means "file logging only".
db_manager = None
db_session_id = None

# Last recorded behavior state (is_drowsy, is_yawning, is_distracted). Used to log/persist
# only when the behavior changes (edge-triggered) instead of on every frame.
_last_behavior_state = (False, False, False)


def _db_behavior_rows(result):
    """Map a process_frame() result into one flat behavior dict per ACTIVE behavior,
    shaped for db_manager.log_behavior() (one row per active behavior)."""
    bc = result.get('behavior_category', {})
    metrics = result.get('metrics', {})
    head_pose = metrics.get('head_pose') or [0.0, 0.0, 0.0]
    hp = {
        'yaw': head_pose[0] if len(head_pose) > 0 else 0.0,
        'pitch': head_pose[1] if len(head_pose) > 1 else 0.0,
        'roll': head_pose[2] if len(head_pose) > 2 else 0.0,
    }
    rows = []
    for name, key in (('drowsy', 'is_drowsy'), ('yawning', 'is_yawning'), ('distracted', 'is_distracted')):
        if bc.get(key):
            rows.append({
                'behavior': name,
                'confidence': result.get('behavior_confidence', 0.0),
                'is_risky': True,
                'ear': metrics.get('ear'),
                'mar': metrics.get('mar'),
                'head_pose': hp,
                'additional_metrics': {'behavior_category': bc},
            })
    return rows


# Severity written to alert_logs for each behavior (AlertLog.severity is varchar(20)).
_ALERT_SEVERITY = {'drowsy': 'high', 'distracted': 'high', 'yawning': 'medium'}


def _persist_onsets(result, newly_on):
    """Persist each JUST-turned-on (onset) behavior to MySQL: one driver_behaviors row AND
    one alert_logs row per behavior. No-op unless persistence is enabled. Never raises — a DB
    failure must not break the /api/process_frame response (file logging stays authoritative)."""
    if db_manager is None or db_session_id is None or not newly_on:
        return
    try:
        for row in _db_behavior_rows(result):
            if row['behavior'] not in newly_on:
                continue
            db_manager.log_behavior(db_session_id, row)
            db_manager.log_alert(db_session_id, {
                'type': row['behavior'],
                'severity': _ALERT_SEVERITY.get(row['behavior'], 'medium'),
                'message': f"{row['behavior']} detected (confidence {row['confidence']:.2f})",
            })
    except Exception as db_err:
        logger.error(f"MySQL onset persist failed: {db_err}")


def _end_db_session_on_exit(manager, sid):
    """atexit hook: mark the monitoring session completed on shutdown. Best-effort — it will
    not run on a forced kill (taskkill /F), but does on a normal exit / Ctrl+C. Guarded so a
    failure here never blocks interpreter exit."""
    try:
        if manager is not None and sid is not None:
            manager.end_monitoring_session(sid)
            logger.info(f"Closed monitoring session {sid} on shutdown")
    except Exception as e:
        logger.error(f"Failed to close monitoring session {sid}: {e}")


@app.before_request
def log_request_info():
    """Log details about incoming requests"""
    logger.debug("Request Headers: %s", dict(request.headers))
    logger.debug("Request Method: %s", request.method)
    logger.debug("Request URL: %s", request.url)
    logger.debug("Request Remote Addr: %s", request.remote_addr)
    if request.method == 'OPTIONS':
        logger.debug("Handling OPTIONS request")

@app.after_request
def after_request(response):
    """Add CORS headers to every response"""
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept, User-Agent',
        'Access-Control-Expose-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '3600',
    }
    
    for key, value in headers.items():
        response.headers.add(key, value)
    
    logger.debug("Response Status: %s", response.status)
    logger.debug("Response Headers: %s", dict(response.headers))
    return response

def base64_to_cv2(base64_string):
    """Convert base64 string to OpenCV image"""
    try:
        # Remove data URL prefix if present
        if 'base64,' in base64_string:
            base64_string = base64_string.split('base64,')[1]
        
        # Decode base64 string
        img_data = base64.b64decode(base64_string)
        
        # Convert to numpy array
        nparr = np.frombuffer(img_data, np.uint8)
        
        # Decode image
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Failed to decode image")
            
        return img
    except Exception as e:
        logger.error(f"Error converting base64 to image: {e}")
        raise

def initialize_system(config_path=DEFAULT_CONFIG_PATH):
    """Initialize the driver monitoring system"""
    global frame_processor, config, log_dir, session_id, db_manager, db_session_id

    try:
        # Load configuration
        config = load_config(config_path)
        
        # Configure logging
        logging.getLogger().setLevel(getattr(logging, config["logging"]["level"]))
        
        # Create log directory
        log_dir = Path(config["logging"]["log_dir"])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create video directory
        video_dir = log_dir / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique session ID
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize frame processor
        frame_processor = OptimizedFrameProcessor(config)

        # Optional MySQL persistence (dual-write alongside the JSON logs).
        # Off unless integration.database.enabled is true; a DB failure must NOT
        # take down the server, so it falls back to file-only logging.
        db_manager = None
        db_session_id = None
        db_cfg = config.get("integration", {}).get("database", {})
        if db_cfg.get("enabled"):
            try:
                from utils.db_manager import DatabaseManager
                db_manager = DatabaseManager(config)
                db_session_id = db_manager.create_monitoring_session(
                    device_info={"source": "eyedtrack-api"}
                )
                logger.info(f"✅ MySQL persistence enabled (db session {db_session_id})")
                atexit.register(_end_db_session_on_exit, db_manager, db_session_id)
            except Exception as db_err:
                logger.error(f"⚠️ MySQL persistence disabled — DatabaseManager init failed: {db_err}")
                db_manager = None
                db_session_id = None
        else:
            logger.info("MySQL persistence disabled (integration.database.enabled is false)")

        # Share the manager + session with the /api/db/* blueprint (None => endpoints return 503).
        attach_database(db_manager, db_session_id)

        logger.info(f"Driver monitoring system initialized. Using log directory: {log_dir}")
        return config
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {str(e)}", exc_info=True)
        raise

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'message': 'Server is running',
            'remote_addr': request.remote_addr
        }
        logger.info(f"Health check successful: {health_data}")
        return jsonify(health_data), 200
    except Exception as e:
        error_data = {
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'message': str(e),
            'remote_addr': request.remote_addr
        }
        logger.error(f"Health check failed: {error_data}")
        return jsonify(error_data), 500

@app.route('/api/test_behavior', methods=['GET'])
def test_behavior():
    """Test endpoint that always returns drowsy behavior"""
    logger.info("🔴 TEST ENDPOINT: Always serving DROWSY behavior")
    
    return jsonify({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'behavior_flags': {
            'is_drowsy': True,
            'is_yawning': False,
            'is_distracted': False
        },
        'metrics': {
            'ear': 0.15,  # Low EAR indicates drowsiness
            'mar': 0.6,
            'pitch': 0.0,
            'yaw': 0.0
        },
        'behavior_output': 'TEST ENDPOINT - DROWSY ALWAYS ACTIVE',
        'behavior_confidence': 1.0
    }), 200

@app.route('/api/latest_behavior', methods=['GET'])
def get_latest_behavior():
    """Get the latest behavior detection from driver_monitoring.json"""
    try:
        log_file_path = os.path.join(str(log_dir), "driver_monitoring.json")
        
        if not os.path.exists(log_file_path):
            logger.warning(f"Driver monitoring log file not found: {log_file_path}")
            return jsonify({
                'success': False,
                'error': 'No monitoring data available',
                'behavior_category': {
                    'is_drowsy': False,
                    'is_yawning': False,
                    'is_distracted': False
                }
            }), 404
        
        # Read the latest entry from the log file
        latest_entry = None
        try:
            with open(log_file_path, 'r') as f:
                lines = f.readlines()
                # Get the last non-empty line
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        latest_entry = json.loads(line)
                        break
        except Exception as e:
            logger.error(f"Error reading driver monitoring log: {e}")
            return jsonify({
                'success': False,
                'error': f'Error reading log file: {str(e)}',
                'behavior_category': {
                    'is_drowsy': False,
                    'is_yawning': False,
                    'is_distracted': False
                }
            }), 500
        
        if not latest_entry:
            logger.warning("No entries found in driver monitoring log")
            return jsonify({
                'success': False,
                'error': 'No monitoring entries found',
                'behavior_category': {
                    'is_drowsy': False,
                    'is_yawning': False,
                    'is_distracted': False
                }
            }), 404
        
        # Extract behavior information
        behavior_category = latest_entry.get("behavior_category", {})
        timestamp = latest_entry.get("timestamp", datetime.now().isoformat())
        
        # Log the behavior detection with detailed metrics
        is_drowsy = behavior_category.get("is_drowsy", False)
        is_yawning = behavior_category.get("is_yawning", False)
        is_distracted = behavior_category.get("is_distracted", False)
        
        # Extract metrics for detailed logging
        metrics = latest_entry.get("metrics", {})
        ear = metrics.get("ear", 0)
        mar = metrics.get("mar", 0)
        head_pose = metrics.get("head_pose", [0, 0, 0])
        yaw = head_pose[0] if len(head_pose) > 0 else 0
        pitch = head_pose[1] if len(head_pose) > 1 else 0
        
        if is_drowsy or is_yawning or is_distracted:
            behaviors = []
            if is_drowsy: behaviors.append("DROWSY")
            if is_yawning: behaviors.append("YAWNING")
            if is_distracted: behaviors.append("DISTRACTED")
            logger.warning(f"🚨 RISKY BEHAVIOR DETECTED: {', '.join(behaviors)} | EAR={ear:.3f} MAR={mar:.3f} Yaw={yaw:.1f}° Pitch={pitch:.1f}°")
        else:
            logger.debug(f"✅ Normal behavior | EAR={ear:.3f} MAR={mar:.3f} Yaw={yaw:.1f}° Pitch={pitch:.1f}°")
        
        return jsonify({
            'success': True,
            'behavior_category': behavior_category,
            'behavior_confidence': latest_entry.get("behavior_confidence", 0.0),
            'timestamp': timestamp,
            'metrics': latest_entry.get("metrics", {}),
            'entry_age_seconds': (datetime.now() - datetime.fromisoformat(timestamp.replace('Z', '+00:00').split('.')[0])).total_seconds() if timestamp else 0
        }), 200
            
    except Exception as e:
        logger.error(f"Error getting latest behavior: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'behavior_category': {
                'is_drowsy': False,
                'is_yawning': False,
                'is_distracted': False
            }
        }), 500

@app.route('/api/alert_history', methods=['GET'])
def get_alert_history():
    """Return recent risky behavior alerts from driver_monitoring.json.

    Query params:
      - limit (int): max number of alerts to return (default 100)
    """
    try:
        limit = request.args.get('limit', default=100, type=int)

        log_file_path = os.path.join(str(log_dir), "driver_monitoring.json")
        abs_log_path = os.path.abspath(log_file_path)
        if not os.path.exists(log_file_path):
            logger.warning(f"Driver monitoring log file not found: {log_file_path}")
            return jsonify({
                'success': True,
                'alerts': [],
                'total_count': 0,
                'returned_count': 0,
                'latest_timestamp': None,
                'api_timestamp': datetime.now().isoformat(),
                'log_file_path': abs_log_path,
                'file_exists': False,
                'file_size_bytes': 0
            }), 200

        alerts = []
        total_risky = 0

        with open(log_file_path, 'r') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('behavior_output') == 'RISKY BEHAVIOR DETECTED':
                        total_risky += 1
                        alerts.append(entry)
                except Exception as e:
                    logger.debug(f"Skipping unparsable log line: {e}")

        def parse_ts(ts: str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00').split('.')[0])
            except Exception:
                return datetime.min

        alerts.sort(key=lambda a: parse_ts(a.get('timestamp', '')), reverse=True)
        limited_alerts = alerts[: max(0, limit)]
        latest_ts = limited_alerts[0].get('timestamp') if limited_alerts else None

        file_size = 0
        try:
            file_size = os.path.getsize(log_file_path)
        except Exception:
            file_size = 0

        return jsonify({
            'success': True,
            'alerts': limited_alerts,
            'total_count': total_risky,
            'returned_count': len(limited_alerts),
            'latest_timestamp': latest_ts,
            'api_timestamp': datetime.now().isoformat(),
            'log_file_path': abs_log_path,
            'file_exists': True,
            'file_size_bytes': file_size
        }), 200

    except Exception as e:
        logger.error(f"Error getting alert history: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'alerts': [],
            'total_count': 0,
            'returned_count': 0,
            'latest_timestamp': None,
            'api_timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/clear_alert_history', methods=['POST'])
def clear_alert_history():
    """Truncate driver_monitoring.json so the app sees an empty history."""
    try:
        log_file_path = os.path.join(str(log_dir), "driver_monitoring.json")
        if not os.path.exists(log_file_path):
            # Nothing to clear; report success so UI can refresh to empty
            return jsonify({
                'success': True,
                'message': 'No log file found; history already empty',
                'api_timestamp': datetime.now().isoformat()
            }), 200

        # Optionally collect stats before clearing
        total_lines = 0
        risky_before = 0
        try:
            with open(log_file_path, 'r') as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(line)
                        if obj.get('behavior_output') == 'RISKY BEHAVIOR DETECTED':
                            risky_before += 1
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Unable to scan log before clear: {e}")

        # Truncate file
        open(log_file_path, 'w').close()
        logger.info("driver_monitoring.json truncated via /api/clear_alert_history")

        return jsonify({
            'success': True,
            'message': 'Alert history cleared',
            'previous_total_entries': total_lines,
            'previous_risky_entries': risky_before,
            'api_timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error clearing alert history: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'api_timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/process_frame', methods=['POST'])
def process_frame():
    """Process a single frame of video data"""
    global session_id, _last_behavior_state
    
    logger.debug("Received frame processing request")
    logger.debug("Content-Type: %s", request.content_type)
    logger.debug("Content-Length: %s", request.content_length)
    
    try:
        # Get data from request. silent=True -> malformed JSON returns None (handled as 400
        # below) instead of raising a 400 that our except would turn into a 500.
        data = request.get_json(silent=True)
        logger.debug("Received data keys: %s", list(data.keys()) if data else None)
        
        if not data or 'frame' not in data:
            logger.error("No frame data provided in request")
            return jsonify({
                'success': False,
                'error': 'No frame data provided',
                'timestamp': datetime.now().isoformat()
            }), 400

        # Log frame data length
        frame_data = data['frame']
        logger.debug("Frame data length: %d", len(frame_data) if frame_data else 0)

        # Convert base64 frame to CV2 image. A decode failure means the client sent a bad
        # frame -> 400 (not 500), and we never echo internals back to the caller.
        try:
            frame = base64_to_cv2(data['frame'])
        except (ValueError, TypeError) as decode_err:
            logger.warning(f"Bad frame in /api/process_frame: {decode_err}")
            return jsonify({
                'success': False,
                'error': 'Invalid or undecodable frame',
                'timestamp': datetime.now().isoformat()
            }), 400
        logger.debug("Successfully converted frame to CV2 image. Shape: %s", frame.shape if frame is not None else None)
        
        # Process the frame
        result = frame_processor.process_frame(frame)
        logger.debug("Frame processing result: %s", result)
        
        # Format behaviors for response - FIX: Extract from correct structure
        behaviors = []
        behavior_category = result.get('behavior_category', {})
        if behavior_category.get('is_drowsy', False):
            behaviors.append('drowsy')
        if behavior_category.get('is_yawning', False):
            behaviors.append('yawning')
        if behavior_category.get('is_distracted', False):
            behaviors.append('distracted')
            
        # Record ONLY on a behavior-state change (edge-triggered) rather than every frame,
        # so the history and MySQL get one entry per transition instead of one per frame.
        current_state = (
            behavior_category.get('is_drowsy', False),
            behavior_category.get('is_yawning', False),
            behavior_category.get('is_distracted', False),
        )
        if current_state != _last_behavior_state:
            # File log: one record reflecting the new state (keeps /api/latest_behavior current).
            try:
                log_event(log_dir, get_event_type(result), result)
            except Exception as log_err:
                logger.error(f"File log_event failed: {log_err}")

            # MySQL: persist onsets (a driver_behaviors + an alert_logs row) for each behavior
            # that JUST turned on, if persistence is enabled.
            if any(current_state):
                names = ('drowsy', 'yawning', 'distracted')
                newly_on = {names[i] for i in range(3) if current_state[i] and not _last_behavior_state[i]}
                _persist_onsets(result, newly_on)

            _last_behavior_state = current_state

        # Format response for frontend - FIX: Extract metrics correctly
        metrics = result.get('metrics', {})
        response = {
            'success': True,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'behaviors': behaviors,
            'metrics': {
                'ear': metrics.get('ear', 0),
                'mar': metrics.get('mar', 0),
                'head_pose': metrics.get('head_pose', None)
            }
        }
        
        return jsonify(response)
        
    except Exception:
        # Genuine server-side failure: log the full traceback server-side only; do NOT leak
        # it (or the raw request body) back to the client.
        logger.exception("Unexpected error processing frame")
        return jsonify({
            'success': False,
            'error': 'Internal error processing frame',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/process_frame', methods=['POST'])
def process_frame_redirect():
    """Redirect /process_frame to /api/process_frame for backward compatibility"""
    return process_frame()

if __name__ == '__main__':
    try:
        # Initialize the system
        config = initialize_system()
        
        # Start the server
        host = config["integration"]["api"]["host"]
        port = config["integration"]["api"]["port"]
        
        logger.info(f"Starting server on {host}:{port}")
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)