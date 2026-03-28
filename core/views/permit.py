from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum, F
from decimal import Decimal
import json
import logging

from core.models import AuditLog, BOPEntry, EntryStatus, Session, UserModel, Polygon, Business, BusinessType

logger = logging.getLogger(__name__)

@login_required
def permit_management(request):
    """Render the permit management page"""
    context = {
        'title': 'Business Operating Permit Management',
        'path': 'Permit Management/BOP',
        'status_choices': EntryStatus.choices,
    }
    return render(request, 'core/main/users/permits.html', context)

@login_required
@require_http_methods(["GET"])
def get_permits(request):
    """Get all BOP entries for DataTable"""
    try:
        # Get all BOP entries with related data
        permits = BOPEntry.objects.filter(
            deleted_at__isnull=True
        ).select_related(
            'session',
            'session__polygon',
            'session__collector',
            'reviewed_by'
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status', '')
        session_filter = request.GET.get('session_id', '')
        search = request.GET.get('search', '')
        
        if status_filter:
            permits = permits.filter(status=status_filter)
        
        if session_filter:
            permits = permits.filter(session_id=session_filter)
        
        if search:
            # Search in JSON data fields
            permits = permits.filter(
                Q(data__business_name__icontains=search) |
                Q(data__owner_name__icontains=search) |
                Q(data__account_number__icontains=search) |
                Q(data__phone_number__icontains=search) |
                Q(data__email__icontains=search) |
                Q(data__location__icontains=search)
            )
        
        data = []
        for permit in permits:
            # Extract data from JSON field
            permit_data = permit.data if permit.data else {}
            
            # Get polygon info
            polygon = permit.session.polygon if permit.session else None
            collector = permit.session.collector if permit.session else None
            
            data.append({
                'id': permit.id,
                'entry_index': permit.entry_index,
                'session_id': permit.session_id,
                'session_status': permit.session.status if permit.session else None,
                'business_name': permit_data.get('business_name', ''),
                'owner_name': permit_data.get('owner_name', ''),
                'account_number': permit_data.get('account_number', ''),
                'phone_number': permit_data.get('phone_number', ''),
                'email': permit_data.get('email', ''),
                'location': permit_data.get('location', ''),
                'business_type': permit_data.get('business_type', ''),
                'business_category': permit_data.get('business_category', ''),
                'amount': float(permit_data.get('amount', 0)) if permit_data.get('amount') else 0,
                'status': permit.status,
                'mode': permit.mode,
                'polygon_id': polygon.id if polygon else None,
                'polygon_display': f"Div {polygon.division} / Blk {polygon.block}" if polygon else 'N/A',
                'collector_name': collector.name if collector else 'N/A',
                'reviewed_by': permit.reviewed_by.name if permit.reviewed_by else None,
                'reviewed_at': permit.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if permit.reviewed_at else None,
                'created_at': permit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': permit.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        logger.error(f"Error in get_permits: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_permit_detail(request, permit_id):
    """Get detailed permit information"""
    try:
        permit = get_object_or_404(BOPEntry, id=permit_id, deleted_at__isnull=True)
        permit_data = permit.data if permit.data else {}
        
        # Get related objects
        session = permit.session
        polygon = session.polygon if session else None
        collector = session.collector if session else None
        
        data = {
            'id': permit.id,
            'entry_index': permit.entry_index,
            'session_id': session.id if session else None,
            'session_status': session.status if session else None,
            'mode': permit.mode,
            'status': permit.status,
            'status_display': permit.get_status_display(),
            
            # Business data
            'business_name': permit_data.get('business_name', ''),
            'owner_name': permit_data.get('owner_name', ''),
            'account_number': permit_data.get('account_number', ''),
            'phone_number': permit_data.get('phone_number', ''),
            'email': permit_data.get('email', ''),
            'location': permit_data.get('location', ''),
            'address': permit_data.get('address', ''),
            'digital_address': permit_data.get('digital_address', ''),
            'business_type': permit_data.get('business_type', ''),
            'business_category': permit_data.get('business_category', ''),
            'business_class': permit_data.get('business_class', ''),
            'amount': float(permit_data.get('amount', 0)),
            'flat_rate': float(permit_data.get('flat_rate', 0)) if permit_data.get('flat_rate') else None,
            'additional_info': permit_data.get('additional_info', {}),
            
            # Location data
            'latitude': float(permit_data.get('latitude', 0)) if permit_data.get('latitude') else None,
            'longitude': float(permit_data.get('longitude', 0)) if permit_data.get('longitude') else None,
            'centroid': permit_data.get('centroid', ''),
            
            # Polygon data
            'polygon_id': polygon.id if polygon else None,
            'polygon_display': f"Div {polygon.division} - Blk {polygon.block} (Prop {polygon.property})" if polygon else 'N/A',
            'division': polygon.division if polygon else None,
            'block': polygon.block if polygon else None,
            
            # Collector data
            'collector_id': collector.id if collector else None,
            'collector_name': collector.name if collector else 'N/A',
            'collector_email': collector.email if collector else None,
            
            # Review data
            'reviewed_by': permit.reviewed_by.name if permit.reviewed_by else None,
            'reviewed_by_id': permit.reviewed_by.id if permit.reviewed_by else None,
            'reviewed_at': permit.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if permit.reviewed_at else None,
            'review_notes': permit.review_notes or '',
            
            # Timestamps
            'created_at': permit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': permit.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'revision_of': str(permit.revision_of) if permit.revision_of else None,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error in get_permit_detail: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def approve_permit(request, permit_id):
    """Approve a permit"""
    try:
        # Check if user has permission (supervisor or admin)
        if request.user.profile.role not in ['admin', 'supervisor']:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        permit = get_object_or_404(BOPEntry, id=permit_id, deleted_at__isnull=True)
        data = json.loads(request.body)
        
        with transaction.atomic():
            permit.status = EntryStatus.APPROVED
            permit.reviewed_by = request.user.profile
            permit.reviewed_at = timezone.now()
            permit.review_notes = data.get('review_notes', '')
            permit.save()
            
            # Update session status if all entries are approved
            if permit.session:
                permit.session.update_status()
            
            # Create audit log
            AuditLog.objects.create(
                actor=request.user.profile,
                action='APPROVE_PERMIT',
                entity_type='BOPEntry',
                entity_id=str(permit.id),
                details={
                    'business_name': permit.data.get('business_name', ''),
                    'session_id': permit.session_id,
                    'notes': permit.review_notes
                },
                ip_address=get_client_ip(request)
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Permit #{permit.id} approved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in approve_permit: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def reject_permit(request, permit_id):
    """Reject a permit"""
    try:
        # Check if user has permission (supervisor or admin)
        if request.user.profile.role not in ['admin', 'supervisor']:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        permit = get_object_or_404(BOPEntry, id=permit_id, deleted_at__isnull=True)
        data = json.loads(request.body)
        
        if not data.get('review_notes'):
            return JsonResponse({'success': False, 'error': 'Rejection reason is required'}, status=400)
        
        with transaction.atomic():
            permit.status = EntryStatus.REJECTED
            permit.reviewed_by = request.user.profile
            permit.reviewed_at = timezone.now()
            permit.review_notes = data.get('review_notes', '')
            permit.save()
            
            # Update session status if all entries are rejected
            if permit.session:
                permit.session.update_status()
            
            # Create audit log
            AuditLog.objects.create(
                actor=request.user.profile,
                action='REJECT_PERMIT',
                entity_type='BOPEntry',
                entity_id=str(permit.id),
                details={
                    'business_name': permit.data.get('business_name', ''),
                    'session_id': permit.session_id,
                    'reason': permit.review_notes
                },
                ip_address=get_client_ip(request)
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Permit #{permit.id} rejected'
        })
        
    except Exception as e:
        logger.error(f"Error in reject_permit: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def bulk_approve_permits(request):
    """Bulk approve multiple permits"""
    try:
        # Check if user has permission
        if request.user.profile.role not in ['admin', 'supervisor']:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        data = json.loads(request.body)
        permit_ids = data.get('permit_ids', [])
        review_notes = data.get('review_notes', '')
        
        if not permit_ids:
            return JsonResponse({'success': False, 'error': 'No permit IDs provided'}, status=400)
        
        permits = BOPEntry.objects.filter(id__in=permit_ids, deleted_at__isnull=True)
        approved_count = 0
        
        with transaction.atomic():
            for permit in permits:
                if permit.status == EntryStatus.PENDING:
                    permit.status = EntryStatus.APPROVED
                    permit.reviewed_by = request.user.profile
                    permit.reviewed_at = timezone.now()
                    permit.review_notes = review_notes
                    permit.save()
                    approved_count += 1
                    
                    # Update session status
                    if permit.session:
                        permit.session.update_status()
            
            # Create audit log
            AuditLog.objects.create(
                actor=request.user.profile,
                action='BULK_APPROVE_PERMITS',
                entity_type='BOPEntry',
                details={
                    'permit_ids': permit_ids,
                    'count': approved_count,
                    'notes': review_notes
                },
                ip_address=get_client_ip(request)
            )
        
        return JsonResponse({
            'success': True,
            'message': f'{approved_count} permits approved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in bulk_approve_permits: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["DELETE"])
def delete_permit(request, permit_id):
    """Soft delete a permit"""
    try:
        # Check if user has permission (admin only)
        if request.user.profile.role != 'admin':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        permit = get_object_or_404(BOPEntry, id=permit_id, deleted_at__isnull=True)
        
        permit.deleted_at = timezone.now()
        permit.save()
        
        # Create audit log
        AuditLog.objects.create(
            actor=request.user.profile,
            action='DELETE_PERMIT',
            entity_type='BOPEntry',
            entity_id=str(permit.id),
            details={'business_name': permit.data.get('business_name', '')},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Permit #{permit.id} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in delete_permit: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_permit_stats(request):
    """Get permit statistics"""
    try:
        total_permits = BOPEntry.objects.filter(deleted_at__isnull=True).count()
        
        # Status distribution
        pending_permits = BOPEntry.objects.filter(
            status=EntryStatus.PENDING,
            deleted_at__isnull=True
        ).count()
        
        approved_permits = BOPEntry.objects.filter(
            status=EntryStatus.APPROVED,
            deleted_at__isnull=True
        ).count()
        
        rejected_permits = BOPEntry.objects.filter(
            status=EntryStatus.REJECTED,
            deleted_at__isnull=True
        ).count()
        
        # Recent permits (last 7 days)
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent_permits = BOPEntry.objects.filter(
            created_at__gte=seven_days_ago,
            deleted_at__isnull=True
        ).count()
        
        # Permits by session status
        permits_by_session = BOPEntry.objects.filter(
            deleted_at__isnull=True
        ).values('session__status').annotate(
            count=Count('id')
        )
        
        # Monthly trend (last 6 months)
        from django.db.models.functions import TruncMonth
        monthly_trend = BOPEntry.objects.filter(
            deleted_at__isnull=True,
            created_at__gte=timezone.now() - timezone.timedelta(days=180)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            approved=Count('id', filter=Q(status=EntryStatus.APPROVED)),
            rejected=Count('id', filter=Q(status=EntryStatus.REJECTED))
        ).order_by('month')
        
        # Total permit value
        total_value = 0
        for permit in BOPEntry.objects.filter(deleted_at__isnull=True):
            if permit.data and permit.data.get('amount'):
                try:
                    total_value += float(permit.data.get('amount', 0))
                except:
                    pass
        
        stats = {
            'total_permits': total_permits,
            'pending_permits': pending_permits,
            'approved_permits': approved_permits,
            'rejected_permits': rejected_permits,
            'recent_permits': recent_permits,
            'total_value': total_value,
            'permits_by_session': list(permits_by_session),
            'monthly_trend': list(monthly_trend),
            'approval_rate': round((approved_permits / total_permits * 100), 2) if total_permits > 0 else 0,
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        logger.error(f"Error in get_permit_stats: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def export_permits(request):
    """Export permits data in CSV format"""
    try:
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="permits_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Permit ID', 'Business Name', 'Owner Name', 'Account Number',
            'Phone', 'Email', 'Location', 'Business Type', 'Business Category',
            'Amount (GHS)', 'Status', 'Session ID', 'Polygon', 'Collector',
            'Reviewed By', 'Created At', 'Reviewed At'
        ])
        
        # Get data
        permits = BOPEntry.objects.filter(
            deleted_at__isnull=True
        ).select_related('session', 'session__polygon', 'session__collector', 'reviewed_by')
        
        for permit in permits:
            data = permit.data if permit.data else {}
            polygon = permit.session.polygon if permit.session else None
            collector = permit.session.collector if permit.session else None
            
            writer.writerow([
                permit.id,
                data.get('business_name', ''),
                data.get('owner_name', ''),
                data.get('account_number', ''),
                data.get('phone_number', ''),
                data.get('email', ''),
                data.get('location', ''),
                data.get('business_type', ''),
                data.get('business_category', ''),
                data.get('amount', 0),
                permit.get_status_display(),
                permit.session_id,
                f"Div {polygon.division}/Blk {polygon.block}" if polygon else 'N/A',
                collector.name if collector else 'N/A',
                permit.reviewed_by.name if permit.reviewed_by else '',
                permit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                permit.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if permit.reviewed_at else ''
            ])
        
        return response
        
    except Exception as e:
        logger.error(f"Error in export_permits: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip