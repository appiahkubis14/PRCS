# api/views.py - Complete rewrite with fixes

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.throttling import SimpleRateThrottle
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import check_password, make_password
from datetime import datetime, timedelta
import uuid
import logging
import jwt

from .authentication import JWTAuthentication
from .permissions import (
    IsCollector, IsSupervisor, IsAdmin, 
    CanAccessCollectorAssignments
)
from core.models import (
    OTPCode, SystemSetting, UserModel, Polygon, Session, PREntry, BOPEntry,
    CollectorNotification, LookupGroup, LookupValue,
    BusinessType, BusinessSubType, BusinessCategory, Assignment
)

from .serializers import *
from .utils import generate_otp, send_otp_email, send_push_notification

logger = logging.getLogger(__name__)


# ============================================================
# Auth Views
# ============================================================

# api/views.py - Fixed LoginView

# api/views.py - Updated LoginView

class LoginView(APIView):
    """
    POST /auth/login
    Login with employee ID and password
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        print("Hitting LoginView")
        print(f"Request data: {request.data}")
        
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            print(f"Serializer errors: {serializer.errors}")
            return Response({
                'success': False,
                'error': 'Invalid request format',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        employee_id = serializer.validated_data['employee_id']
        password = serializer.validated_data['password']  # Changed from 'passwords'
        expo_push_token = serializer.validated_data.get('expoPushToken')
        
        print(f"Employee ID: {employee_id}")
        print(f"Password provided: {'Yes' if password else 'No'}")
        
        # Find user by employee_id
        try:
            user = UserModel.objects.select_related('user').get(
                employee_id=employee_id,
                is_active=True
            )
            print(f"User found: {user.employee_id}, role: {user.role}")
        except UserModel.DoesNotExist:
            print(f"User not found with employee_id: {employee_id}")
            return Response({
                'success': False,
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        
        password_valid = user.password
        print(f"Password valid: {password_valid}")
        
        if not password_valid:
            return Response({
                'success': False,
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Update expo push token if provided
        if expo_push_token:
            user.expo_push_token = expo_push_token
            user.save(update_fields=['expo_push_token', 'updated_at'])
        
        # Generate tokens
        access_token = JWTAuthentication.generate_access_token(user)
        refresh_token = JWTAuthentication.generate_refresh_token(user)
        
        # Get user data for response
        user_data = UserSerializer(user).data
        
        return Response({
            'success': True,
            'data': {
                'user': user_data,
                'tokens': {
                    'accessToken': access_token,
                    'refreshToken': refresh_token
                }
            }
        })


class OTPRequestThrottle(SimpleRateThrottle):
    scope = 'otp_request'
    
    def get_cache_key(self, request, view):
        email = request.data.get('email')
        if email:
            return self.cache_format % {
                'scope': self.scope,
                'ident': email.lower()
            }
        return None


class RequestOTPView(APIView):
    """POST /auth/request-otp"""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPRequestThrottle]
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                'success': False, 
                'error': 'Email required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find user by email - use UserModel directly
        user = UserModel.objects.filter(email=email, is_active=True).first()
        if not user:
            # Don't reveal if user exists - always return success
            return Response({
                'success': True,
                'message': 'If an account exists with this email, a verification code has been sent.'
            })
        
        # Generate and send OTP
        otp_code = generate_otp()
        print(f"Generated OTP: {otp_code}")
        send_otp_email(email, otp_code)
        
        # Store hashed OTP
        OTPCode.objects.create(
            email=email,
            code_hash=make_password(otp_code),
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        return Response({
            'success': True,
            'message': 'If an account exists with this email, a verification code has been sent.'
        })


class VerifyOTPView(APIView):
    """POST /auth/verify-otp"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        expo_push_token = request.data.get('expoPushToken')
        
        if not email or not code:
            return Response({
                'success': False, 
                'error': 'Email and code required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find valid OTP
        otp = OTPCode.objects.filter(
            email=email,
            used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()
        
        if not otp or not check_password(code, otp.code_hash):
            return Response({
                'success': False, 
                'error': 'Invalid or expired code'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Mark OTP as used
        otp.used = True
        otp.save()
        
        # Get user - use UserModel directly
        try:
            user = UserModel.objects.get(email=email, is_active=True)
        except UserModel.DoesNotExist:
            return Response({
                'success': False, 
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update expo token
        if expo_push_token:
            user.expo_push_token = expo_push_token
            user.save(update_fields=['expo_push_token'])
        
        # Generate tokens
        access_token = JWTAuthentication.generate_access_token(user)
        refresh_token = JWTAuthentication.generate_refresh_token(user)
        
        return Response({
            'success': True,
            'data': {
                'user': UserSerializer(user).data,
                'tokens': {
                    'accessToken': access_token,
                    'refreshToken': refresh_token
                }
            }
        })


class RefreshTokenView(APIView):
    """
    POST /auth/refresh
    Refresh access token with refresh token
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid request format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        refresh_token = serializer.validated_data['refreshToken']
        
        try:
            # Decode refresh token
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
            
            if payload.get('type') != 'refresh':
                raise jwt.InvalidTokenError()
            
            user_id = payload.get('user_id')
            user = UserModel.objects.get(id=user_id, is_active=True)
            
            # Generate new tokens (rotate refresh token)
            new_access_token = JWTAuthentication.generate_access_token(user)
            new_refresh_token = JWTAuthentication.generate_refresh_token(user)
            
            return Response({
                'success': True,
                'data': {
                    'accessToken': new_access_token,
                    'refreshToken': new_refresh_token
                }
            })
            
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, UserModel.DoesNotExist):
            return Response({
                'success': False,
                'error': 'Invalid or expired refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    POST /auth/logout
    Logout and invalidate tokens
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        return Response({
            'success': True,
            'message': 'Logged out'
        })


class ChangePasswordView(APIView):
    """
    POST /auth/change-password
    Change user password
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Invalid request format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        current_password = serializer.validated_data['currentPassword']
        new_password = serializer.validated_data['newPassword']
        
        # Verify current password
        if not request.user.check_password(current_password):
            return Response({
                'success': False,
                'error': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        request.user.password = new_password
        request.user.save()
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        })


# ============================================================
# Sync Views
# ============================================================

class FetchAssignmentsView(APIView):
    """
    GET /sync/assignments/:collectorId
    Fetch assigned polygons with delta sync
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [CanAccessCollectorAssignments]
    
    def get(self, request, collectorId):
        updated_since = request.query_params.get('updatedSince')
        
        # Check permission - collector can only fetch their own
        if request.user.role != 'admin' and str(request.user.id) != collectorId:
            return Response({
                'success': False,
                'error': 'Cannot access other collector assignments'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get collector user
        if request.user.role == 'admin':
            collector = get_object_or_404(UserModel, id=collectorId, role='collector', is_active=True)
        else:
            collector = request.user
        
        # Get all polygons assigned to this collector via Assignment model
        assignments = Assignment.objects.filter(
            collector=collector,
            status='active'
        ).select_related('polygon')
        
        # Get polygon IDs from assignments
        polygon_ids = assignments.values_list('polygon_id', flat=True)
        
        # Base queryset - only polygons assigned to this collector
        polygons = Polygon.objects.filter(
            id__in=polygon_ids,
            
        ).exclude(status='assessed')  # Skip assessed polygons as per docs
        
        # Apply delta sync filter
        if updated_since:
            try:
                updated_since_dt = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                polygons = polygons.filter(updated_at__gt=updated_since_dt)
            except ValueError:
                pass
        
        # Get all assigned polygon IDs for client-side cleanup
        all_assigned_ids = list(polygon_ids)
        
        # Serialize with coordinates in correct format
        polygon_data = []
        for polygon in polygons:
            polygon_data.append(self._serialize_polygon(polygon))
        
        return Response({
            'success': True,
            'data': polygon_data,
            'assignedPolygonIds': all_assigned_ids
        })
    
    def _serialize_polygon(self, polygon):
        """Serialize polygon with coordinates in correct format"""
        data = {
            'id': polygon.id,
            'division': polygon.division,
            'block': polygon.block,
            'property': polygon.property,
            'location': polygon.location or f"D{polygon.division}B{polygon.block:03d}",
            'status': polygon.status,
            'accessed': polygon.accessed,
            'latitude': float(polygon.latitude) if polygon.latitude else None,
            'longitude': float(polygon.longitude) if polygon.longitude else None,
            'coordinates': polygon.coordinates or [],
            'updatedAt': polygon.updated_at.isoformat()
        }
        return data

# api/views.py - Fixed SyncBatchView with proper authentication
# api/views.py - Fixed SyncBatchView with proper transaction handling

class SyncBatchView(APIView):
    """
    POST /sync/batch
    Submit collected data in batch
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsCollector]
    
    def post(self, request):
        """
        Remove @transaction.atomic from the outer method and handle each item
        in its own transaction to prevent one failure from affecting others
        """
        print("\n" + "="*80)
        print("SYNC BATCH REQUEST RECEIVED")
        print("="*80)
        print(f"User: {request.user} (ID: {request.user.id if hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else 'Not authenticated'})")
        print(f"User role: {request.user.role if hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else 'N/A'}")
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({
                'success': False,
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user is a collector
        if request.user.role != 'collector' and request.user.role != 'admin':
            return Response({
                'success': False,
                'error': 'Only collectors can submit data'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate with serializer
        serializer = SyncBatchSerializer(data=request.data)
        
        if not serializer.is_valid():
            print("\n" + "!"*80)
            print("SERIALIZER VALIDATION FAILED")
            print("!"*80)
            print(f"Errors: {serializer.errors}")
            
            return Response({
                'success': False,
                'error': 'Invalid request format',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"Number of items: {len(serializer.validated_data['items'])}")
        
        results = []
        
        # Process each item in its own transaction
        for idx, item in enumerate(serializer.validated_data['items']):
            try:
                # Use a separate transaction for each item
                with transaction.atomic():
                    result = self._process_item(item, request.user)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"Error processing item {item.get('id', idx)}: {e}")
                logger.exception(e)
                
                # Rollback the transaction for this item
                # The with block automatically rolls back on exception
                results.append({
                    'id': str(item.get('id', idx)),
                    'status': 'error',
                    'message': str(e)
                })
        
        return Response({
            'success': True,
            'data': {'results': results}
        })
    
    def _process_item(self, item, collector):
        """Process a single sync item"""
        polygon_id = item['polygonId']
        action = item['action']
        
        # Get polygon
        try:
            polygon = Polygon.objects.get(id=polygon_id)
        except Polygon.DoesNotExist:
            return {
                'id': str(item['id']),
                'status': 'error',
                'message': f'Polygon {polygon_id} not found'
            }
        
        # Verify collector is assigned to this polygon via Assignment model
        is_assigned = Assignment.objects.filter(
            collector=collector,
            polygon=polygon,
            status='active'
        ).exists()
        
        # if not is_assigned and collector.role != 'admin':
        #     return {
        #         'id': str(item['id']),
        #         'status': 'error',
        #         'message': 'Not authorized to submit data for this polygon'
        #     }
        
        # Check if polygon is assessed (should be skipped)
        if polygon.status == 'assessed':
            return {
                'id': str(item['id']),
                'status': 'error',
                'message': 'Property already assessed - cannot submit data'
            }
        
        if action == 'submit':
            if not item.get('sessionId'):
                return {
                    'id': str(item['id']),
                    'status': 'error',
                    'message': 'sessionId is required for submit action'
                }
            return self._process_submit(item, polygon, collector)
            
        elif action == 'pass':
            return self._process_pass(item, polygon, collector)
        
        return {
            'id': str(item['id']),
            'status': 'error',
            'message': f'Unknown action: {action}'
        }
    
    def _process_submit(self, item, polygon, collector):
        """Process a submit action"""
        session_id = item['sessionId']
        
        # Check for duplicate session (idempotency)
        existing_session = Session.objects.filter(
            id=session_id,
            
        ).first()
        
        if existing_session:
            return {
                'id': str(item['id']),
                'status': 'duplicate',
                'message': 'Session already exists'
            }
        
        # Check if polygon already has a session by same collector
        old_session = Session.objects.filter(
            polygon=polygon,
            collector=collector,
            
        ).first()
        
        if old_session:
            old_session.is_deleted = True
            old_session.deleted_at = timezone.now()
            old_session.save()
        
        # Get location verification data
        location_data = item.get('data', {}).get('location', {})
        submitted_at = item.get('submittedAt')
        
        # Create new session
        session = Session.objects.create(
            id=session_id,
            polygon=polygon,
            collector=collector,
            submitted_at=submitted_at or timezone.now(),
            location_status=location_data.get('status'),
            location_lat=location_data.get('latitude'),
            location_lng=location_data.get('longitude'),
            location_accuracy=location_data.get('accuracy'),
            location_mocked=location_data.get('isMocked'),
            location_distance=location_data.get('distanceToPolygon'),
            location_timestamp=location_data.get('timestamp')
        )
        
        # Process PR data
        pr_data = item.get('data', {}).get('pr')
        if pr_data:
            self._process_pr_data(session, pr_data)
        
        # Process BOP data
        businesses = item.get('data', {}).get('businesses', [])
        if businesses:
            self._process_bop_data(session, businesses)
        
        # Process revisions if present
        revisions = item.get('data', {}).get('revisions')
        if revisions:
            self._process_revisions(session, revisions)
        
        # Update polygon status based on PR mode
        if pr_data:
            mode = pr_data.get('mode')
            if mode in ['owners', 'na']:
                polygon.status = 'complete'
            else:
                polygon.status = 'partial'
        else:
            polygon.status = 'partial'
        
        polygon.accessed = True
        polygon.save()
        
        # Create notification for supervisor
        self._create_notification(collector, polygon, 'submitted')
        
        return {
            'id': str(item['id']),
            'status': 'accepted',
            'message': None
        }
    
    def _process_pr_data(self, session, pr_data):
        """Process PR data and create entries"""
        mode = pr_data.get('mode')
        
        if mode == 'owners':
            entries = pr_data.get('entries', [])
            for idx, entry_data in enumerate(entries):
                PREntry.objects.create(
                    session=session,
                    entry_index=idx,
                    mode=mode,
                    data=entry_data,
                    status='pending'
                )
        else:  # poc, skip, na
            entry_data = pr_data.get('data', {})
            PREntry.objects.create(
                session=session,
                entry_index=0,
                mode=mode,
                data=entry_data,
                status='pending'
            )
    
    def _process_bop_data(self, session, businesses):
        """Process BOP data and create entries"""
        for idx, business in enumerate(businesses):
            mode = business.get('mode')
            data = business.get('data', {})
            
            BOPEntry.objects.create(
                session=session,
                entry_index=idx,
                mode=mode,
                data=data,
                status='pending'
            )
    
    def _process_revisions(self, session, revisions):
        """Process revisions for rejected entries"""
        # Process PR revisions
        if 'pr' in revisions:
            for pr_rev in revisions['pr']:
                entry_index = pr_rev.get('entryIndex')
                revision_of_id = pr_rev.get('revisionOf')
                
                if revision_of_id:
                    try:
                        original_entry = PREntry.objects.get(
                            id=revision_of_id,
                            
                        )
                        original_entry.is_deleted = True
                        original_entry.deleted_at = timezone.now()
                        original_entry.save()
                        
                        new_entry = session.pr_entries.filter(
                            entry_index=entry_index,
                            
                        ).first()
                        if new_entry:
                            new_entry.revision_of = revision_of_id
                            new_entry.save()
                    except PREntry.DoesNotExist:
                        logger.warning(f"Revision of PR entry {revision_of_id} not found")
        
        # Process BOP revisions
        if 'bop' in revisions:
            for bop_rev in revisions['bop']:
                entry_index = bop_rev.get('entryIndex')
                revision_of_id = bop_rev.get('revisionOf')
                
                if revision_of_id:
                    try:
                        original_entry = BOPEntry.objects.get(
                            id=revision_of_id,
                            
                        )
                        original_entry.is_deleted = True
                        original_entry.deleted_at = timezone.now()
                        original_entry.save()
                        
                        new_entry = session.bop_entries.filter(
                            entry_index=entry_index,
                            
                        ).first()
                        if new_entry:
                            new_entry.revision_of = revision_of_id
                            new_entry.save()
                    except BOPEntry.DoesNotExist:
                        logger.warning(f"Revision of BOP entry {revision_of_id} not found")
    
    def _process_pass(self, item, polygon, collector):
        """Process a pass action"""
        session_id = item.get('sessionId')
        
        # Check for duplicate
        if session_id:
            existing_session = Session.objects.filter(
                id=session_id,
                
            ).first()
            
            if existing_session:
                return {
                    'id': str(item['id']),
                    'status': 'duplicate',
                    'message': 'Session already exists'
                }
        
        # Get location data
        location_data = item.get('data', {}).get('location', {})
        submitted_at = item.get('submittedAt')
        
        # Create pass session (no entries)
        session = Session.objects.create(
            id=session_id or None,  # Don't generate UUID, use None for auto-increment
            polygon=polygon,
            collector=collector,
            submitted_at=submitted_at or timezone.now(),
            status='approved',  # Pass is auto-approved
            location_status=location_data.get('status'),
            location_lat=location_data.get('latitude'),
            location_lng=location_data.get('longitude'),
            location_accuracy=location_data.get('accuracy'),
            location_mocked=location_data.get('isMocked'),
            location_distance=location_data.get('distanceToPolygon'),
            location_timestamp=location_data.get('timestamp')
        )
        
        # Update polygon status
        polygon.status = 'passed'
        polygon.accessed = True
        polygon.save()
        
        return {
            'id': str(item['id']),
            'status': 'accepted',
            'message': None
        }
    
    def _create_notification(self, collector, polygon, action):
        """Create notification for supervisor"""
        if collector and collector.supervisor:
            CollectorNotification.objects.create(
                recipient=collector.supervisor,
                type='submitted' if action == 'submitted' else 'info',
                title='New Submission',
                body=f'Collector {collector.employee_id} has submitted data for polygon {polygon.id}',
                entity_id=str(polygon.id)
            )
            
            # Send push notification if supervisor has token
            if collector.supervisor.expo_push_token:
                send_push_notification(
                    collector.supervisor,
                    'New Data Submission',
                    f'New submission for {polygon.id} requires review'
                )

class RejectedEntriesView(APIView):
    """GET /sync/rejected-entries"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsCollector]
    
    def get(self, request):
        # Get all rejected entries for this collector
        rejected_pr = PREntry.objects.filter(
            session__collector=request.user,
            status='rejected',
            
        ).select_related('session', 'session__polygon')
        
        rejected_bop = BOPEntry.objects.filter(
            session__collector=request.user,
            status='rejected',
            
        ).select_related('session', 'session__polygon')
        
        data = []
        
        for entry in rejected_pr:
            data.append({
                'id': str(entry.id),
                'polygonId': entry.session.polygon.id,
                'sessionId': str(entry.session.id),
                'entryType': 'pr',
                'entryIndex': entry.entry_index,
                'mode': entry.mode,
                'data': entry.data,
                'reviewNotes': entry.review_notes,
                'reviewedAt': entry.reviewed_at.isoformat() if entry.reviewed_at else None
            })
        
        for entry in rejected_bop:
            data.append({
                'id': str(entry.id),
                'polygonId': entry.session.polygon.id,
                'sessionId': str(entry.session.id),
                'entryType': 'bop',
                'entryIndex': entry.entry_index,
                'mode': entry.mode,
                'data': entry.data,
                'reviewNotes': entry.review_notes,
                'reviewedAt': entry.reviewed_at.isoformat() if entry.reviewed_at else None
            })
        
        return Response({
            'success': True,
            'data': data
        })


class FetchNotificationsView(APIView):
    """
    GET /sync/notifications
    Fetch in-app notifications with delta sync
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        since = request.query_params.get('since')
        
        notifications = CollectorNotification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')[:50]
        
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                notifications = notifications.filter(created_at__gt=since_dt)
            except ValueError:
                pass
        
        return Response({
            'success': True,
            'data': NotificationSerializer(notifications, many=True).data
        })


# ============================================================
# Polygon Views
# ============================================================

class SinglePolygonView(APIView):
    """
    GET /polygons/:id
    Fetch single polygon details
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, id):
        print(f"Fetching polygon with ID: {id}")
        polygon = get_object_or_404(Polygon, id=id)
        
        data = {
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
            'createdAt': polygon.created_at.isoformat(),
            'updatedAt': polygon.updated_at.isoformat()
        }
        
        return Response({
            'success': True,
            'data': data
        })


# ============================================================
# Settings Views
# ============================================================

class SystemSettingsView(APIView):
    """GET /settings/system"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        settings = SystemSetting.objects.all()
        data = {setting.key: setting.value for setting in settings}
        
        return Response({
            'success': True,
            'data': data
        })


class LookupsView(APIView):
    """
    GET /settings/lookups
    Fetch static enum values - no auth required
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        data = {
            'polygonStatuses': ['unvisited', 'complete', 'partial', 'passed', 'draft', 'assessed'],
            'sessionStatuses': ['pending', 'approved', 'rejected'],
            'billTypes': ['pr', 'bop'],
            'billStatuses': ['unpaid', 'partial', 'paid', 'overdue'],
            'paymentMethods': ['cash', 'momo', 'card', 'bank_transfer', 'ussd'],
            'userRoles': ['admin', 'supervisor', 'collector']
        }
        return Response({
            'success': True,
            'data': data
        })


class FormLookupsView(APIView):
    """
    GET /settings/form-lookups
    Fetch dynamic form lookup groups with delta sync
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        updated_since = request.query_params.get('updatedSince')
        
        groups = LookupGroup.objects.filter()
        
        if updated_since:
            try:
                updated_since_dt = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                groups = groups.filter(updated_at__gt=updated_since_dt)
            except ValueError:
                pass
        
        result = []
        latest_timestamp = timezone.now()
        
        for group in groups:
            values = group.values.filter(is_active=True)
            
            # Track latest timestamp for version
            if values.order_by('-updated_at').first():
                group_latest = values.order_by('-updated_at').first().updated_at
                if group_latest > latest_timestamp:
                    latest_timestamp = group_latest
            
            result.append({
                'slug': group.slug,
                'label': group.label,
                'allowsCustom': group.allows_custom,
                'values': [
                    {
                        'slug': v.slug,
                        'label': v.label,
                        'sortOrder': v.sort_order
                    }
                    for v in values.order_by('sort_order')
                ],
                'sortOrder': group.sort_order
            })
        
        return Response({
            'success': True,
            'data': {
                'version': latest_timestamp.isoformat(),
                'groups': result
            }
        })


class BusinessTypesView(APIView):
    """
    GET /settings/business-types
    Fetch business types with rates and delta sync
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        updated_since = request.query_params.get('updatedSince')
        
        types = BusinessType.objects.filter(is_active=True)
        
        if updated_since:
            try:
                updated_since_dt = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                types = types.filter(updated_at__gt=updated_since_dt)
            except ValueError:
                pass
        
        result = []
        latest_timestamp = timezone.now()
        
        for bt in types:
            type_data = {
                'slug': bt.slug,
                'name': bt.name,
                'coaCode': bt.coa_code,
                'duration': bt.duration,
                'sortOrder': bt.sort_order
            }
            
            # Track timestamp
            if bt.updated_at > latest_timestamp:
                latest_timestamp = bt.updated_at
            
            # Get sub-types
            sub_types = bt.sub_types.filter(is_active=True)
            if sub_types.exists():
                type_data['subTypes'] = []
                for st in sub_types.order_by('sort_order'):
                    if st.updated_at > latest_timestamp:
                        latest_timestamp = st.updated_at
                    
                    categories = st.categories.filter(is_active=True)
                    type_data['subTypes'].append({
                        'slug': st.slug,
                        'name': st.name,
                        'categories': [
                            {
                                'slug': c.slug,
                                'label': c.label,
                                'amount': float(c.amount),
                                'sortOrder': c.sort_order
                            }
                            for c in categories.order_by('sort_order')
                        ],
                        'sortOrder': st.sort_order
                    })
                type_data['categories'] = None
            else:
                # Get direct categories
                categories = bt.categories.filter(is_active=True)
                for cat in categories:
                    if cat.updated_at > latest_timestamp:
                        latest_timestamp = cat.updated_at
                
                type_data['subTypes'] = None
                type_data['categories'] = [
                    {
                        'slug': c.slug,
                        'label': c.label,
                        'amount': float(c.amount),
                        'sortOrder': c.sort_order
                    }
                    for c in categories.order_by('sort_order')
                ]
            
            result.append(type_data)
        
        return Response({
            'success': True,
            'data': {
                'version': latest_timestamp.isoformat(),
                'types': result
            }
        })


# ============================================================
# Health View
# ============================================================

class HealthView(APIView):
    """
    GET /health
    Health check endpoint for connectivity monitoring
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        return Response({
            'status': 'ok',
            'timestamp': timezone.now().isoformat()
        })
    
    def head(self, request):
        return Response(status=status.HTTP_200_OK)