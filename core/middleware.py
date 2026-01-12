"""
Simple CORS middleware for development.
In production, use django-cors-headers package.
"""
from django.http import HttpResponse


class CorsMiddleware:
    """
    Middleware to add CORS headers for API requests (development only).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Handle preflight OPTIONS requests immediately
        if request.method == 'OPTIONS':
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, Authorization'
            response['Access-Control-Max-Age'] = '86400'
            response.status_code = 200
            return response
        
        response = self.get_response(request)
        
        # Add CORS headers to all API responses
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, Authorization'
        
        return response
