# api/authentication.py

import jwt
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model

from core.models import UserModel

User = get_user_model()


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        
        print(f"Auth header: {auth_header}")
        
        if not auth_header:
            print("No Authorization header")
            return None
        
        try:
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                print(f"Invalid auth format: {parts}")
                return None
            
            token = parts[1]
            print(f"Token: {token[:50]}...")
            
            payload = self.decode_token(token)
            print(f"Payload: {payload}")
            
            user_id = payload.get('user_id')
            if not user_id:
                print("No user_id in payload")
                raise exceptions.AuthenticationFailed('Invalid token')
            
            # Convert user_id to int if it's a string
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                pass
            
            # Get user from database - use UserModel directly
            try:
                user = UserModel.objects.select_related('user').get(id=user_id, is_active=True)
                print(f"User found: {user.employee_id}, role: {user.role}")
            except UserModel.DoesNotExist:
                print(f"User not found with id: {user_id}")
                raise exceptions.AuthenticationFailed('User not found')
            
            # DO NOT try to set is_authenticated - it's a property that already returns True
            # The property is already defined in the model
            
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            print("Token expired")
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {e}")
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            print(f"Auth error: {e}")
            import traceback
            traceback.print_exc()
            raise exceptions.AuthenticationFailed(f'Authentication error: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'
    
    def decode_token(self, token):
        """Decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise
        except jwt.InvalidTokenError:
            raise
    
    @staticmethod
    def generate_access_token(user):
        """Generate access token (15 min expiry)"""
        payload = {
            'user_id': str(user.id),
            'email': user.email,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME),
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def generate_refresh_token(user):
        """Generate refresh token (7 days expiry)"""
        payload = {
            'user_id': str(user.id),
            'exp': datetime.utcnow() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')