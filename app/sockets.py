from threading import Thread, Lock, Event
from app.routes import get_alerts, get_stats, manage_cameras
from . import socketio
from flask_socketio import emit
from flask import current_app
from datetime import datetime
import logging
from collections import deque

logger = logging.getLogger(__name__)
camera_streams = {}
processing_active = True
frame_lock = Lock()
latest_frames = {}
alert_queue = deque(maxlen=100)
camera_status = {}
# ================== WEBSOCKET HANDLERS ==================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info('Client connected')
    socketio.emit('connection_response', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat(),
        'active_cameras': len([c for c in camera_streams.values() if c.running])
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info('Client disconnected')

@socketio.on('request_stats')
def handle_stats_request():
    """Send current statistics."""
    app = current_app._get_current_object()
    
    with app.test_request_context('/'):
        stats_response = get_stats()  # Ensure get_stats is defined in your app
        stats = stats_response.json
        socketio.emit('stats_update', stats)

@socketio.on('request_camera_status')
def handle_camera_status_request():
    """Send camera status updates."""
    cameras_info = []
    for cam_id, cam in camera_streams.items():
        status = cam.get_status()
        with frame_lock:
            status['has_latest_frame'] = cam_id in latest_frames
        cameras_info.append(status)
    
    socketio.emit('camera_status_update', {
        'cameras': cameras_info,
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('request_camera_list')
def handle_camera_list_request():
    """Send list of all cameras."""
    app = current_app._get_current_object()
    
    with app.test_request_context('/'):
        cameras_response = manage_cameras()  # Ensure manage_cameras is defined in your app
        cameras_data = cameras_response.json
        socketio.emit('camera_list_update', cameras_data)

@socketio.on('ping')
def handle_ping():
    """Handle ping from client."""
    socketio.emit('pong', {
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('start_monitoring')
def handle_start_monitoring():
    """Handle start monitoring request."""
    logger.info("Monitoring started by client")
    socketio.emit('monitoring_status', {
        'active': True,
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('stop_monitoring')
def handle_stop_monitoring():
    """Handle stop monitoring request."""
    logger.info("Monitoring stopped by client")
    socketio.emit('monitoring_status', {
        'active': False,
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('request_alerts')
def handle_alerts_request(data):
    """Send alerts based on filters."""
    app = current_app._get_current_object()
    
    limit = data.get('limit', 50)
    behavior = data.get('behavior', None)
    reviewed = data.get('reviewed', None)
    
    with app.test_request_context(
        f'/api/alerts?limit={limit}' + 
        (f'&behavior={behavior}' if behavior else '') +
        (f'&reviewed={reviewed}' if reviewed is not None else '')
    ):
        alerts_response = get_alerts()  # Ensure get_alerts is defined in your app
        alerts = alerts_response.json
        socketio.emit('alerts_data', {
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        })
