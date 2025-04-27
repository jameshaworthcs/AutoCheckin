from flask import Flask, jsonify, send_from_directory, request, redirect
from api.test_auth import auth_bp
from api.utils import create_response, debug_log, read_local_user_data, write_local_user_data
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
import json
from scripts.local_user import refresh_local_user_session, try_local_user_codes
from scripts.local_code_fetcher import run_local_code_fetcher
from scripts.session_refresh import get_all_refresh_sessions

# Load environment variables
load_dotenv()

# Determine if running in local mode
AUTOCHECKIN_LOCAL = os.getenv("AUTOCHECKIN_LOCAL", "false").lower() == "true"
CHECKOUT_API_URL = os.getenv("CHECKOUT_API_URL", "") # Get base URL
LOCAL_CHECKOUT_API_URL = os.getenv("LOCAL_CHECKOUT_API_URL", "") # Get local base URL

app = Flask(__name__, static_folder="public", static_url_path="")


def start_background_tasks():
    """Start background tasks conditionally based on AUTOCHECKIN_LOCAL."""
    debug_log("\n=== Starting Background Tasks ===")

    if os.environ.get("BACKGROUND_TASKS_STARTED"):
        debug_log("Background tasks already started, skipping...")
        return

    os.environ["BACKGROUND_TASKS_STARTED"] = "true"

    try:
        # --- Tasks common to both modes (or adaptable) ---
        
        # Start connection monitor (seems useful in both modes)
        debug_log("Starting connection monitor...")
        monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
        monitor_thread.start()
        debug_log("Connection monitor started successfully")

        # State monitor (can be useful for debugging local mode too)
        def monitor_state_generic(): # Renamed to avoid conflict if state module changes
            debug_log("State monitor started")
            while True:
                try:
                    # In local mode, maybe log user.json content instead/additionally?
                    log_data = read_local_user_data() if AUTOCHECKIN_LOCAL else state.data
                    debug_log("\n=== CURRENT STATE/USER DATA ===")
                    debug_log(json.dumps(log_data, indent=2))
                    debug_log("=============================\n")
                    time.sleep(10)
                except Exception as e:
                    debug_log(f"Error in state/user monitor: {str(e)}")
                    time.sleep(5)  # Wait before retrying

        debug_log("Starting state/user monitor...")
        state_monitor_thread = threading.Thread(target=monitor_state_generic, daemon=True)
        state_monitor_thread.start()
        debug_log("State/user monitor started successfully")

        # --- Mode-specific tasks ---
        if AUTOCHECKIN_LOCAL:
            # Start Local Code Fetcher
            debug_log("Starting local code fetcher...")
            local_fetcher_thread = threading.Thread(target=run_local_code_fetcher, daemon=True)
            local_fetcher_thread.start()
            debug_log("Local code fetcher started successfully.")
        else:
            # Start Production Schedulers (Original Logic)
            
            # Start auto checkin scheduler
            def run_checkin_scheduler_prod():
                debug_log("Production auto checkin scheduler thread starting...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(start_scheduler())
                except Exception as e:
                    debug_log(f"Error in production checkin scheduler: {str(e)}")
                finally:
                    loop.close()

            debug_log("Starting production auto checkin scheduler...")
            checkin_thread_prod = threading.Thread(target=run_checkin_scheduler_prod, daemon=True)
            checkin_thread_prod.start()
            debug_log("Production auto checkin scheduler started successfully")

            # Start attendance scheduler
            def run_attendance_scheduler_prod():
                debug_log("Production attendance scheduler thread starting...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Assuming initialize_scheduler is async and might run repeatedly or loop internally
                try:
                     loop.run_until_complete(initialize_scheduler())
                except Exception as e:
                    debug_log(f"Error in production attendance scheduler: {str(e)}")
                    # Add sleep if it needs to retry? Original code had loop/retry logic.
                    # This part needs review based on how initialize_scheduler works.
                finally:
                    loop.close()

            debug_log("Starting production attendance fetch scheduler...")
            attendance_thread_prod = threading.Thread(
                target=run_attendance_scheduler_prod, daemon=True
            )
            attendance_thread_prod.start()
            debug_log("Production attendance scheduler started successfully")

        debug_log("=== All relevant background tasks started successfully ===\n")

    except Exception as e:
        debug_log(f"Error starting background tasks: {str(e)}")
        os.environ.pop("BACKGROUND_TASKS_STARTED", None)
        raise


# Start background tasks
try:
    start_background_tasks()
except Exception as e:
    # debug_log(f"Failed to start background tasks: {str(e)}")
    debug_log("Failed to start background tasks")


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
# Conditionally register production session routes or define local routes
if not AUTOCHECKIN_LOCAL:
    app.register_blueprint(session_bp, url_prefix="/api/v1")
else:
    # Define local versions of relevant session endpoints if needed
    @app.route("/api/v1/refresh")
    def local_refresh():
        debug_log("Received request to /api/v1/refresh in local mode.")
        result = refresh_local_user_session()
        if result["success"]:
            return create_response(message="Local user session refreshed successfully.", data=result)
        else:
            return create_response(success=False, message="Local user session refresh failed.", error=result.get("error"), status_code=500)

    # Add stubs or alternative logic for other session_bp routes if they are called by SPA
    # For example, /refresh-session/<email> is not applicable in single-user local mode
    @app.route("/api/v1/refresh-session/<email>")
    def local_refresh_by_email_stub(email):
         return create_response(success=False, message="Not Applicable", error="Individual refresh by email not supported in local mode.", status_code=404)

    # /fetch-users is not applicable
    @app.route("/api/v1/fetch-users")
    def local_fetch_users_stub():
         return create_response(success=False, message="Not Applicable", error="Fetching multiple users not supported in local mode.", status_code=404)
    
    # /codes - Implement local version
    @app.route("/api/v1/codes")
    def local_codes():
        debug_log("Received request to /api/v1/codes in local mode.")
        user_data = read_local_user_data()
        available_codes = user_data.get("available_untried_codes", [])
        # Maybe also return tried codes or other info?
        return create_response(
            message="Local available untried codes retrieved.", 
            data={
                "codes": available_codes, 
                "tried_codes_count": len(user_data.get("tried_codes", [])),
                "source": "local_user.json"
            }
        ) 

    # /try-codes - Implement local version
    @app.route("/api/v1/try-codes")
    def local_try_codes():
        debug_log("Received request to /api/v1/try-codes in local mode.")
        result = try_local_user_codes() # Call the local function
        if result.get("success"):
             # Check if message exists, otherwise provide default
             message = result.get("message", "Local code submission process completed.")
             return create_response(message=message, data=result)
        else:
             error = result.get("error", "Unknown error during local code submission.")
             return create_response(success=False, message="Local code submission failed.", error=error, status_code=500)
    
    # --- NEW: Endpoint specifically for SPA manual submit --- 
    @app.route("/api/v1/local/submit", methods=["POST"]) # Use POST
    def local_manual_submit():
        debug_log("Received POST request to /api/v1/local/submit.")
        # You could potentially pass arguments from SPA request body/form if needed in future
        # e.g., force = request.json.get('force', False)
        result = try_local_user_codes() # Call the same core logic
        
        # Return JSON directly, consistent with create_response structure
        response_data = {
            "success": result.get("success", False),
            "message": result.get("message") if result.get("success") else "Local code submission failed.",
            "error": result.get("error") if not result.get("success") else None,
            "data": result # Include the raw result dict for potentially more details
        }
        status_code = 200 if response_data["success"] else 500 # Or maybe 400 if specific user error?
        return jsonify(response_data), status_code

    # Add stubs for attendance endpoints if needed
    @app.route("/api/v1/fetch-attendance")
    def local_fetch_attendance_stub():
        return create_response(success=False, message="Not Applicable", error="Attendance fetching not supported in local mode.", status_code=404)
    
    @app.route("/api/v1/fetch-attendance-by-user")
    def local_fetch_attendance_by_user_stub():
        return create_response(success=False, message="Not Applicable", error="Attendance fetching not supported in local mode.", status_code=404)

    @app.route("/api/v1/fetch-prior-attendance")
    def local_fetch_prior_attendance_stub():
         return create_response(success=False, message="Not Applicable", error="Attendance fetching not supported in local mode.", status_code=404)


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
    if AUTOCHECKIN_LOCAL:
        # Serve the local SPA page if in local mode
        return send_from_directory(app.static_folder, "local_spa.html")
    else:
        # Original behavior: Return API info
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


# New endpoint to provide config for local mode frontend
@app.route("/api/v1/local/config")
def local_config():
    if not AUTOCHECKIN_LOCAL:
        return create_response(success=False, message="Not Found", error="Endpoint only available in local mode", status_code=404)

    # Fetch existing user data using the helper
    user_data = read_local_user_data()

    # Extract relevant data, providing defaults
    config_data = {
        "checkout_api_url": LOCAL_CHECKOUT_API_URL, 
        "user": {
            "email": user_data.get("email", ""),
            "token": user_data.get("token", ""), # Note: Consider security implications of sending token to frontend
            "codes_url_suffix": user_data.get("codes_url_suffix", "api/app/active/yrk/cs/2")
        },
        "state": {
            "last_session_refresh": user_data.get("last_session_refresh", None),
            "last_code_attempt": user_data.get("last_code_attempt", None),
            "available_untried_codes_count": len(user_data.get("available_untried_codes", [])),
            "tried_codes_count": len(user_data.get("tried_codes", []))
        },
        "logs": user_data.get("logs", []) # Include the logs array
    }

    return create_response(
        success=True,
        message="Local config data retrieved.", # Updated message
        data=config_data
    )


# Route to save local user data
@app.route("/save-local-user", methods=["POST"])
def save_local_user():
    if not AUTOCHECKIN_LOCAL:
        return create_response(success=False, message="Not Found", error="Endpoint only available in local mode", status_code=404)

    try:
        email = request.form.get("email")
        token = request.form.get("token")
        codes_suffix = request.form.get("codes_suffix")

        if not email or not token or not codes_suffix:
            return create_response(success=False, message="Missing form data", error="Email, token, and codes suffix are required.", status_code=400)

        # Read existing data to preserve other fields (like state)
        user_data = read_local_user_data()

        # Construct the full codes URL (using LOCAL_CHECKOUT_API_URL as per user edit)
        base_url = LOCAL_CHECKOUT_API_URL
        if base_url.endswith('/') and codes_suffix.startswith('/'):
            codes_suffix_adjusted = codes_suffix[1:]
        elif not base_url.endswith('/') and not codes_suffix.startswith('/'):
             codes_suffix_adjusted = '/' + codes_suffix
        else:
            codes_suffix_adjusted = codes_suffix

        full_codes_url = base_url + codes_suffix_adjusted

        # Update only the relevant fields from the form
        user_data["email"] = email
        user_data["token"] = token
        user_data["codes_url"] = full_codes_url
        user_data["codes_url_suffix"] = codes_suffix # Store original suffix

        # Write updated data back using the helper
        if not write_local_user_data(user_data):
             # Handle write error - maybe return an error response?
             debug_log("Failed to write local user data during save.")
             return create_response(success=False, message="Internal Server Error", error="Failed to save configuration.", status_code=500)

        return redirect("/?saved=true")

    except Exception as e:
        debug_log(f"Error saving local user data: {str(e)}")
        return create_response(success=False, message="Internal Server Error", error=str(e), status_code=500)


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
