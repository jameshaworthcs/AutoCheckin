import os
import requests
from typing import Optional, Dict, Any, Union
from urllib.parse import urljoin

class CheckOutAPIError(Exception):
    """Custom exception for CheckOut API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class CheckOutClient:
    def __init__(self):
        # Remove /api/autocheckin from base_url as it's part of the path
        base_url = os.getenv('CHECKOUT_API_URL', '').rstrip('/')
        if '/api/autocheckin' in base_url:
            self.base_url = base_url.replace('/api/autocheckin', '')
        else:
            self.base_url = base_url
            
        self.api_key = os.getenv('CHECKOUT_API_KEY')
        if not self.base_url or not self.api_key:
            raise ValueError("CHECKOUT_API_URL and CHECKOUT_API_KEY must be set in environment variables")
        
        self.timeout = int(os.getenv('REQUESTS_TIMEOUT', '10'))
        self.verify_ssl = os.getenv('VERIFY_SSL', '0') == '1'
    
    def _make_request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a request to the CheckOut API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            data: Optional data for POST requests
            
        Returns:
            API response as dictionary
            
        Raises:
            CheckOutAPIError: If the request fails or returns non-200 status
        """
        # Always include /api/autocheckin in the path
        full_path = f"/api/autocheckin/{path.lstrip('/')}"
        url = urljoin(self.base_url, full_path)

        if os.getenv('FLASK_DEBUG') == '1':
            print(f"Making request to: {url}")
        
        headers = {
            'x-checkout-key': self.api_key,
            'User-Agent': 'AutoCheckin/1.0',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if method.upper() != 'GET' else None,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Raise for bad status codes
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', False):
                raise CheckOutAPIError(
                    f"API returned success=false: {data.get('message', 'No message provided')}",
                    response.status_code,
                    data
                )
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise CheckOutAPIError(f"Request failed: {str(e)}")
    
    def get(self, path: str) -> Dict[str, Any]:
        """Make a GET request to the CheckOut API"""
        return self._make_request('GET', path)
    
    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the CheckOut API"""
        return self._make_request('POST', path, data)
    
    def test_connection(self) -> bool:
        """Test connection to the CheckOut API"""
        try:
            self.get('test')
            return True
        except CheckOutAPIError:
            return False 