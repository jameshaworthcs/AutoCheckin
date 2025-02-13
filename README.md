# AutoCheckin

A Flask-based REST API that provides an session handling and checkins for the CheckOut AutoCheckin system.

## Features

- RESTful API design
- API Key authentication testing
- Standardized JSON responses
- Proper error handling
- Environment configuration
- Production-ready with Gunicorn support

## Setup

1. Clone the repository:
```bash
git clone https://github.com/jameshaworthcs/AutoCheckin.git
cd AutoCheckin
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Edit `.env` file with your specific configuration. Make sure to set the `CHECKOUT_API_KEY` for authentication testing.

## Development Server

To run the development server:

```bash
python main.py
```

The server will start on http://localhost:5000 (or the PORT specified in your .env file)

## Production Deployment

For production deployment, this project includes a Procfile for platforms like Railway. The Procfile uses Gunicorn as the WSGI server:

```
web: gunicorn main:app
```

## API Endpoints

### Root Endpoint
- GET `/`
  - Returns API information and available endpoints

### Authentication Test Endpoint
- GET/POST `/api/v1/auth/test`
  - Tests if the provided API key matches the configured key
  - Required Headers:
    ```
    x-checkout-key: your-api-key-here
    ```
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Authentication Test Result",
        "data": {
            "authenticated": true|false
        }
    }
    ```

### Status Endpoints
- GET `/api/v1/status`
  - Returns the current API connection status
  - Response Format:
    ```json
    {
        "success": true,
        "message": "API Status",
        "data": {
            "connected": true|false
        }
    }
    ```

- GET `/api/v1/state`
  - Returns the global state including connection status and stored data
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Global State",
        "data": {
            "connected": true|false,
            "stored_data": {
                "last_users_fetch": "2024-03-21T10:30:00Z",
                "last_all_session_refresh": "2024-03-21T10:35:00Z",
                "last_individual_session_refresh": "2024-03-21T10:40:00Z",
                "autoCheckinUsers": [...]
            }
        }
    }
    ```

### Session Management Endpoints
- GET `/api/v1/refresh`
  - Refreshes and returns all user checkin sessions
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Checkin sessions refreshed successfully",
        "data": {
            "sessions": [...]
        }
    }
    ```

- GET `/api/v1/refresh-session/<email>`
  - Refreshes and returns a specific user's checkin session
  - Parameters:
    - `email`: Email address of the user
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Checkin session refreshed successfully",
        "data": {
            "session": {...}
        }
    }
    ```

### User Management Endpoints
- GET `/api/v1/fetch-users`
  - Triggers a new fetch of users from the CheckOut API
  - Response Format:
    ```json
    {
        "success": true,
        "message": "User fetch completed",
        "data": {
            "success": true
        }
    }
    ```

## Error Handling

All errors return a standardized JSON response:
```json
{
    "success": false,
    "message": "API Error",
    "error": "Error description"
}
```

Common HTTP status codes:
- 200: Successful operation
- 400: Bad request (missing or invalid API key)
- 404: Endpoint not found
- 405: Method not allowed
- 500: Internal server error