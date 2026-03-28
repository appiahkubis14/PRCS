# api/utils.py - Complete file with all utilities

import logging
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """
    Generate a random numeric OTP code
    
    Args:
        length (int): Length of OTP code (default: 6)
    
    Returns:
        str: Random numeric OTP code
    """
    return ''.join(random.choices(string.digits, k=length))


def hash_otp(otp_code):
    """
    Hash OTP code for secure storage
    
    Args:
        otp_code (str): Plain text OTP code
    
    Returns:
        str: Hashed OTP code
    """
    return make_password(otp_code)


def verify_otp(plain_otp, hashed_otp):
    """
    Verify OTP code against hashed version
    
    Args:
        plain_otp (str): Plain text OTP code
        hashed_otp (str): Hashed OTP code
    
    Returns:
        bool: True if OTP matches, False otherwise
    """
    return check_password(plain_otp, hashed_otp)


def send_otp_email(email, code):
    """
    Send OTP verification email
    
    Args:
        email (str): Recipient email address
        code (str): OTP code to send
    """
    try:
        subject = "GEMA Mobile App - Verification Code"
        
        # Try to render HTML template, fallback to plain text
        try:
            html_message = render_to_string('emails/otp.html', {
                'code': code,
                'expires_in': 10
            })
        except Exception as template_error:
            logger.warning(f"Template rendering failed: {template_error}")
            html_message = None
        
        plain_message = f"Your GEMA verification code is: {code}\n\nThis code expires in 10 minutes.\n\nIf you did not request this code, please ignore this email."
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False
        )
        logger.info(f"OTP email sent to {email}")
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        raise


def send_push_notification(user, title, body, data=None):
    """
    Send push notification via Expo
    
    Args:
        user: User object with expo_push_token
        title (str): Notification title
        body (str): Notification body
        data (dict): Additional data to send with notification
    """
    if not user or not user.expo_push_token:
        logger.warning(f"No Expo push token for user {user}")
        return
    
    try:
        # This is a placeholder - implement actual Expo push notification logic
        # You'll need to install expo-server-sdk and configure properly
        # from exponent_server_sdk import PushClient, PushMessage
        
        logger.info(f"Push notification sent to {user.email}: {title} - {body}")
        
    except Exception as e:
        logger.error(f"Failed to send push notification to {user.email}: {e}")


def calculate_distance_to_polygon(lat, lng, polygon_geometry):
    """
    Calculate distance from point to polygon (simplified)
    
    Args:
        lat (float): Latitude of point
        lng (float): Longitude of point
        polygon_geometry: Polygon geometry object
    
    Returns:
        float: Distance in meters (0 if inside polygon)
    """
    # This is a simplified implementation
    # In production, use proper GIS calculations with PostGIS
    
    try:
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import D
        
        point = Point(lng, lat, srid=4326)
        
        if polygon_geometry and polygon_geometry.contains(point):
            return 0
        
        # Calculate distance to polygon boundary
        if polygon_geometry:
            distance = point.distance(polygon_geometry) * 100000  # Rough conversion to meters
            return distance
        else:
            return 1000  # Unknown distance
            
    except Exception as e:
        logger.error(f"Error calculating distance: {e}")
        return 1000


def verify_location_status(location_data, polygon):
    """
    Determine location verification status
    
    Args:
        location_data (dict): Location data from collector
        polygon: Polygon object with geometry
    
    Returns:
        dict: Status and details
    """
    status = location_data.get('status', 'unverified')
    is_mocked = location_data.get('isMocked', False)
    distance = location_data.get('distanceToPolygon')
    
    # Check for mocked location
    if is_mocked:
        return {
            'status': 'mocked',
            'message': 'Mocked location detected',
            'distance': distance
        }
    
    # Use provided distance or calculate
    if distance is None and polygon.geometry:
        lat = location_data.get('latitude')
        lng = location_data.get('longitude')
        if lat and lng:
            distance = calculate_distance_to_polygon(lat, lng, polygon.geometry)
    
    # Determine status based on distance
    if distance is not None:
        if distance <= 0:
            return {
                'status': 'verified',
                'message': 'Collector is inside the property boundary',
                'distance': distance
            }
        elif distance <= 50:
            return {
                'status': 'proximity',
                'message': f'Collector is within {distance:.0f}m of property',
                'distance': distance
            }
        else:
            return {
                'status': 'unverified',
                'message': f'Collector is {distance:.0f}m away from property',
                'distance': distance
            }
    
    # Default to client-provided status
    return {
        'status': status,
        'message': 'Using client-provided status',
        'distance': distance
    }


def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error responses
    
    Args:
        exc: Exception instance
        context: Exception context
    
    Returns:
        Response: Custom formatted error response
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    # If DRF handled the exception, format it
    if response is not None:
        error_detail = response.data.get('detail', str(exc))
        
        # Extract validation errors
        if isinstance(response.data, dict):
            error_messages = []
            for field, errors in response.data.items():
                if field != 'detail':
                    error_messages.append(f"{field}: {', '.join(errors)}")
            if error_messages:
                error_detail = '; '.join(error_messages)
        
        return Response({
            'success': False,
            'error': error_detail,
            'status_code': response.status_code
        }, status=response.status_code)
    
    # Handle unhandled exceptions
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return Response({
        'success': False,
        'error': 'An unexpected error occurred. Please try again later.',
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def format_polygon_response(polygon):
    """
    Format polygon data for API response
    
    Args:
        polygon: Polygon model instance
    
    Returns:
        dict: Formatted polygon data
    """
    return {
        'id': polygon.id,
        'division': polygon.division,
        'block': polygon.block,
        'property': polygon.property,
        'location': polygon.location or f"D{polygon.division}B{polygon.block:03d}",
        'coordinates': polygon.coordinates or [],
        'latitude': float(polygon.latitude) if polygon.latitude else None,
        'longitude': float(polygon.longitude) if polygon.longitude else None,
        'status': polygon.status,
        'accessed': polygon.accessed,
        'createdAt': polygon.created_at.isoformat() if polygon.created_at else None,
        'updatedAt': polygon.updated_at.isoformat() if polygon.updated_at else None
    }


def format_notification_response(notification):
    """
    Format notification data for API response
    
    Args:
        notification: CollectorNotification model instance
    
    Returns:
        dict: Formatted notification data
    """
    return {
        'id': str(notification.id),
        'type': notification.type,
        'title': notification.title,
        'body': notification.body,
        'entityId': notification.entity_id,
        'createdAt': notification.created_at.isoformat()
    }


class OTPRequestThrottle:
    """
    Throttle for OTP requests to prevent abuse
    """
    def __init__(self, rate='5/15m'):
        self.rate = rate
        self.cache = {}  # Simple in-memory cache, use Redis in production
    
    def allow_request(self, email):
        """Check if request is allowed"""
        if not email:
            return True
        
        now = datetime.now()
        cache_key = f"otp_throttle_{email.lower()}"
        
        if cache_key not in self.cache:
            self.cache[cache_key] = []
        
        # Clean old entries
        self.cache[cache_key] = [
            ts for ts in self.cache[cache_key] 
            if (now - ts).total_seconds() < 900  # 15 minutes
        ]
        
        # Check if under limit
        if len(self.cache[cache_key]) >= 5:  # 5 attempts per 15 min
            return False
        
        # Add current request
        self.cache[cache_key].append(now)
        return True

