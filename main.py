from flask import Flask, jsonify, send_from_directory, request
from api.test_auth import auth_bp
from api.utils import create_response, debug_log
from api.middleware import check_api_key
from api.state import state, connection_monitor
from api.routes.user_routes import session_bp
import threading
import os
from dotenv import load_dotenv
import asyncio
from scripts.auto_checkin_scheduler import start_scheduler
from scripts.auto_attendance_scheduler import initialize_scheduler
import time

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder="public", static_url_path="")


def start_background_tasks():
    """Start all background tasks in a way that prevents duplicate threads in debug mode"""
    if not os.environ.get("WERKZEUG_RUN_MAIN"):  # Only run in the main process
        return

    if os.environ.get("BACKGROUND_TASKS_STARTED"):  # Prevent duplicate starts
        return

    os.environ["BACKGROUND_TASKS_STARTED"] = "true"

    # Start connection monitor in background thread
    monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
    monitor_thread.start()

    # Start state monitoring thread
    def monitor_state():
        while True:
            debug_log("\n=== CURRENT STATE DATA ===")
            debug_log(str(state.data))
            debug_log("=========================\n")
            time.sleep(10)

    state_monitor_thread = threading.Thread(target=monitor_state, daemon=True)
    state_monitor_thread.start()

    # Start auto checkin scheduler in background thread
    def run_checkin_scheduler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_scheduler())

    # Start attendance scheduler in background thread
    def run_attendance_scheduler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            try:
                loop.run_until_complete(initialize_scheduler())
            except Exception as e:
                debug_log(f"Error in attendance scheduler: {str(e)}")
                # Sleep for a bit before retrying to avoid tight error loops
                time.sleep(5)

    debug_log("Starting auto checkin scheduler")
    checkin_thread = threading.Thread(target=run_checkin_scheduler, daemon=True)
    checkin_thread.start()

    debug_log("Starting attendance fetch scheduler")
    attendance_thread = threading.Thread(target=run_attendance_scheduler, daemon=True)
    attendance_thread.start()


# Start background tasks
start_background_tasks()


# Register global authentication middleware
@app.before_request
def authenticate():
    # Skip authentication for static files
    # if request.path.startswith('/'):
    #     path = request.path[1:]  # Remove leading slash
    #     if os.path.exists(os.path.join(app.static_folder, path)):
    #         return None

    result = check_api_key()
    if result is not None:
        return result


# Register blueprints
app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
app.register_blueprint(session_bp, url_prefix="/api/v1")


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return create_response(
        success=False, message="API Error", error="Endpoint not found", status_code=404
    )


@app.errorhandler(405)
def method_not_allowed(error):
    return create_response(
        success=False, message="API Error", error="Method not allowed", status_code=405
    )


@app.errorhandler(500)
def internal_server_error(error):
    return create_response(
        success=False,
        message="API Error",
        error="Internal server error",
        status_code=500,
    )


# Root endpoint
@app.route("/")
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
                "fetch_users": "/api/v1/fetch-users",
                "codes": "/api/v1/codes",
                "try_codes": "/api/v1/try-codes",
            },
            "status": {"connected": state.is_connected()},
        },
    )


# Status endpoint
@app.route("/api/v1/status")
def status():
    return create_response(
        message="API Status", data={"connected": state.is_connected()}
    )


# Global state endpoint
@app.route("/api/v1/state")
def get_state():
    stored_data = {
        "last_users_fetch": state.get_data("last_users_fetch"),
        "last_all_session_refresh": state.get_data("last_all_session_refresh"),
        "last_individual_session_refresh": state.get_data(
            "last_individual_session_refresh"
        ),
        "next_cycle_run_time": state.get_data("next_cycle_run_time"),
        "last_attendance_fetch_run": state.get_data("last_attendance_fetch_run"),
        "autoCheckinUsers": state.get_data("autoCheckinUsers"),
    }
    return create_response(
        message="Global State",
        data={"connected": state.is_connected(), "stored_data": stored_data},
    )


# Serve favicon.ico from public folder
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


# Serve favicon.svg from public folder
@app.route("/favicon.svg")
def favicon_svg():
    return send_from_directory(app.static_folder, "favicon.svg")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "::")
    debug = os.getenv("FLASK_DEBUG", "0") == "1"

    app.run(host=host, port=port, debug=debug)
