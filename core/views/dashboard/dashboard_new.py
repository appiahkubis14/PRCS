# core/views/dashboard_views.py

from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q, F, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model
import json

from core.models import (
    Business, Bill, Session, Polygon, UserModel, 
    PropertyRate, BOPEntry, PREntry
)

User = get_user_model()


@login_required
def field_collection_dashboard(request):
    """Render the field collection dashboard"""
    # Get all field collectors
    field_collectors = UserModel.objects.filter(
        role='collector',
        is_active=True
    ).order_by('name')
    
    return render(request, 'core/main/dashboard/dashboard.html', {
        'field_collectors': field_collectors
    })


@require_GET
@login_required
def field_dashboard_stats(request):
    """Get field collection statistics"""
    try:
        user_id = request.GET.get('user_id', 'all')
        days = int(request.GET.get('days', 30))
        
        # Base querysets
        sessions = Session.objects.filter(deleted_at__isnull=True)
        polygons = Polygon.objects.all()
        businesses = Business.objects.filter(is_deleted=False)
        
        # Filter by user if specified
        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)
            polygons = polygons.filter(assigned_to_user_id=user_id)
        
        # Calculate dates
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        pace_start = end_date - timedelta(days=28)
        
        # Total Passes (total sessions submitted)
        total_passes = sessions.count()
        
        # Passed Properties (complete polygons)
        passed_properties = polygons.filter(status='complete').count()
        
        # Incomplete Properties (partial polygons)
        incomplete_properties = polygons.filter(status='partial').count()
        
        # Submitted Properties (assessed polygons - not unassessed)
        submitted_properties = polygons.filter(~Q(status='unassessed')).count()
        
        # BOP Collected (businesses with BOP entries)
        bop_collected = BOPEntry.objects.filter(
            session__in=sessions,
            deleted_at__isnull=True
        ).values('session').distinct().count()
        
        # Owners Collected (unique property owners from sessions)
        owners_collected = PREntry.objects.filter(
            session__in=sessions,
            deleted_at__isnull=True,
            data__has_key='owner_name'
        ).values('data__owner_name').distinct().count()
        
        # Pace calculations (last 4 weeks)
        pace_properties = polygons.filter(
            updated_at__date__gte=pace_start,
            status='complete'
        ).count() / 28 if polygons.filter(updated_at__date__gte=pace_start).exists() else 0
        
        pace_bop = BOPEntry.objects.filter(
            session__submitted_at__date__gte=pace_start,
            deleted_at__isnull=True
        ).values('session').distinct().count() / 28
        
        pace_owners = PREntry.objects.filter(
            session__submitted_at__date__gte=pace_start,
            deleted_at__isnull=True
        ).values('data__owner_name').distinct().count() / 28
        
        # Completion rate
        total_polygons = polygons.count()
        if total_polygons > 0:
            completion_rate = round((submitted_properties / total_polygons) * 100, 1)
        else:
            completion_rate = 0
        
        stats = {
            'total_passes': total_passes,
            'passed_properties': passed_properties,
            'incomplete_properties': incomplete_properties,
            'submitted_properties': submitted_properties,
            'bop_collected': bop_collected,
            'owners_collected': owners_collected,
            'pace': {
                'properties_per_day': round(pace_properties, 1),
                'bop_per_day': round(pace_bop, 1),
                'owners_per_day': round(pace_owners, 1)
            },
            'completion_rate': completion_rate
        }
        
        return JsonResponse({'success': True, 'stats': stats})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
