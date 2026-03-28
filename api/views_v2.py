# api/views.py

import json
import uuid
from datetime import datetime
# from click import parser
from dateutil import parser
from django.http import JsonResponse
from django.db import models as django_models
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.models import (
    NoPropertyContactAvailable, PassProperty, PropertyOwner, UserModel, Polygon, Session, PREntry, 
    VersionTbl, PaymentTransaction
)
from .serializers_v2 import (
    PropertyOwnerSerializer, PropertyPOCSerializer,
    PassPropertySerializer, NoPropertyContactSerializer,
    LoginSerializer, VersionCheckSerializer
)

import logging

logger = logging.getLogger(__name__)


# ============================================================
# Helper Decorators (Modified - No Authentication)
# ============================================================

def require_authenticated(func):
    """
    Decorator that no longer checks authentication - allows all requests
    """
    def wrapper(self, request, *args, **kwargs):
        # For development - create a dummy user if needed
        # This allows the API to work without authentication
        try:
            # Try to get a default user or create one if needed
            default_user = UserModel.objects.filter(is_active=True).first()
            if default_user:
                request.authenticated_user = default_user
            else:
                # Create a dummy user if none exists
                dummy_user = UserModel.objects.create(
                    employee_id='dummy_user',
                    name='Dummy User',
                    email='dummy@example.com',
                    is_active=True,
                    role='collector'
                )
                dummy_user.set_password('dummy123')
                dummy_user.save()
                request.authenticated_user = dummy_user
        except Exception as e:
            # If we can't get/create a user, create a mock user object
            class MockUser:
                id = 1
                name = 'Mock User'
                employee_id = 'mock_user'
                email = 'mock@example.com'
                phone = ''
                role = 'collector'
                is_active = True
            request.authenticated_user = MockUser()
        
        return func(self, request, *args, **kwargs)
    
    return wrapper


