"""
Custom API Key Authentication for Django REST Framework.
Allows external apps to authenticate via X-API-Key header.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    """
    Custom authentication using API keys.
    
    Usage:
        Send requests with header: X-API-Key: sk_your_key_here
    """
    
    keyword = 'X-API-Key'
    
    def authenticate(self, request):
        """
        Authenticate the request using the API key from headers.
        Returns (user, api_key) tuple on success, None if no key provided.
        """
        # Get API key from header
        api_key_header = request.META.get('HTTP_X_API_KEY')
        
        if not api_key_header:
            # No API key provided - let other authentication methods try
            return None
        
        # Validate the API key
        api_key = APIKey.authenticate(api_key_header)
        
        if api_key is None:
            raise AuthenticationFailed('Invalid or inactive API key')
        
        if not api_key.user.is_active:
            raise AuthenticationFailed('User account is disabled')
        
        # Return (user, auth_info) tuple
        # The api_key object is passed as auth_info for optional use in views
        return (api_key.user, api_key)
    
    def authenticate_header(self, request):
        """
        Return string to be used as value of WWW-Authenticate header.
        """
        return self.keyword