@login_required
def field_dashboard_collection_trend(request):
    """Get daily collection trend data"""
    try:
        user_id = request.GET.get('user_id', 'all')
        days = int(request.GET.get('days', 30))
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        trend_data = []
        current_date = start_date
        
        # Base querysets
        sessions = Session.objects.filter(deleted_at__isnull=True)
        polygons = Polygon.objects.all()
        
        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)
            polygons = polygons.filter(assigned_to_user_id=user_id)
        
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            # Passes (sessions submitted on this date)
            passes_count = sessions.filter(
                submitted_at__date=current_date
            ).count()
            
            # Properties (polygons completed on this date)
            properties_count = polygons.filter(
                updated_at__date=current_date,
                status='complete'
            ).count()
            
            # BOP (business entries on this date)
            bop_count = BOPEntry.objects.filter(
                session__in=sessions,
                session__submitted_at__date=current_date,
                deleted_at__isnull=True
            ).values('session').distinct().count()
            
            trend_data.append({
                'date': current_date.strftime('%b %d'),
                'passes': passes_count,
                'properties': properties_count,
                'bop': bop_count
            })
            
            current_date = next_date
        
        return JsonResponse({
            'success': True,
            'trend_data': trend_data
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
@login_required
def field_dashboard_activities(request):
    """Get recent field activities"""
    try:
        user_id = request.GET.get('user_id', 'all')
        limit = int(request.GET.get('limit', 50))
        
        activities = []
        
        # Base queryset for sessions
        sessions = Session.objects.filter(deleted_at__isnull=True).select_related('collector', 'polygon')
        
        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)
        
        # Get recent sessions
        for session in sessions.order_by('-submitted_at')[:limit]:
            collector_name = session.collector.name if session.collector else 'Unknown'
            property_id = session.polygon.g_code or session.polygon.property if session.polygon else 'Unknown'
            
            # Determine type and status
            entry_type = 'Submit'
            if session.pr_entries.exists() or session.bop_entries.exists():
                if session.status == 'pending':
                    entry_type = 'Submit'
                elif session.status == 'approved':
                    entry_type = 'Submit'
                else:
                    entry_type = 'Submit'
            
            status_display = 'Not Approved' if session.status == 'pending' else 'Approved' if session.status == 'approved' else 'Rejected'
            
            activities.append({
                'collector': collector_name,
                'property': property_id,
                'type': entry_type,
                'status': session.status,
                'status_display': status_display,
                'time': session.submitted_at.isoformat() if session.submitted_at else None
            })
        
        return JsonResponse({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
@login_required
def field_dashboard_snapshots(request):
    """Get end of month snapshots and projections"""
    try:
        # Get pace from last 4 weeks
        pace_start = timezone.now().date() - timedelta(days=28)
        
        # Calculate current pace
        current_properties = Polygon.objects.filter(
            updated_at__date__gte=pace_start,
            status='complete'
        ).count()
        
        current_bop = BOPEntry.objects.filter(
            session__submitted_at__date__gte=pace_start,
            deleted_at__isnull=True
        ).values('session').distinct().count()
        
        current_owners = PREntry.objects.filter(
            session__submitted_at__date__gte=pace_start,
            deleted_at__isnull=True
        ).values('data__owner_name').distinct().count()
        
        # Calculate daily rates
        days_in_pace = 28
        properties_per_day = current_properties / days_in_pace
        bop_per_day = current_bop / days_in_pace
        owners_per_day = current_owners / days_in_pace
        
        # Get current totals
        current_properties_total = Polygon.objects.filter(~Q(status='unassessed')).count()
        current_bop_total = BOPEntry.objects.filter(
            deleted_at__isnull=True
        ).values('session').distinct().count()
        current_owners_total = PREntry.objects.filter(
            deleted_at__isnull=True
        ).values('data__owner_name').distinct().count()
        
        # Project for next months
        projections = []
        snapshots = []
        
        months = ['Mar 2026', 'Apr 2026', 'May 2026', 'Jun 2026']
        
        for i, month in enumerate(months):
            days_projection = 30 * (i + 1)  # Days from now
            
            projected_properties = current_properties_total + (properties_per_day * days_projection)
            projected_bop = current_bop_total + (bop_per_day * days_projection)
            projected_owners = current_owners_total + (owners_per_day * days_projection)
            
            projections.append({
                'month': month,
                'properties': round(projected_properties),
                'bop': round(projected_bop),
                'owners': round(projected_owners)
            })
            
            # Also create snapshots (actual historical data would be here)
            snapshots.append({
                'month': month,
                'properties': round(projected_properties * 0.8),  # Placeholder for actual data
                'bop': round(projected_bop * 0.85),
                'owners': round(projected_owners * 0.9)
            })
        
        return JsonResponse({
            'success': True,
            'projections': projections,
            'snapshots': snapshots,
            'current_pace': {
                'properties_per_day': round(properties_per_day, 1),
                'bop_per_day': round(bop_per_day, 1),
                'owners_per_day': round(owners_per_day, 1)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)