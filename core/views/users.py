# Add these imports at the top
from asyncio.log import logger
import json

from django.contrib.auth.hashers import make_password, check_password
from django.core.paginator import Paginator
from django.db.models import Q, Count
import random
import string

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from core.models import AuditLog, UserModel, UserModelRole
from django.contrib.auth import authenticate, login
#import django timezone\
from django.utils import timezone

# User Management Views
@login_required
def user_management(request):
    """Render the user management page"""
    context = {
        'title': 'User Management',
        'path': 'Administration/User Management',
        'roles': UserModelRole.choices,
    }
    return render(request, 'core/main/users/users.html', context)

@login_required
@require_http_methods(["GET"])
def get_users(request):
    """Get all users for DataTable"""
    try:
        # Check if user has permission (admin only)
        # if request.user.profile.role not in ['admin', 'supervisor']:
        #     return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Get all users
        users = UserModel.objects.all().select_related('supervisor')
        
        # Apply filters
        role_filter = request.GET.get('role', '')
        status_filter = request.GET.get('status', '')
        search = request.GET.get('search', '')
        
        if role_filter:
            users = users.filter(role=role_filter)
        
        if status_filter:
            is_active = status_filter == 'active'
            users = users.filter(is_active=is_active)
        
        if search:
            users = users.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Order by created_at desc
        users = users.order_by('-created_at')
        
        data = []
        for user in users:
            # Get subordinate count
            subordinate_count = UserModel.objects.filter(supervisor=user).count()
            
            data.append({
                'id': user.id,
                'user_id': user.user.id if user.user else None,
                'employee_id': user.employee_id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone or '',
                'role': user.role,
                'role_display': user.get_role_display(),
                'supervisor_name': user.supervisor.name if user.supervisor else 'None',
                'supervisor_id': user.supervisor.id if user.supervisor else None,
                'is_active': user.is_active,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                'subordinate_count': subordinate_count,
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        logger.error(f"Error in get_users: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def create_user(request):
    """Create a new user"""
    try:
        # Check if user has permission (admin only)
        # if request.user.profile.role not in ['admin']:
        #     return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['name', 'email', 'employee_id', 'role']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({'success': False, 'error': f'{field} is required'}, status=400)
        
        # Check if email already exists
        if UserModel.objects.filter(email=data['email']).exists():
            return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
        
        # Check if employee_id already exists
        if UserModel.objects.filter(employee_id=data['employee_id']).exists():
            return JsonResponse({'success': False, 'error': 'Employee ID already exists'}, status=400)
        
        # Check if linked Django user exists, create if not
        django_user = None
        try:
            django_user = User.objects.get(username=data['email'])
        except User.DoesNotExist:
            # Generate a random password if not provided
            password = data.get('password', generate_random_password())
            django_user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                password=password,
                first_name=data.get('name', '').split()[0] if data.get('name') else '',
                last_name=' '.join(data.get('name', '').split()[1:]) if data.get('name') else ''
            )
        
        # Create UserModel
        user = UserModel(
            user=django_user,
            employee_id=data['employee_id'],
            name=data['name'],
            email=data['email'],
            phone=data.get('phone', ''),
            role=data['role'],
            is_active=data.get('is_active', True),
        )
        
        # Set password if provided
        if data.get('password'):
            user.password = data['password']
        
        # Set supervisor if provided
        if data.get('supervisor_id'):
            try:
                supervisor = UserModel.objects.get(id=data['supervisor_id'])
                user.supervisor = supervisor
            except UserModel.DoesNotExist:
                pass
        
        user.save()
        
        # Log the action
        AuditLog.objects.create(
            actor=request.user,
            action='CREATE_USER',
            entity_type='UserModel',
            entity_id=str(user.id),
            details={'name': user.name, 'email': user.email, 'role': user.role},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'User {user.name} created successfully',
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        logger.error(f"Error in create_user: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_user_detail(request, user_id):
    """Get user details for editing"""
    try:
        # Check if user has permission
        # if request.user.profile.role not in ['admin', 'supervisor']:
        #     return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        user = get_object_or_404(UserModel, id=user_id)
        
        data = {
            'id': user.id,
            'user_id': user.user.id if user.user else None,
            'employee_id': user.employee_id,
            'name': user.name,
            'email': user.email,
            'phone': user.phone or '',
            'role': user.role,
            'supervisor_id': user.supervisor.id if user.supervisor else None,
            'is_active': user.is_active,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error in get_user_detail: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_user(request, user_id):
    """Update user details"""
    try:
        # Check if user has permission
        # if request.user.profile.role not in ['admin', 'supervisor']:
        #     return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        user = get_object_or_404(UserModel, id=user_id)
        data = json.loads(request.body)
        
        # Update basic fields
        if 'name' in data:
            user.name = data['name']
            # Update Django user if exists
            if user.user:
                name_parts = data['name'].split()
                user.user.first_name = name_parts[0] if name_parts else ''
                user.user.last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                user.user.save()
        
        if 'email' in data and data['email'] != user.email:
            # Check if email already exists for other users
            if UserModel.objects.filter(email=data['email']).exclude(id=user_id).exists():
                return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
            user.email = data['email']
            # Update Django user email
            if user.user:
                user.user.email = data['email']
                user.user.username = data['email']
                user.user.save()
        
        if 'phone' in data:
            user.phone = data['phone']
        
        if 'role' in data:
            # Only admin can change role to admin
            if data['role'] == 'admin' :
                return JsonResponse({'success': False, 'error': 'Only admin can assign admin role'}, status=403)
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
            # Update Django user active status
            if user.user:
                user.user.is_active = data['is_active']
                user.user.save()
        
        if 'supervisor_id' in data:
            if data['supervisor_id']:
                try:
                    supervisor = UserModel.objects.get(id=data['supervisor_id'])
                    # Prevent circular reference
                    if supervisor.id == user.id:
                        return JsonResponse({'success': False, 'error': 'Cannot set self as supervisor'}, status=400)
                    user.supervisor = supervisor
                except UserModel.DoesNotExist:
                    pass
            else:
                user.supervisor = None
        
        if 'password' in data and data['password']:
            user.password = data['password']
        
        user.save()
        
        # Log the action
        AuditLog.objects.create(
            actor=request.user.profile,
            action='UPDATE_USER',
            entity_type='UserModel',
            entity_id=str(user.id),
            details={'name': user.name, 'email': user.email},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'User {user.name} updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in update_user: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["DELETE"])
def delete_user(request, user_id):
    """Delete user (soft delete by deactivating)"""
    try:
        # Check if user has permission
        if request.user.profile.role != 'admin':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        user = get_object_or_404(UserModel, id=user_id)
        
        # Prevent deleting yourself
        if user.id == request.user.profile.id:
            return JsonResponse({'success': False, 'error': 'Cannot delete your own account'}, status=400)
        
        # Soft delete by deactivating
        user.is_active = False
        if user.user:
            user.user.is_active = False
            user.user.save()
        user.save()
        
        # Log the action
        AuditLog.objects.create(
            actor=request.user.profile,
            action='DELETE_USER',
            entity_type='UserModel',
            entity_id=str(user.id),
            details={'name': user.name, 'email': user.email},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'User {user.name} has been deactivated'
        })
        
    except Exception as e:
        logger.error(f"Error in delete_user: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def bulk_delete_users(request):
    """Bulk delete users"""
    try:
        # Check if user has permission
        if request.user.profile.role != 'admin':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return JsonResponse({'success': False, 'error': 'No user IDs provided'}, status=400)
        
        # Prevent deleting yourself
        if request.user.profile.id in user_ids:
            return JsonResponse({'success': False, 'error': 'Cannot delete your own account'}, status=400)
        
        users = UserModel.objects.filter(id__in=user_ids)
        deleted_count = 0
        
        for user in users:
            user.is_active = False
            if user.user:
                user.user.is_active = False
                user.user.save()
            user.save()
            deleted_count += 1
        
        # Log the action
        AuditLog.objects.create(
            actor=request.user.profile,
            action='BULK_DELETE_USERS',
            entity_type='UserModel',
            details={'user_ids': user_ids, 'count': deleted_count},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} users have been deactivated'
        })
        
    except Exception as e:
        logger.error(f"Error in bulk_delete_users: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def reset_user_password(request, user_id):
    """Reset user password"""
    try:
        # Check if user has permission
        if request.user.profile.role not in ['admin', 'supervisor']:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        user = get_object_or_404(UserModel, id=user_id)
        
        # Generate new random password
        new_password = generate_random_password()
        user.password = new_password
        user.save()
        
        # Update Django user password if exists
        if user.user:
            user.user.set_password(new_password)
            user.user.save()
        
        # Log the action
        AuditLog.objects.create(
            actor=request.user.profile,
            action='RESET_PASSWORD',
            entity_type='UserModel',
            entity_id=str(user.id),
            details={'name': user.name},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Password reset for {user.name}',
            'new_password': new_password  # Only show this in response, should be communicated securely
        })
        
    except Exception as e:
        logger.error(f"Error in reset_user_password: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_user_stats(request):
    """Get user management statistics"""
    try:
        total_users = UserModel.objects.count()
        active_users = UserModel.objects.filter(is_active=True).count()
        inactive_users = UserModel.objects.filter(is_active=False).count()
        
        # Role distribution
        role_stats = UserModel.objects.values('role').annotate(
            count=Count('id')
        )
        
        # Supervisor stats
        supervisors = UserModel.objects.filter(role__in=['admin', 'supervisor'], is_active=True)
        supervisor_stats = []
        for sup in supervisors:
            subordinate_count = UserModel.objects.filter(supervisor=sup, is_active=True).count()
            supervisor_stats.append({
                'name': sup.name,
                'role': sup.get_role_display(),
                'subordinate_count': subordinate_count
            })
        
        # Recent users (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_users = UserModel.objects.filter(created_at__gte=thirty_days_ago).count()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'recent_users': recent_users,
            'role_distribution': list(role_stats),
            'supervisor_stats': supervisor_stats,
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        logger.error(f"Error in get_user_stats: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_supervisors(request):
    """Get list of users who can be supervisors"""
    try:
        supervisors = UserModel.objects.filter(
            role__in=['admin', 'supervisor'],
            is_active=True
        ).order_by('name')
        
        data = []
        for sup in supervisors:
            data.append({
                'id': sup.id,
                'name': sup.name,
                'email': sup.email,
                'role': sup.get_role_display(),
                'subordinate_count': UserModel.objects.filter(supervisor=sup).count()
            })
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error in get_supervisors: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

def generate_random_password(length=10):
    """Generate a random password"""
    characters = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(random.choice(characters) for _ in range(length))

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip