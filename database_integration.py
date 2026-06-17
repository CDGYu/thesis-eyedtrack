"""
Database-backed REST endpoints for the EyeDTrack mobile app.

This module exposes a Flask **Blueprint** (`db_bp`) that serves driver-behavior history and
dashboard summaries from the MySQL persistence layer (``utils/db_manager.py`` +
``models/schema.py``).

It deliberately does **not** run its own Flask server or open its own database connection.
``main.py`` owns the Flask app, the ``DatabaseManager``, and the active monitoring session, and
shares them with this blueprint via :func:`attach_database`. That avoids the old design's bugs
(a second Flask app fighting for port 5000, a mocked SocketIO worker emitting fake data, and
calls to ``DatabaseManager`` methods that never existed).

When MySQL is disabled (``integration.database.enabled: false``) or unreachable, every endpoint
responds with HTTP 503 and a clear message instead of crashing.

Endpoints (all read-only except cleanup):
    GET  /api/db/health              -> is persistence active?
    GET  /api/db/behaviors/recent    -> recent behaviors (?hours, ?limit)
    GET  /api/db/dashboard/summary   -> aggregated risk dashboard (?hours)
    GET  /api/db/session/summary     -> summary for the current monitoring session (?session_id)
    POST /api/db/cleanup             -> delete data older than N days (?days)
"""

import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

db_bp = Blueprint("database", __name__)

# Populated by main.initialize_system() through attach_database(). Held in a dict so the
# reference can be swapped at runtime without re-importing the module.
_state = {"manager": None, "session_id": None}


def attach_database(db_manager, session_id):
    """Wire the shared DatabaseManager and active monitoring session into the blueprint.

    Call with ``(None, None)`` when persistence is disabled — the endpoints then report 503.
    """
    _state["manager"] = db_manager
    _state["session_id"] = session_id
    if db_manager is not None:
        logger.info("Database blueprint attached (session %s)", session_id)
    else:
        logger.info("Database blueprint attached in disabled mode (no MySQL)")


def _require_manager():
    """Return ``(manager, None)`` when available, else ``(None, <503 response tuple>)``."""
    manager = _state["manager"]
    if manager is None:
        response = jsonify({
            "success": False,
            "error": "Database persistence is disabled or unavailable",
            "hint": "Set integration.database.enabled: true in config.yaml and ensure MySQL is reachable",
        })
        return None, (response, 503)
    return manager, None


@db_bp.route("/api/db/health", methods=["GET"])
def db_health():
    """Report whether MySQL persistence is active and which session is logging."""
    return jsonify({
        "success": True,
        "database_enabled": _state["manager"] is not None,
        "session_id": _state["session_id"],
        "timestamp": datetime.now().isoformat(),
    }), 200


@db_bp.route("/api/db/behaviors/recent", methods=["GET"])
def recent_behaviors():
    """Recent driver behaviors. Query params: ``hours`` (default 24), ``limit`` (default 100)."""
    manager, err = _require_manager()
    if err:
        return err

    hours = request.args.get("hours", default=24, type=int)
    limit = request.args.get("limit", default=100, type=int)
    try:
        behaviors = manager.get_recent_behaviors(hours=hours, limit=limit)
        return jsonify({
            "success": True,
            "behaviors": behaviors,
            "returned_count": len(behaviors),
            "hours": hours,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error("recent_behaviors failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@db_bp.route("/api/db/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """Aggregate recent behaviors into a mobile dashboard summary. Query param: ``hours`` (default 24)."""
    manager, err = _require_manager()
    if err:
        return err

    hours = request.args.get("hours", default=24, type=int)
    try:
        # get_recent_behaviors is the real API; aggregate the window in-process.
        behaviors = manager.get_recent_behaviors(hours=hours, limit=100000)

        counts = {"drowsy": 0, "yawning": 0, "distracted": 0}
        ear_vals, mar_vals, conf_vals = [], [], []
        for b in behaviors:
            name = b.get("behavior")
            if name in counts:
                counts[name] += 1
            if b.get("ear") is not None:
                ear_vals.append(b["ear"])
            if b.get("mar") is not None:
                mar_vals.append(b["mar"])
            if b.get("confidence") is not None:
                conf_vals.append(b["confidence"])

        # Weight drowsiness highest, then distraction, then yawning.
        risk_score = min(100.0, counts["drowsy"] * 2 + counts["distracted"] * 1.5 + counts["yawning"] * 1.2)
        if risk_score > 60:
            status, message = "high_risk", "High risk detected - please take a break"
        elif risk_score > 30:
            status, message = "moderate_risk", "Moderate risk - stay alert"
        else:
            status, message = "safe", "Safe driving detected"

        def avg(values):
            return round(sum(values) / len(values), 3) if values else 0.0

        return jsonify({
            "success": True,
            "summary": {
                "safety_status": status,
                "safety_message": message,
                "risk_score": round(risk_score, 1),
                "time_period_hours": hours,
                "total_incidents": len(behaviors),
                "incident_breakdown": counts,
                "averages": {"ear": avg(ear_vals), "mar": avg(mar_vals), "confidence": avg(conf_vals)},
                "last_updated": datetime.now().isoformat(),
            },
        }), 200
    except Exception as e:
        logger.error("dashboard_summary failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@db_bp.route("/api/db/session/summary", methods=["GET"])
def session_summary():
    """Summary for the current monitoring session (or ``?session_id=`` to override)."""
    manager, err = _require_manager()
    if err:
        return err

    session_id = request.args.get("session_id", default=_state["session_id"], type=str)
    if not session_id:
        return jsonify({"success": False, "error": "No active monitoring session"}), 404
    try:
        summary = manager.get_session_summary(session_id)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error("session_summary failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@db_bp.route("/api/db/cleanup", methods=["POST"])
def cleanup_old_data():
    """Maintenance: delete monitoring data older than N days. Query/body param: ``days`` (default 30)."""
    manager, err = _require_manager()
    if err:
        return err

    days = request.args.get("days", default=30, type=int)
    try:
        manager.cleanup_old_data(days=days)
        return jsonify({
            "success": True,
            "message": f"Deleted monitoring data older than {days} days",
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error("cleanup_old_data failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
