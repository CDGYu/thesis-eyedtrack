"""
Enhanced API server for mobile app integration
Add this to your existing database_integration.py or create as mobile_api.py
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import base64
import cv2
import numpy as np
import threading
import time
from datetime import datetime, timedelta
import logging

from database_integration import DatabaseManager
from main import run_driver_monitoring  # Your main monitoring function

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database manager
db_manager = DatabaseManager()

# Global variables for real-time monitoring
monitoring_active = False
monitoring_thread = None
latest_frame = None
latest_results = None

logger = logging.getLogger(__name__)

class MobileAPIServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.monitoring_active = False
        
    def start_monitoring_session(self):
        """Start a new monitoring session"""
        global monitoring_active, monitoring_thread
        
        if not monitoring_active:
            monitoring_active = True
            monitoring_thread = threading.Thread(
                target=self._monitoring_worker,
                daemon=True
            )
            monitoring_thread.start()
            return True
        return False
    
    def stop_monitoring_session(self):
        """Stop the current monitoring session"""
        global monitoring_active
        monitoring_active = False
        return True
    
    def _monitoring_worker(self):
        """Background worker for monitoring (simplified version)"""
        # This would integrate with your main monitoring pipeline
        # For now, we'll simulate data
        while monitoring_active:
            # In real implementation, this would get data from your main pipeline
            # You'd need to modify your main.py to expose results via a queue or callback
            
            # Simulate monitoring data
            mock_data = {
                "timestamp": datetime.now().isoformat(),
                "behavior": "attentive driver",
                "confidence": 0.85,
                "is_risky": False,
                "ear": 0.25,
                "mar": 0.15,
                "head_pose": {"pitch": 2.1, "yaw": -1.5, "roll": 0.8},
                "session_id": "mobile_session_" + str(int(time.time()))
            }
            
            # Emit to connected mobile clients
            socketio.emit('monitoring_update', mock_data, namespace='/mobile')
            
            # Log to database if risky
            if mock_data.get('is_risky'):
                db_manager.log_risky_behavior(mock_data)
            
            time.sleep(1)  # Update every second

# REST API Endpoints
@app.route('/api/mobile/session/start', methods=['POST'])
def start_session():
    """Start a new monitoring session"""
    try:
        api_server = MobileAPIServer()
        success = api_server.start_monitoring_session()
        
        if success:
            session_data = {
                "session_id": f"mobile_session_{int(time.time())}",
                "start_time": datetime.now().isoformat(),
                "status": "active"
            }
            return jsonify({
                "success": True,
                "session": session_data,
                "message": "Monitoring session started"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Session already active"
            }), 400
            
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/mobile/session/stop', methods=['POST'])
def stop_session():
    """Stop the current monitoring session"""
    try:
        api_server = MobileAPIServer()
        success = api_server.stop_monitoring_session()
        
        return jsonify({
            "success": True,
            "message": "Monitoring session stopped"
        })
        
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/mobile/behaviors/recent', methods=['GET'])
def get_recent_behaviors():
    """Get recent risky behaviors for mobile dashboard"""
    try:
        # Get time range from query params
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Calculate start time
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Get behaviors from database
        behaviors = db_manager.get_risky_behaviors(
            start_time=start_time,
            limit=limit
        )
        
        # Format for mobile consumption
        mobile_behaviors = []
        for behavior in behaviors:
            mobile_behavior = {
                "id": behavior.get("id"),
                "timestamp": behavior.get("timestamp"),
                "behavior": behavior.get("behavior"),
                "confidence": behavior.get("confidence"),
                "risk_level": "high" if behavior.get("confidence", 0) > 0.7 else "moderate",
                "metrics": {
                    "ear": behavior.get("ear"),
                    "mar": behavior.get("mar"),
                    "head_pose": behavior.get("head_pose")
                }
            }
            mobile_behaviors.append(mobile_behavior)
        
        return jsonify({
            "success": True,
            "behaviors": mobile_behaviors,
            "total_count": len(mobile_behaviors)
        })
        
    except Exception as e:
        logger.error(f"Error getting recent behaviors: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/mobile/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get dashboard summary for mobile app"""
    try:
        # Get time range from query params
        hours = request.args.get('hours', 24, type=int)
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Get summary from database
        summary = db_manager.get_behavior_summary(start_time=start_time)
        
        # Calculate additional metrics for mobile dashboard
        total_behaviors = summary.get("total_count", 0)
        risk_score = 0
        
        if total_behaviors > 0:
            drowsy_pct = (summary.get("drowsy_count", 0) / total_behaviors) * 100
            distracted_pct = (summary.get("distracted_count", 0) / total_behaviors) * 100
            yawning_pct = (summary.get("yawning_count", 0) / total_behaviors) * 100
            
            # Calculate overall risk score
            risk_score = min(100, drowsy_pct * 2 + distracted_pct * 1.5 + yawning_pct * 1.2)
        
        # Determine safety status
        if risk_score > 60:
            safety_status = "high_risk"
            safety_message = "High risk detected - please take a break"
        elif risk_score > 30:
            safety_status = "moderate_risk"
            safety_message = "Moderate risk - stay alert"
        else:
            safety_status = "safe"
            safety_message = "Safe driving detected"
        
        mobile_summary = {
            "safety_status": safety_status,
            "safety_message": safety_message,
            "risk_score": round(risk_score, 1),
            "time_period_hours": hours,
            "total_incidents": total_behaviors,
            "incident_breakdown": {
                "drowsy": summary.get("drowsy_count", 0),
                "distracted": summary.get("distracted_count", 0),
                "yawning": summary.get("yawning_count", 0)
            },
            "averages": {
                "ear": round(summary.get("avg_ear", 0), 3),
                "mar": round(summary.get("avg_mar", 0), 3),
                "confidence": round(summary.get("avg_confidence", 0), 3)
            },
            "behavior_counts": summary.get("behavior_counts", {}),
            "last_updated": datetime.now().isoformat()
        }
        
        return jsonify({
            "success": True,
            "summary": mobile_summary
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/mobile/upload-frame', methods=['POST'])
def upload_frame():
    """Accept frame upload from mobile app for analysis"""
    try:
        data = request.get_json()
        
        if 'frame' not in data:
            return jsonify({
                "success": False,
                "message": "No frame data provided"
            }), 400
        
        # Decode base64 frame
        frame_data = base64.b64decode(data['frame'])
        np_array = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({
                "success": False,
                "message": "Invalid frame data"
            }), 400
        
        # TODO: Process frame with your monitoring pipeline
        # For now, return mock analysis
        analysis_result = {
            "behavior": "attentive driver",
            "confidence": 0.85,
            "is_risky": False,
            "risk_level": "safe",
            "metrics": {
                "ear": 0.25,
                "mar": 0.15
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Log to database if risky
        if analysis_result.get('is_risky'):
            db_manager.log_risky_behavior(analysis_result)
        
        return jsonify({
            "success": True,
            "analysis": analysis_result
        })
        
    except Exception as e:
        logger.error(f"Error processing uploaded frame: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# WebSocket Events for Real-time Communication
@socketio.on('connect', namespace='/mobile')
def mobile_connect():
    """Handle mobile client connection"""
    print(f"Mobile client connected: {request.sid}")
    emit('connected', {'message': 'Connected to monitoring server'})

@socketio.on('disconnect', namespace='/mobile')
def mobile_disconnect():
    """Handle mobile client disconnection"""
    print(f"Mobile client disconnected: {request.sid}")

@socketio.on('start_monitoring', namespace='/mobile')
def handle_start_monitoring(data):
    """Handle start monitoring request from mobile"""
    try:
        api_server = MobileAPIServer()
        success = api_server.start_monitoring_session()
        
        if success:
            emit('monitoring_started', {
                'success': True,
                'session_id': f"mobile_session_{int(time.time())}",
                'message': 'Monitoring started successfully'
            })
        else:
            emit('monitoring_error', {
                'success': False,
                'message': 'Session already active'
            })
            
    except Exception as e:
        emit('monitoring_error', {
            'success': False,
            'message': str(e)
        })

@socketio.on('stop_monitoring', namespace='/mobile')
def handle_stop_monitoring(data):
    """Handle stop monitoring request from mobile"""
    try:
        api_server = MobileAPIServer()
        api_server.stop_monitoring_session()
        
        emit('monitoring_stopped', {
            'success': True,
            'message': 'Monitoring stopped successfully'
        })
        
    except Exception as e:
        emit('monitoring_error', {
            'success': False,
            'message': str(e)
        })

if __name__ == '__main__':
    # Start the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)