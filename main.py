from flask import Flask, jsonify, send_from_directory, request
from api.test_auth import auth_bp
from api.utils import create_response
from api.middleware import check_api_key
from api.state import state, connection_monitor
from api.routes.user_routes import session_bp
import threading
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')

# Start connection monitor in background thread
monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
monitor_thread.start()

# Register global authentication middleware
@app.before_request
def authenticate():
    # Skip authentication for static files
    if request.path.startswith('/'):
        path = request.path[1:]  # Remove leading slash
        if os.path.exists(os.path.join(app.static_folder, path)):
            return None
    
    result = check_api_key()
    if result is not None:
        return result

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
app.register_blueprint(session_bp, url_prefix='/api/v1')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return create_response(
        success=False,
        message="API Error",
        error="Endpoint not found",
        status_code=404
    )

@app.errorhandler(405)
def method_not_allowed(error):
    return create_response(
        success=False,
        message="API Error",
        error="Method not allowed",
        status_code=405
    )

@app.errorhandler(500)
def internal_server_error(error):
    return create_response(
        success=False,
        message="API Error",
        error="Internal server error",
        status_code=500
    )

# Root endpoint
@app.route('/')
def index():
    return create_response(
        message="Welcome to the AutoCheckin API",
        data={
            "version": "1.0",
            "endpoints": {
                "auth_test": "/api/v1/auth/test",
                "status": "/api/v1/status",
                "state": "/api/v1/state",
                "refresh": "/api/v1/refresh",
                "refresh_session": "/api/v1/refresh-session/<email>",
                "fetch_users": "/api/v1/fetch-users"
            },
            "status": {
                "connected": state.is_connected()
            }
        }
    )

# Status endpoint
@app.route('/api/v1/status')
def status():
    return create_response(
        message="API Status",
        data={
            "connected": state.is_connected()
        }
    )

# Global state endpoint
@app.route('/api/v1/state')
def get_state():
    return create_response(
        message="Global State",
        data={
            "connected": state.is_connected(),
            "stored_data": state.data
        }
    )

# Serve favicon.ico from public folder
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')

# Serve favicon.svg from public folder
@app.route('/favicon.svg')
def favicon_svg():
    return send_from_directory(app.static_folder, 'favicon.svg')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    
    app.run(host=host, port=port, debug=debug)