def require_polygon_exists(func):
    """
    Decorator to check if polygon exists
    """
    def wrapper(self, request, *args, **kwargs):
        polygon_id = request.data.get('polygon_id') or request.query_params.get('polygon_id')
        
        if not polygon_id:
            return Response({
                'msg': 'polygon_id is required',
                'data': [],
                'status': 0
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Convert to integer if needed (since Polygon uses integer IDs)
            try:
                polygon_id = int(polygon_id)
            except (ValueError, TypeError):
                pass
            
            polygon = Polygon.objects.get(id=polygon_id)
            request.polygon = polygon
            return func(self, request, *args, **kwargs)
        except Polygon.DoesNotExist:
            return Response({
                'msg': 'Polygon not found',
                'data': [],
                'status': 0
            }, status=status.HTTP_404_NOT_FOUND)
    
    return wrapper


# ============================================================
# Version Check API
# ============================================================

@method_decorator(csrf_exempt, name='dispatch')
class VersionCheckAPIView(APIView):
    """
    API endpoint to check app version compatibility
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Check if the app version is compatible with the server",
        request_body=VersionCheckSerializer,
        responses={
            200: openapi.Response(
                description="Version check successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'msg': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'is_valid': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'current_version': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'latest_version': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'update_required': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'force_update': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            }
                        )
                    }
                )
            ),
            400: "Version field is required",
            500: "Internal server error"
        }
    )
    def post(self, request):
        """
        Check if the app version matches the server version
        
        Args:
            version (int): The app version number
            
        Returns:
            Response: Version compatibility status
        """
        response_data = {
            "status": 0,
            "msg": "Error Occurred!",
            "data": None
        }
        
        try:
            # Parse request data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.data
            
            # Get version from request
            app_version = data.get("version")
            
            if app_version is None:
                response_data["msg"] = "version field is required"
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Get latest version from database
            try:
                latest_version_obj = VersionTbl.objects.filter(is_deleted=False).order_by('-created_at').first()
                latest_version = latest_version_obj.version if latest_version_obj else 1
            except Exception:
                latest_version = 1
            
            # Check version compatibility
            is_valid = (app_version >= latest_version - 1)  # Allow one version behind
            update_required = (app_version < latest_version)
            force_update = (app_version < latest_version - 1)
            
            response_data["status"] = 1
            response_data["msg"] = "Version check successful"
            response_data["data"] = {
                "is_valid": is_valid,
                "current_version": app_version,
                "latest_version": latest_version,
                "update_required": update_required,
                "force_update": force_update
            }
            
        except json.JSONDecodeError as e:
            response_data["msg"] = "Invalid JSON format"
            response_data["data"] = str(e)
        except Exception as e:
            logger.error(f"Version check error: {str(e)}")
            response_data["msg"] = "Error Occurred!"
            response_data["data"] = str(e)
        
        return Response(response_data)


# ============================================================
# Login API
# ============================================================
from django.db.models import Q
class LoginAPIView(APIView):
    """
    API endpoint for user login
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="User login with employee_id/email and password",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'msg': openapi.Schema(type=openapi.TYPE_STRING),
                        'status': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'employee_id': openapi.Schema(type=openapi.TYPE_STRING),
                                'name': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                                'phone': openapi.Schema(type=openapi.TYPE_STRING),
                                'role': openapi.Schema(type=openapi.TYPE_STRING),
                                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            }
                        )
                    }
                )
            ),
            400: "Invalid credentials",
            500: "Internal server error"
        }
    )
    def post(self, request):
        """
        Authenticate user with username (employee_id or email) and password
        
        Args:
            username (str): employee_id or email
            password (str): user password
            
        Returns:
            Response: user data with authentication status
        """
        try:
            # serializer = LoginSerializer(data=request.data)
            
            data = request.data
            username = data.get('username')
            password = data.get('password_new')
            print(username,password)
                # Try to find user by employee_id or email
            user = UserModel.objects.filter(
                Q(employee_id=username) | Q(email=username),
                password_new=password,
                
            ).first()
                
            # Authenticate with password
            if user:
                # Return user data
                user_data = {
                    'id': user.id,
                    'employee_id': user.employee_id,
                    'name': user.name,
                    'email': user.email,
                    'phone': user.phone,
                    'role': user.role,
                    'is_active': user.is_active
                }
                
                return Response({
                    'msg': 'Login successful',
                    'status': 1,
                    'data': user_data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'msg': 'Invalid username or password',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_401_UNAUTHORIZED)
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                'msg': f'Error during login: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================
# Property Owner API (Open - No Authentication)
# ============================================================

class PropertyOwnerAPIView(APIView):
    """
    API endpoint for Property Owner data management (Open Access)
    Uses the PropertyOwner model for structured storage
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all property owner entries",
        manual_parameters=[
            openapi.Parameter(
                'session_id',
                openapi.IN_QUERY,
                description="Filter by session ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'polygon_id',
                openapi.IN_QUERY,
                description="Filter by polygon ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'collector_id',
                openapi.IN_QUERY,
                description="Filter by collector ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'is_verified',
                openapi.IN_QUERY,
                description="Filter by verification status",
                type=openapi.TYPE_BOOLEAN,
                required=False
            ),
        ],
        responses={
            200: "Success",
            500: "Internal server error"
        }
    )
    def get(self, request):
        """
        Fetch property owner entries with optional filters
        """
        try:
            # Build queryset
            queryset = PropertyOwner.objects.filter(
                
                is_active=True
            ).select_related('polygon', 'session', 'collector')
            
            # Apply filters
            session_id = request.query_params.get('session_id')
            if session_id:
                try:
                    session_id = int(session_id)
                    queryset = queryset.filter(session_id=session_id)
                except (ValueError, TypeError):
                    pass
            
            polygon_id = request.query_params.get('polygon_id')
            if polygon_id:
                try:
                    polygon_id = int(polygon_id)
                    queryset = queryset.filter(polygon_id=polygon_id)
                except (ValueError, TypeError):
                    pass
            
            collector_id = request.query_params.get('collector_id')
            if collector_id:
                try:
                    collector_id = int(collector_id)
                    queryset = queryset.filter(collector_id=collector_id)
                except (ValueError, TypeError):
                    pass
            
            is_verified = request.query_params.get('is_verified')
            if is_verified is not None:
                queryset = queryset.filter(is_verified=is_verified.lower() == 'true')
            
            # Order by created_at descending
            queryset = queryset.order_by('-created_at')
            
            # Serialize data
            result_data = []
            for owner in queryset:
                result_data.append({
                    'id': owner.id,
                    'title': owner.title,
                    'owner_name': owner.owner_name,
                    'contact_number': owner.contact_number,
                    'alternative_number': owner.alternative_number,
                    'email': owner.email,
                    'ghana_card_number': owner.ghana_card_number,
                    'tin_number': owner.tin_number,
                    'location': owner.location,
                    'gps_location': owner.gps_location,
                    'street_name': owner.street_name,
                    'house_number': owner.house_number,
                    'digital_address': owner.digital_address,
                    'property_type': owner.property_type,
                    'property_state': owner.property_state,
                    'property_details': owner.property_details,
                    'rooms': owner.rooms,
                    'occupier': owner.occupier,
                    'communication_method': owner.communication_method,
                    'payment_method': owner.payment_method,
                    'preferred_contact_time': owner.preferred_contact_time,
                    'polygon_id': owner.polygon_id,
                    'session_id': owner.session_id,
                    'collector_id': owner.collector_id,
                    'collector_name': owner.collector.name if owner.collector else None,
                    'is_verified': owner.is_verified,
                    'verified_at': owner.verified_at,
                    'verified_by': owner.verified_by_id,
                    'notes': owner.notes,
                    'created_at': owner.created_at,
                    'updated_at': owner.updated_at,
                })
            
            return Response({
                'msg': 'Property owner entries fetched successfully',
                'status': 1,
                'data': result_data,
                'count': len(result_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching property owner entries: {str(e)}")
            return Response({
                'msg': f'Error fetching data: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Create a new property owner entry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING, enum=['Mr', 'Mrs', 'Ms', 'Dr', 'Chief', 'None']),
                'owner_name': openapi.Schema(type=openapi.TYPE_STRING),
                'contact_number': openapi.Schema(type=openapi.TYPE_STRING),
                'alternative_number': openapi.Schema(type=openapi.TYPE_STRING),
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'ghana_card_number': openapi.Schema(type=openapi.TYPE_STRING),
                'tin_number': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'gps_location': openapi.Schema(type=openapi.TYPE_STRING),
                'street_name': openapi.Schema(type=openapi.TYPE_STRING),
                'house_number': openapi.Schema(type=openapi.TYPE_STRING),
                'digital_address': openapi.Schema(type=openapi.TYPE_STRING),
                'property_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['Residential', 'Commercial', 'Industrial', 'Mixed Use', 'Vacant Land', 'Other']),
                'property_state': openapi.Schema(type=openapi.TYPE_STRING, enum=['Completed', 'Under Construction', 'Unfinished', 'Abandoned', 'Under Renovation']),
                'property_details': openapi.Schema(type=openapi.TYPE_STRING),
                'rooms': openapi.Schema(type=openapi.TYPE_STRING),
                'occupier': openapi.Schema(type=openapi.TYPE_STRING, enum=['Owner Occupied', 'Tenant', 'Vacant', 'Partially Occupied']),
                'communication_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['Phone Call', 'SMS', 'Email', 'WhatsApp', 'In Person']),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['Mobile Money', 'Bank Transfer', 'Cash', 'Cheque', 'Card']),
                'preferred_contact_time': openapi.Schema(type=openapi.TYPE_STRING),
                'polygon_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'collector_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['owner_name', 'polygon_id']
        ),
        responses={
            201: "Created successfully",
            400: "Validation error",
            404: "Polygon not found",
            500: "Internal server error"
        }
    )
    def post(self, request):
        """
        Create a new property owner entry
        """
        try:
            # Validate required fields
            required_fields = ['owner_name', 'polygon_id']
            for field in required_fields:
                if field not in request.data:
                    return Response({
                        'msg': f'{field} is required',
                        'status': 0,
                        'data': []
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate polygon exists
            try:
                polygon = Polygon.objects.get(
                    id=request.data['polygon_id'],
                    
                )
            except Polygon.DoesNotExist:
                return Response({
                    'msg': 'Polygon not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get or create session if session_id provided
            session = None
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(
                        id=request.data['session_id'],
                        
                    )
                except Session.DoesNotExist:
                    pass
            
            # Get collector if provided
            collector = None
            if 'agent_id' in request.data:
                try:
                    collector = UserModel.objects.get(id=request.data['agent_id'])
                except UserModel.DoesNotExist:
                    pass
            
            # Create property owner
            owner = PropertyOwner.objects.create(
                title=request.data.get('title'),
                owner_name=request.data['owner_name'],
                contact_number=request.data.get('contact_number'),
                alternative_number=request.data.get('alternative_number'),
                email=request.data.get('email'),
                ghana_card_number=request.data.get('ghana_card_number'),
                tin_number=request.data.get('tin_number'),
                location=request.data.get('location'),
                gps_location=request.data.get('gps_location'),
                street_name=request.data.get('street_name'),
                house_number=request.data.get('house_number'),
                digital_address=request.data.get('digital_address'),
                property_type=request.data.get('property_type'),
                property_state=request.data.get('property_state'),
                property_details=request.data.get('property_details'),
                rooms=request.data.get('rooms'),
                occupier=request.data.get('occupier'),
                communication_method=request.data.get('communication_method'),
                payment_method=request.data.get('payment_method'),
                preferred_contact_time=request.data.get('preferred_contact_time'),
                polygon=polygon,
                session=session,
                collector=collector,
                notes=request.data.get('notes'),
                is_active=True
            )
            
            # Prepare response data
            response_data = {
                'id': owner.id,
                'title': owner.title,
                'owner_name': owner.owner_name,
                'contact_number': owner.contact_number,
                'alternative_number': owner.alternative_number,
                'email': owner.email,
                'ghana_card_number': owner.ghana_card_number,
                'tin_number': owner.tin_number,
                'location': owner.location,
                'gps_location': owner.gps_location,
                'street_name': owner.street_name,
                'house_number': owner.house_number,
                'digital_address': owner.digital_address,
                'property_type': owner.property_type,
                'property_state': owner.property_state,
                'property_details': owner.property_details,
                'rooms': owner.rooms,
                'occupier': owner.occupier,
                'communication_method': owner.communication_method,
                'payment_method': owner.payment_method,
                'preferred_contact_time': owner.preferred_contact_time,
                'polygon_id': owner.polygon_id,
                'session_id': owner.session_id,
                'collector_id': owner.collector_id,
                'notes': owner.notes,
                'created_at': owner.created_at,
                'updated_at': owner.updated_at,
            }
            
            return Response({
                'msg': 'Property owner created successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating property owner entry: {str(e)}")
            return Response({
                'msg': f'Error creating entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Update a property owner entry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING),
                'owner_name': openapi.Schema(type=openapi.TYPE_STRING),
                'contact_number': openapi.Schema(type=openapi.TYPE_STRING),
                'alternative_number': openapi.Schema(type=openapi.TYPE_STRING),
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'ghana_card_number': openapi.Schema(type=openapi.TYPE_STRING),
                'tin_number': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'gps_location': openapi.Schema(type=openapi.TYPE_STRING),
                'street_name': openapi.Schema(type=openapi.TYPE_STRING),
                'house_number': openapi.Schema(type=openapi.TYPE_STRING),
                'digital_address': openapi.Schema(type=openapi.TYPE_STRING),
                'property_type': openapi.Schema(type=openapi.TYPE_STRING),
                'property_state': openapi.Schema(type=openapi.TYPE_STRING),
                'property_details': openapi.Schema(type=openapi.TYPE_STRING),
                'rooms': openapi.Schema(type=openapi.TYPE_STRING),
                'occupier': openapi.Schema(type=openapi.TYPE_STRING),
                'communication_method': openapi.Schema(type=openapi.TYPE_STRING),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                'preferred_contact_time': openapi.Schema(type=openapi.TYPE_STRING),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: "Updated successfully",
            400: "Validation error",
            404: "Entry not found",
            500: "Internal server error"
        }
    )
    def put(self, request, entry_id=None):
        """
        Update an existing property owner entry
        """
        try:
            # Get entry ID
            entry_id = entry_id or request.data.get('id')
            
            if not entry_id:
                return Response({
                    'msg': 'Entry ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                entry_id = int(entry_id)
                owner = PropertyOwner.objects.get(
                    id=entry_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid entry ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PropertyOwner.DoesNotExist:
                return Response({
                    'msg': 'Property owner entry not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update fields if provided
            updatable_fields = [
                'title', 'owner_name', 'contact_number', 'alternative_number',
                'email', 'ghana_card_number', 'tin_number', 'location',
                'gps_location', 'street_name', 'house_number', 'digital_address',
                'property_type', 'property_state', 'property_details', 'rooms',
                'occupier', 'communication_method', 'payment_method',
                'preferred_contact_time', 'notes'
            ]
            
            for field in updatable_fields:
                if field in request.data:
                    setattr(owner, field, request.data[field])
            
            # Handle relationship updates
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(id=request.data['session_id'])
                    owner.session = session
                except Session.DoesNotExist:
                    pass
            
            if 'collector_id' in request.data:
                try:
                    collector = UserModel.objects.get(id=request.data['collector_id'])
                    owner.collector = collector
                except UserModel.DoesNotExist:
                    pass
            
            owner.save()
            
            # Prepare response data
            response_data = {
                'id': owner.id,
                'title': owner.title,
                'owner_name': owner.owner_name,
                'contact_number': owner.contact_number,
                'alternative_number': owner.alternative_number,
                'email': owner.email,
                'ghana_card_number': owner.ghana_card_number,
                'tin_number': owner.tin_number,
                'location': owner.location,
                'gps_location': owner.gps_location,
                'street_name': owner.street_name,
                'house_number': owner.house_number,
                'digital_address': owner.digital_address,
                'property_type': owner.property_type,
                'property_state': owner.property_state,
                'property_details': owner.property_details,
                'rooms': owner.rooms,
                'occupier': owner.occupier,
                'communication_method': owner.communication_method,
                'payment_method': owner.payment_method,
                'preferred_contact_time': owner.preferred_contact_time,
                'polygon_id': owner.polygon_id,
                'session_id': owner.session_id,
                'collector_id': owner.collector_id,
                'notes': owner.notes,
                'is_verified': owner.is_verified,
                'verified_at': owner.verified_at,
                'created_at': owner.created_at,
                'updated_at': owner.updated_at,
            }
            
            return Response({
                'msg': 'Property owner entry updated successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating property owner entry: {str(e)}")
            return Response({
                'msg': f'Error updating entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Delete a property owner entry (soft delete)",
        responses={
            200: "Deleted successfully",
            404: "Entry not found",
            500: "Internal server error"
        }
    )
    def delete(self, request, entry_id=None):
        """
        Soft delete a property owner entry
        """
        try:
            # Get entry ID
            entry_id = entry_id or request.data.get('id')
            
            if not entry_id:
                return Response({
                    'msg': 'Entry ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                entry_id = int(entry_id)
                owner = PropertyOwner.objects.get(
                    id=entry_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid entry ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PropertyOwner.DoesNotExist:
                return Response({
                    'msg': 'Property owner entry not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Soft delete
            owner.deleted_at = timezone.now()
            owner.is_active = False
            owner.save()
            
            return Response({
                'msg': 'Property owner entry deleted successfully',
                'status': 1,
                'data': []
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting property owner entry: {str(e)}")
            return Response({
                'msg': f'Error deleting entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Verify a property owner entry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'verified': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'verifier_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['verified']
        ),
        responses={
            200: "Verified successfully",
            400: "Validation error",
            404: "Entry not found",
            500: "Internal server error"
        }
    )
    def patch(self, request, entry_id=None):
        """
        Verify or unverify a property owner entry
        """
        try:
            # Get entry ID
            entry_id = entry_id or request.data.get('id')
            
            if not entry_id:
                return Response({
                    'msg': 'Entry ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                entry_id = int(entry_id)
                owner = PropertyOwner.objects.get(
                    id=entry_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid entry ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PropertyOwner.DoesNotExist:
                return Response({
                    'msg': 'Property owner entry not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update verification status
            verified = request.data.get('verified', False)
            owner.is_verified = verified
            
            if verified:
                owner.verified_at = timezone.now()
                
                # Set verifier if provided
                verifier_id = request.data.get('verifier_id')
                if verifier_id:
                    try:
                        verifier = UserModel.objects.get(id=verifier_id)
                        owner.verified_by = verifier
                    except UserModel.DoesNotExist:
                        pass
                
                # Add verification notes if provided
                if 'notes' in request.data:
                    owner.notes = request.data['notes']
            else:
                owner.verified_at = None
                owner.verified_by = None
            
            owner.save()
            
            return Response({
                'msg': f'Property owner {"verified" if verified else "unverified"} successfully',
                'status': 1,
                'data': {
                    'id': owner.id,
                    'is_verified': owner.is_verified,
                    'verified_at': owner.verified_at,
                    'verified_by': owner.verified_by_id,
                    'notes': owner.notes
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error verifying property owner entry: {str(e)}")
            return Response({
                'msg': f'Error verifying entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================
# Property POC (Person of Contact) API (Open - No Authentication)
# ============================================================

class PropertyPOCAPIView(APIView):
    """
    API endpoint for Property Person of Contact data management (Open Access)
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all property POC entries",
        manual_parameters=[
            openapi.Parameter(
                'session_id',
                openapi.IN_QUERY,
                description="Filter by session ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'polygon_id',
                openapi.IN_QUERY,
                description="Filter by polygon ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: "Success",
            500: "Internal server error"
        }
    )
    def get(self, request):
        """
        Fetch property POC entries
        """
        try:
            queryset = PREntry.objects.filter(
                mode='property_poc',
                
            ).select_related('session', 'session__polygon')
            
            # Apply filters
            session_id = request.query_params.get('session_id')
            if session_id:
                try:
                    session_id = int(session_id)
                    queryset = queryset.filter(session_id=session_id)
                except (ValueError, TypeError):
                    pass
            
            polygon_id = request.query_params.get('polygon_id')
            if polygon_id:
                try:
                    polygon_id = int(polygon_id)
                    queryset = queryset.filter(session__polygon_id=polygon_id)
                except (ValueError, TypeError):
                    pass
            
            queryset = queryset.order_by('-created_at')
            
            # Serialize data - extract the stored data fields
            result_data = []
            for entry in queryset:
                entry_data = {
                    'id': entry.id,
                    'session_id': entry.session_id,
                    'entry_index': entry.entry_index,
                    'mode': entry.mode,
                    'status': entry.status,
                    'created_at': entry.created_at,
                    'updated_at': entry.updated_at,
                }
                # Merge the JSON data fields
                if entry.data:
                    entry_data.update(entry.data)
                result_data.append(entry_data)
            
            return Response({
                'msg': 'Property POC entries fetched successfully',
                'status': 1,
                'data': result_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching property POC entries: {str(e)}")
            return Response({
                'msg': f'Error fetching data: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Create a new property POC entry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'property_type': openapi.Schema(type=openapi.TYPE_STRING),
                'property_state': openapi.Schema(type=openapi.TYPE_STRING),
                'rooms': openapi.Schema(type=openapi.TYPE_STRING),
                'relationship': openapi.Schema(type=openapi.TYPE_STRING),
                'property_details': openapi.Schema(type=openapi.TYPE_STRING),
                'communication_method': openapi.Schema(type=openapi.TYPE_STRING),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                'owner_name': openapi.Schema(type=openapi.TYPE_STRING),
                'contact_number': openapi.Schema(type=openapi.TYPE_STRING),
                'ghana_card_number': openapi.Schema(type=openapi.TYPE_STRING),
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'gps_location': openapi.Schema(type=openapi.TYPE_STRING),
                'street_name': openapi.Schema(type=openapi.TYPE_STRING),
                'agent_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'polygon_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            },
            required=['polygon_id']
        ),
        responses={
            201: "Created successfully",
            400: "Validation error",
            404: "Polygon not found",
            500: "Internal server error"
        }
    )
    @require_polygon_exists
    def post(self, request):
        """
        Create a new property POC entry
        """
        try:
            session = self._get_or_create_session(request)
            
            # Extract the property POC specific fields into data JSON
            property_fields = [
                'title', 'location', 'property_type', 'property_state', 'rooms',
                'relationship', 'property_details', 'communication_method', 'payment_method',
                'owner_name', 'contact_number', 'ghana_card_number', 'email',
                'gps_location', 'street_name', 'agent_id', 'polygon_id'
            ]
            
            data_json = {}
            for field in property_fields:
                if field in request.data:
                    data_json[field] = request.data[field]
            
            # Get next entry index
            last_entry = PREntry.objects.filter(
                session=session,
                
            ).order_by('-entry_index').first()
            
            entry_index = (last_entry.entry_index + 1) if last_entry else 1
            
            # Create entry
            entry = PREntry.objects.create(
                session=session,
                entry_index=entry_index,
                mode='property_poc',
                data=data_json,
                status='pending'
            )
            
            # Prepare response data
            response_data = {
                'id': entry.id,
                'session_id': entry.session_id,
                'entry_index': entry.entry_index,
                'mode': entry.mode,
                'status': entry.status,
                'created_at': entry.created_at,
                'updated_at': entry.updated_at,
            }
            response_data.update(data_json)
            
            return Response({
                'msg': 'Property POC entry created successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating property POC entry: {str(e)}")
            return Response({
                'msg': f'Error creating entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Update a property POC entry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'title': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'property_type': openapi.Schema(type=openapi.TYPE_STRING),
                'property_state': openapi.Schema(type=openapi.TYPE_STRING),
                'rooms': openapi.Schema(type=openapi.TYPE_STRING),
                'relationship': openapi.Schema(type=openapi.TYPE_STRING),
                'property_details': openapi.Schema(type=openapi.TYPE_STRING),
                'communication_method': openapi.Schema(type=openapi.TYPE_STRING),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                'owner_name': openapi.Schema(type=openapi.TYPE_STRING),
                'contact_number': openapi.Schema(type=openapi.TYPE_STRING),
                'ghana_card_number': openapi.Schema(type=openapi.TYPE_STRING),
                'email': openapi.Schema(type=openapi.TYPE_STRING),
                'gps_location': openapi.Schema(type=openapi.TYPE_STRING),
                'street_name': openapi.Schema(type=openapi.TYPE_STRING),
                'agent_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            },
            required=['id']
        ),
        responses={
            200: "Updated successfully",
            400: "Validation error",
            404: "Entry not found",
            500: "Internal server error"
        }
    )
    def put(self, request, entry_id=None):
        """
        Update an existing property POC entry
        """
        try:
            entry_id = entry_id or request.data.get('id')
            
            if not entry_id:
                return Response({
                    'msg': 'Entry ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                entry_id = int(entry_id)
                entry = PREntry.objects.get(
                    id=entry_id,
                    mode='property_poc',
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid entry ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PREntry.DoesNotExist:
                return Response({
                    'msg': 'Property POC entry not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update the data JSON field
            property_fields = [
                'title', 'location', 'property_type', 'property_state', 'rooms',
                'relationship', 'property_details', 'communication_method', 'payment_method',
                'owner_name', 'contact_number', 'ghana_card_number', 'email',
                'gps_location', 'street_name', 'agent_id'
            ]
            
            # Get current data
            current_data = entry.data or {}
            
            # Update with new data
            for field in property_fields:
                if field in request.data:
                    current_data[field] = request.data[field]
            
            entry.data = current_data
            entry.save()
            
            # Prepare response data
            response_data = {
                'id': entry.id,
                'session_id': entry.session_id,
                'entry_index': entry.entry_index,
                'mode': entry.mode,
                'status': entry.status,
                'created_at': entry.created_at,
                'updated_at': entry.updated_at,
            }
            response_data.update(current_data)
            
            return Response({
                'msg': 'Property POC entry updated successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating property POC entry: {str(e)}")
            return Response({
                'msg': f'Error updating entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Delete a property POC entry (soft delete)",
        responses={
            200: "Deleted successfully",
            404: "Entry not found",
            500: "Internal server error"
        }
    )
    def delete(self, request, entry_id=None):
        """
        Soft delete a property POC entry
        """
        try:
            entry_id = entry_id or request.data.get('id')
            
            if not entry_id:
                return Response({
                    'msg': 'Entry ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                entry_id = int(entry_id)
                entry = PREntry.objects.get(
                    id=entry_id,
                    mode='property_poc',
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid entry ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PREntry.DoesNotExist:
                return Response({
                    'msg': 'Property POC entry not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            entry.deleted_at = timezone.now()
            entry.save()
            
            return Response({
                'msg': 'Property POC entry deleted successfully',
                'status': 1,
                'data': []
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting property POC entry: {str(e)}")
            return Response({
                'msg': f'Error deleting entry: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_or_create_session(self, request):
        """
        Helper method to get or create a session
        """
        polygon = request.polygon
        
        # Get a dummy user or create one
        try:
            user = UserModel.objects.filter(is_active=True).first()
            if not user:
                user = UserModel.objects.create(
                    employee_id='system_user',
                    name='System User',
                    email='system@example.com',
                    is_active=True,
                    role='collector'
                )
                user.set_password('system123')
                user.save()
        except:
            # Create a mock user object
            class MockUser:
                id = 1
                name = 'System User'
                employee_id = 'system_user'
                email = 'system@example.com'
                phone = ''
                role = 'collector'
                is_active = True
            user = MockUser()
        
        session = Session.objects.filter(
            polygon=polygon,
            status__in=['pending', 'draft'],
            
        ).first()
        
        if not session:
            session = Session.objects.create(
                polygon=polygon,
                collector_id=user.id if hasattr(user, 'id') else 1,
                status='pending',
                pr_data={},
                businesses=[]
            )
        
        return session


# ============================================================
# Pass Property API (Open - No Authentication)
# ============================================================
# ============================================================
# Pass Property API
# ============================================================

class PassPropertyAPIView(APIView):
    """
    API endpoint for Pass Property records (Open Access)
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all pass property records",
        manual_parameters=[
            openapi.Parameter(
                'polygon_id',
                openapi.IN_QUERY,
                description="Filter by polygon ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'agent_id',
                openapi.IN_QUERY,
                description="Filter by agent ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'reason',
                openapi.IN_QUERY,
                description="Filter by reason",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'session_id',
                openapi.IN_QUERY,
                description="Filter by session ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: "Success",
            500: "Internal server error"
        }
    )
    def get(self, request):
        """
        Fetch pass property records with optional filters
        """
        try:
            # Build queryset
            queryset = PassProperty.objects.filter(
                
                is_active=True
            ).select_related('polygon', 'agent', 'session')
            
            # Apply filters
            polygon_id = request.query_params.get('polygon_id')
            if polygon_id:
                try:
                    polygon_id = int(polygon_id)
                    queryset = queryset.filter(polygon_id=polygon_id)
                except (ValueError, TypeError):
                    pass
            
            agent_id = request.query_params.get('agent_id')
            if agent_id:
                try:
                    agent_id = int(agent_id)
                    queryset = queryset.filter(agent_id=agent_id)
                except (ValueError, TypeError):
                    pass
            
            reason = request.query_params.get('reason')
            if reason:
                queryset = queryset.filter(reason=reason)
            
            session_id = request.query_params.get('session_id')
            if session_id:
                try:
                    session_id = int(session_id)
                    queryset = queryset.filter(session_id=session_id)
                except (ValueError, TypeError):
                    pass
            
            # Order by passed_at descending
            queryset = queryset.order_by('-passed_at')
            
            # Serialize data
            result_data = []
            for record in queryset:
                result_data.append({
                    'id': record.id,
                    'reason': record.reason,
                    'reason_display': record.get_reason_display(),
                    'notes': record.notes,
                    'polygon_id': record.polygon_id,
                    'polygon_info': {
                        'id': record.polygon.id,
                        'division': record.polygon.division,
                        'block': record.polygon.block,
                        'address': record.polygon.address
                    } if record.polygon else None,
                    'agent_id': record.agent_id,
                    'agent_name': record.agent.name if record.agent else None,
                    'session_id': record.session_id,
                    'passed_at': record.passed_at,
                    'created_at': record.created_at,
                    'updated_at': record.updated_at,
                })
            
            return Response({
                'msg': 'Pass property records fetched successfully',
                'status': 1,
                'data': result_data,
                'count': len(result_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching pass property records: {str(e)}")
            return Response({
                'msg': f'Error fetching data: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Create a new pass property record",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['inaccessible', 'no_answer', 'security', 'vacant', 
                          'under_construction', 'wrong_address', 'refused', 
                          'no_consent', 'other']
                ),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                'polygon_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'agent_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            },
            required=['reason', 'polygon_id']
        ),
        responses={
            201: "Created successfully",
            400: "Validation error",
            404: "Polygon not found",
            500: "Internal server error"
        }
    )
    def post(self, request):
        """
        Create a new pass property record
        """
        try:
            # Validate required fields
            required_fields = ['reason', 'polygon_id']
            for field in required_fields:
                if field not in request.data:
                    return Response({
                        'msg': f'{field} is required',
                        'status': 0,
                        'data': []
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate polygon exists
            try:
                polygon = Polygon.objects.get(
                    id=request.data['polygon_id'],
                    
                )
            except Polygon.DoesNotExist:
                return Response({
                    'msg': 'Polygon not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate reason is valid
            if request.data['reason'] not in dict(PassProperty.PassReason.choices):
                return Response({
                    'msg': f'Invalid reason. Must be one of: {", ".join(dict(PassProperty.PassReason.choices).keys())}',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get agent if provided
            agent = None
            if 'agent_id' in request.data:
                try:
                    agent = UserModel.objects.get(id=request.data['agent_id'])
                except UserModel.DoesNotExist:
                    pass
            
            # Get session if provided
            session = None
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(id=request.data['session_id'])
                except Session.DoesNotExist:
                    pass
            
            # Check if there's already an active pass record for this polygon
            existing_record = PassProperty.objects.filter(
                polygon_id=polygon.id,
                is_active=True,
                
            ).first()
            
            if existing_record:
                # Soft delete the existing record
                existing_record.deleted_at = timezone.now()
                existing_record.is_active = False
                existing_record.save()
            
            # Create pass property record
            record = PassProperty.objects.create(
                reason=request.data['reason'],
                notes=request.data.get('notes', ''),
                polygon=polygon,
                agent=agent,
                session=session,
                is_active=True
            )
            
            # Prepare response data
            response_data = {
                'id': record.id,
                'reason': record.reason,
                'reason_display': record.get_reason_display(),
                'notes': record.notes,
                'polygon_id': record.polygon_id,
                'agent_id': record.agent_id,
                'agent_name': record.agent.name if record.agent else None,
                'session_id': record.session_id,
                'passed_at': record.passed_at,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
            }
            
            return Response({
                'msg': 'Pass property record created successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating pass property record: {str(e)}")
            return Response({
                'msg': f'Error creating record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Update a pass property record",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'reason': openapi.Schema(type=openapi.TYPE_STRING),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                'agent_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
        responses={
            200: "Updated successfully",
            400: "Validation error",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def put(self, request, record_id=None):
        """
        Update an existing pass property record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                record_id = int(record_id)
                record = PassProperty.objects.get(
                    id=record_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PassProperty.DoesNotExist:
                return Response({
                    'msg': 'Pass property record not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update fields
            if 'reason' in request.data:
                if request.data['reason'] not in dict(PassProperty.PassReason.choices):
                    return Response({
                        'msg': f'Invalid reason. Must be one of: {", ".join(dict(PassProperty.PassReason.choices).keys())}',
                        'status': 0,
                        'data': []
                    }, status=status.HTTP_400_BAD_REQUEST)
                record.reason = request.data['reason']
            
            if 'notes' in request.data:
                record.notes = request.data['notes']
            
            if 'agent_id' in request.data:
                try:
                    agent = UserModel.objects.get(id=request.data['agent_id'])
                    record.agent = agent
                except UserModel.DoesNotExist:
                    record.agent = None
            
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(id=request.data['session_id'])
                    record.session = session
                except Session.DoesNotExist:
                    record.session = None
            
            record.save()
            
            # Prepare response data
            response_data = {
                'id': record.id,
                'reason': record.reason,
                'reason_display': record.get_reason_display(),
                'notes': record.notes,
                'polygon_id': record.polygon_id,
                'agent_id': record.agent_id,
                'agent_name': record.agent.name if record.agent else None,
                'session_id': record.session_id,
                'passed_at': record.passed_at,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
            }
            
            return Response({
                'msg': 'Pass property record updated successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating pass property record: {str(e)}")
            return Response({
                'msg': f'Error updating record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Delete a pass property record (soft delete)",
        responses={
            200: "Deleted successfully",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def delete(self, request, record_id=None):
        """
        Soft delete a pass property record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                record_id = int(record_id)
                record = PassProperty.objects.get(
                    id=record_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except PassProperty.DoesNotExist:
                return Response({
                    'msg': 'Pass property record not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Soft delete
            record.deleted_at = timezone.now()
            record.is_active = False
            record.save()
            
            return Response({
                'msg': 'Pass property record deleted successfully',
                'status': 1,
                'data': []
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting pass property record: {str(e)}")
            return Response({
                'msg': f'Error deleting record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# No Property Contact Available API
# ============================================================

class NoPropertyContactAvailableAPIView(APIView):
    """
    API endpoint for No Property Contact Available records (Open Access)
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all no-contact records",
        manual_parameters=[
            openapi.Parameter(
                'polygon_id',
                openapi.IN_QUERY,
                description="Filter by polygon ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="Filter by user/collector ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'resolved',
                openapi.IN_QUERY,
                description="Filter by resolved status",
                type=openapi.TYPE_BOOLEAN,
                required=False
            ),
            openapi.Parameter(
                'session_id',
                openapi.IN_QUERY,
                description="Filter by session ID",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: "Success",
            500: "Internal server error"
        }
    )
    def get(self, request):
        """
        Fetch no-contact records with optional filters
        """
        try:
            # Build queryset
            queryset = NoPropertyContactAvailable.objects.filter(
                
                is_no_contact=True
            ).select_related('polygon', 'user', 'session', 'resolved_by')
            
            # Apply filters
            polygon_id = request.query_params.get('polygon_id')
            if polygon_id:
                try:
                    polygon_id = int(polygon_id)
                    queryset = queryset.filter(polygon_id=polygon_id)
                except (ValueError, TypeError):
                    pass
            
            user_id = request.query_params.get('user_id')
            if user_id:
                try:
                    user_id = int(user_id)
                    queryset = queryset.filter(user_id=user_id)
                except (ValueError, TypeError):
                    pass
            
            resolved = request.query_params.get('resolved')
            if resolved is not None:
                queryset = queryset.filter(resolved=resolved.lower() == 'true')
            
            session_id = request.query_params.get('session_id')
            if session_id:
                try:
                    session_id = int(session_id)
                    queryset = queryset.filter(session_id=session_id)
                except (ValueError, TypeError):
                    pass
            
            # Order by created_at descending
            queryset = queryset.order_by('-created_at')
            
            # Serialize data
            result_data = []
            for record in queryset:
                result_data.append({
                    'id': record.id,
                    'user_id': record.user_id,
                    'user_name': record.user.name if record.user else None,
                    'polygon_id': record.polygon_id,
                    'polygon_info': {
                        'id': record.polygon.id,
                        'division': record.polygon.division,
                        'block': record.polygon.block,
                        'address': record.polygon.address
                    } if record.polygon else None,
                    'is_no_contact': record.is_no_contact,
                    'reason': record.reason,
                    'reason_display': record.get_reason_display() if record.reason else None,
                    'notes': record.notes,
                    'session_id': record.session_id,
                    'attempt_count': record.attempt_count,
                    'last_attempt_at': record.last_attempt_at,
                    'next_attempt_suggested': record.next_attempt_suggested,
                    'resolved': record.resolved,
                    'resolved_at': record.resolved_at,
                    'resolved_by': record.resolved_by_id,
                    'resolved_by_name': record.resolved_by.name if record.resolved_by else None,
                    'created_at': record.created_at,
                    'updated_at': record.updated_at,
                })
            
            return Response({
                'msg': 'No-contact records fetched successfully',
                'status': 1,
                'data': result_data,
                'count': len(result_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error fetching no-contact records: {str(e)}")

            logger.error(f"Error fetching no-contact records: {str(e)}")
            return Response({
                'msg': f'Error fetching data: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Create a new no-contact record",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'polygon_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['no_one_home', 'unavailable', 'working_hours', 
                          'traveling', 'business_hours', 'after_hours', 'other']
                ),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'next_attempt_suggested': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATETIME
                ),
            },
            required=['polygon_id']
        ),
        responses={
            201: "Created successfully",
            400: "Validation error",
            404: "Polygon not found",
            500: "Internal server error"
        }
    )
    def post(self, request):
        """
        Create a new no-contact record
        """
        try:
            # Validate required fields
            if 'polygon_id' not in request.data:
                return Response({
                    'msg': 'polygon_id is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate polygon exists
            try:
                polygon = Polygon.objects.get(
                    id=request.data['polygon_id'],
                    
                )
            except Polygon.DoesNotExist:
                return Response({
                    'msg': 'Polygon not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if there's already an active no-contact record
            existing_record = NoPropertyContactAvailable.get_active_by_polygon(polygon.id)
            if existing_record:
                return Response({
                    'msg': 'An active no-contact record already exists for this polygon',
                    'status': 0,
                    'data': {'existing_record_id': existing_record.id}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate reason if provided
            if 'reason' in request.data:
                valid_reasons = dict(NoPropertyContactAvailable.NoContactReason.choices).keys()
                if request.data['reason'] not in valid_reasons:
                    return Response({
                        'msg': f'Invalid reason. Must be one of: {", ".join(valid_reasons)}',
                        'status': 0,
                        'data': []
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user if provided
            user = None
            if 'user_id' in request.data:
                try:
                    user = UserModel.objects.get(id=request.data['user_id'])
                except UserModel.DoesNotExist:
                    pass
            
            # Get session if provided
            session = None
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(id=request.data['session_id'])
                except Session.DoesNotExist:
                    pass
            
            # Parse next_attempt_suggested if provided
            next_attempt = None
            if 'next_attempt_suggested' in request.data:
                try:
                    next_attempt = parser.parse(request.data['next_attempt_suggested'])
                except (ValueError, TypeError):
                    pass
            
            # Create no-contact record
            record = NoPropertyContactAvailable.objects.create(
                user=user,
                polygon=polygon,
                is_no_contact=True,
                reason=request.data.get('reason'),
                notes=request.data.get('notes', ''),
                session=session,
                attempt_count=1,
                next_attempt_suggested=next_attempt,
                is_active=True
            )
            
            # Prepare response data
            response_data = {
                'id': record.id,
                'user_id': record.user_id,
                'user_name': record.user.name if record.user else None,
                'polygon_id': record.polygon_id,
                'is_no_contact': record.is_no_contact,
                'reason': record.reason,
                'reason_display': record.get_reason_display() if record.reason else None,
                'notes': record.notes,
                'session_id': record.session_id,
                'attempt_count': record.attempt_count,
                'last_attempt_at': record.last_attempt_at,
                'next_attempt_suggested': record.next_attempt_suggested,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
            }
            
            return Response({
                'msg': 'No-contact record created successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error creating no-contact record: {str(e)}")
            logger.error(f"Error creating no-contact record: {str(e)}")
            return Response({
                'msg': f'Error creating record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Update a no-contact record",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'reason': openapi.Schema(type=openapi.TYPE_STRING),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'session_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'next_attempt_suggested': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: "Updated successfully",
            400: "Validation error",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def put(self, request, record_id=None):
        """
        Update an existing no-contact record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                record_id = int(record_id)
                record = NoPropertyContactAvailable.objects.get(
                    id=record_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except NoPropertyContactAvailable.DoesNotExist:
                return Response({
                    'msg': 'No-contact record not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update fields
            if 'reason' in request.data:
                if request.data['reason']:
                    valid_reasons = dict(NoPropertyContactAvailable.NoContactReason.choices).keys()
                    if request.data['reason'] not in valid_reasons:
                        return Response({
                            'msg': f'Invalid reason. Must be one of: {", ".join(valid_reasons)}',
                            'status': 0,
                            'data': []
                        }, status=status.HTTP_400_BAD_REQUEST)
                record.reason = request.data['reason']
            
            if 'notes' in request.data:
                record.notes = request.data['notes']
            
            if 'user_id' in request.data:
                try:
                    user = UserModel.objects.get(id=request.data['user_id'])
                    record.user = user
                except UserModel.DoesNotExist:
                    record.user = None
            
            if 'session_id' in request.data:
                try:
                    session = Session.objects.get(id=request.data['session_id'])
                    record.session = session
                except Session.DoesNotExist:
                    record.session = None
            
            if 'next_attempt_suggested' in request.data:
                try:
                    record.next_attempt_suggested = parser.parse(request.data['next_attempt_suggested'])
                except (ValueError, TypeError):
                    pass
            
            record.save()
            
            # Prepare response data
            response_data = {
                'id': record.id,
                'user_id': record.user_id,
                'user_name': record.user.name if record.user else None,
                'polygon_id': record.polygon_id,
                'is_no_contact': record.is_no_contact,
                'reason': record.reason,
                'reason_display': record.get_reason_display() if record.reason else None,
                'notes': record.notes,
                'session_id': record.session_id,
                'attempt_count': record.attempt_count,
                'last_attempt_at': record.last_attempt_at,
                'next_attempt_suggested': record.next_attempt_suggested,
                'resolved': record.resolved,
                'created_at': record.created_at,
                'updated_at': record.updated_at,
            }
            
            return Response({
                'msg': 'No-contact record updated successfully',
                'status': 1,
                'data': response_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating no-contact record: {str(e)}")
            return Response({
                'msg': f'Error updating record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Delete a no-contact record (soft delete)",
        responses={
            200: "Deleted successfully",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def delete(self, request, record_id=None):
        """
        Soft delete a no-contact record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                record_id = int(record_id)
                record = NoPropertyContactAvailable.objects.get(
                    id=record_id,
                    
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except NoPropertyContactAvailable.DoesNotExist:
                return Response({
                    'msg': 'No-contact record not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Soft delete
            record.deleted_at = timezone.now()
            record.is_active = False
            record.save()
            
            return Response({
                'msg': 'No-contact record deleted successfully',
                'status': 1,
                'data': []
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting no-contact record: {str(e)}")
            return Response({
                'msg': f'Error deleting record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Increment contact attempt count",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                'next_attempt_suggested': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: "Attempt incremented successfully",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def patch(self, request, record_id=None):
        """
        Increment the contact attempt count for a no-contact record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                record_id = int(record_id)
                record = NoPropertyContactAvailable.objects.get(
                    id=record_id,
                    
                    resolved=False
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except NoPropertyContactAvailable.DoesNotExist:
                return Response({
                    'msg': 'No-contact record not found or already resolved',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Parse next_attempt_suggested if provided
            next_attempt = None
            if 'next_attempt_suggested' in request.data:
                try:
                    next_attempt = parser.parse(request.data['next_attempt_suggested'])
                except (ValueError, TypeError):
                    pass
            
            # Increment attempt
            record.increment_attempt(
                notes=request.data.get('notes'),
                next_attempt_suggested=next_attempt
            )
            
            return Response({
                'msg': 'Contact attempt incremented successfully',
                'status': 1,
                'data': {
                    'id': record.id,
                    'attempt_count': record.attempt_count,
                    'last_attempt_at': record.last_attempt_at,
                    'next_attempt_suggested': record.next_attempt_suggested,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error incrementing contact attempt: {str(e)}")
            return Response({
                'msg': f'Error incrementing attempt: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description="Resolve a no-contact record",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'resolver_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'notes': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['resolver_id']
        ),
        responses={
            200: "Resolved successfully",
            404: "Record not found",
            500: "Internal server error"
        }
    )
    def resolve(self, request, record_id=None):
        """
        Resolve a no-contact record
        """
        try:
            # Get record ID
            record_id = record_id or request.data.get('id')
            
            if not record_id:
                return Response({
                    'msg': 'Record ID is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate resolver_id
            if 'resolver_id' not in request.data:
                return Response({
                    'msg': 'resolver_id is required',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                resolver = UserModel.objects.get(id=request.data['resolver_id'])
            except UserModel.DoesNotExist:
                return Response({
                    'msg': 'Resolver user not found',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            try:
                record_id = int(record_id)
                record = NoPropertyContactAvailable.objects.get(
                    id=record_id,
                    
                    resolved=False
                )
            except (ValueError, TypeError):
                return Response({
                    'msg': 'Invalid record ID',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            except NoPropertyContactAvailable.DoesNotExist:
                return Response({
                    'msg': 'No-contact record not found or already resolved',
                    'status': 0,
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Resolve the record
            record.resolve(resolver, notes=request.data.get('notes'))
            
            return Response({
                'msg': 'No-contact record resolved successfully',
                'status': 1,
                'data': {
                    'id': record.id,
                    'resolved': record.resolved,
                    'resolved_at': record.resolved_at,
                    'resolved_by': record.resolved_by_id,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error resolving no-contact record: {str(e)}")
            return Response({
                'msg': f'Error resolving record: {str(e)}',
                'status': 0,
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)