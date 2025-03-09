# <div align="center">AutoCheckin <picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/jameshaworthcs/AutoCheckin/refs/heads/main/public/favicon-white.svg" width="25" height="25"><img src="https://raw.githubusercontent.com/jameshaworthcs/AutoCheckin/refs/heads/main/public/favicon.svg" width="25" height="25" alt="AutoCheckin Logo"></picture></div>

A Flask-based REST API that provides a session handling and checkins for the CheckOut AutoCheckin system.

## Table of Contents
- [Features](#features)
- [AutoCheckin Process](#autocheckin-process)
- [Setup](#setup)
- [Static Files](#static-files)
- [Development Server](#development-server)
- [Production Deployment](#production-deployment)
- [API Endpoints](#api-endpoints)
  - [Root Endpoint](#root-endpoint)
  - [Authentication Test Endpoint](#authentication-test-endpoint)
  - [Status Endpoints](#status-endpoints)
  - [Session Management Endpoints](#session-management-endpoints)
  - [User Management Endpoints](#user-management-endpoints)
  - [Code Management Endpoints](#code-management-endpoints)
- [Contributing](#contributing)
- [Error Handling](#error-handling)
- [Acknowledgments](#acknowledgments)

## Features

- RESTful API design
- API Key authentication testing
- Standardized JSON responses
- Proper error handling
- Environment configuration
- Production-ready with Gunicorn support
- Public static file serving

## AutoCheckin Process

The AutoCheckin system operates in two modes:

### 1. Scheduled Background Processing

The system runs an intelligent background scheduler that:
- Runs automatically at random intervals (between 1-5 hours) to avoid detection
- Processes users in random order with random delays between each user (0-10 minutes)
- For each user:
  1. Refreshes their session token to maintain authentication
  2. Updates their status in the system
  3. Logs any issues or successes

### 2. On-Demand Code Submission

The system also provides immediate code submission through the `/api/v1/try-codes` endpoint:
- Fetches and sorts available codes from CheckOut by reputation score
- For each registered user:
  1. Refreshes their session token and obtains CSRF token
  2. Gets their current event schedule
  3. For each event not marked as "Present":
     - Tries available codes until one works
     - Logs successful checkins back to CheckOut
     - Moves to next event on success
- Returns detailed statistics about the process:
  - Total number of users processed
  - Number of successful submissions
  - Timestamp of the operation

This dual-mode operation ensures both automated background processing and the ability to manually trigger checkins when needed.

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

## Static Files

The `/public` directory is used to serve static files without authentication. This is useful for:
- Favicons (`favicon.ico`, `favicon.svg`)
- Images
- Other public assets

To serve a static file, simply place it in the `public` directory and access it at the root URL.

## Connecting to the CheckOut API

Ensure the `CHECKOUT_API_URL` is set in .env and you have 'autosysop' permissions with the `CHECKOUT_API_KEY` you're using.

  Tip: When running AutoCheckin in WSL and CheckOut within Windows, run this command within wsl to find the IP address for your windows 'localhost':
  ```bash
  ip route show | grep -i default | awk '{ print $3}'
  ```
  This can often change on reboot, so will need to be updated if this is how you're developing.

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

- GET `/api/v1/fetch-attendance`
  - Triggers an attendance fetch for all users
  - Forces an immediate run of the attendance checker
  - Optional Query Parameters:
    - `year`: Specific academic year to fetch attendance for (e.g., 2023)
    - `week`: Specific week number to fetch attendance for (e.g., 42)
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Attendance fetch completed successfully",
        "data": {
            "success": true,
            "year": 2023,
            "week": 42
        }
    }
    ```
  - Error Response Format:
    ```json
    {
        "success": false,
        "message": "Attendance fetch failed",
        "error": "Error description"
    }
    ```

- GET `/api/v1/fetch-attendance-by-user`
  - Triggers an attendance fetch for a specific user by email
  - Required Query Parameters:
    - `email`: Email address of the user to fetch attendance for
  - Optional Query Parameters:
    - `year`: Specific academic year to fetch attendance for (e.g., 2023)
    - `week`: Specific week number to fetch attendance for (e.g., 42)
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Attendance fetch for user@example.com completed successfully",
        "data": {
            "success": true,
            "email": "user@example.com",
            "year": 2023,
            "week": 42
        }
    }
    ```
  - Error Response Format:
    ```json
    {
        "success": false,
        "message": "Attendance fetch for user@example.com failed",
        "error": "User not found or fetch failed",
        "status_code": 404
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

### Code Management Endpoints
- GET `/api/v1/codes`
  - Returns a sorted list of available codes from the CheckOut API
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Available codes retrieved successfully",
        "data": {
            "codes": [123456, 123457, ...]
        }
    }
    ```

- GET `/api/v1/try-codes`
  - Attempts to use available codes for all users' events
  - For each user:
    1. Refreshes their session token
    2. Gets their current events
    3. Tries available codes for each event not marked as present
    4. Logs successful checkins to CheckOut API
  - Response Format:
    ```json
    {
        "success": true,
        "message": "Code submission completed",
        "data": {
            "total_users": 10,
            "processed_users": 8,
            "timestamp": "2024-03-21T10:45:00Z"
        }
    }
    ```

## Contributing

### Code Formatting

This project uses [Black](https://github.com/psf/black) for code formatting. Black is an uncompromising Python code formatter that ensures consistent style across the project.

To format your code:

1. Install Black (it's included in requirements.txt):
```bash
pip install black
```

2. Format your code before committing:
```bash
black .
```

3. To check if your code is properly formatted without making changes:
```bash
black --check .
```

Note: The project includes a GitHub Actions workflow that automatically checks if all Python files conform to Black's formatting standards. Pull requests will fail if the code is not properly formatted.

To ensure your contributions are accepted:
1. Run `black .` locally before committing
2. Verify all files pass the check with `black --check .`
3. Fix any formatting issues before pushing your changes

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

## Acknowledgments

Special thanks to [actorpus](https://github.com/actorpus/FuckCheckin) for the initial revision of checkin code that this project ultimately stemmed from.