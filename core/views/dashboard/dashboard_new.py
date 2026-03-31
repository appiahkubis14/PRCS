# # core/views/dashboard_views.py

# from django.shortcuts import render
# from django.http import JsonResponse
# from django.db.models import Count, Q, F, Sum, Avg
# from django.utils import timezone
# from datetime import timedelta, datetime
# from django.contrib.auth.decorators import login_required
# from django.views.decorators.http import require_GET
# from django.contrib.auth import get_user_model
# import json

# from core.models import (
#     Business, Bill, Session, Polygon, UserModel, 
#     PropertyRate, BOPEntry, PREntry
# )

# User = get_user_model()


# @login_required
# def field_collection_dashboard(request):
#     """Render the field collection dashboard"""
#     # Get all field collectors
#     field_collectors = UserModel.objects.filter(
#         role='collector',
#         is_active=True
#     ).order_by('name')
    
#     return render(request, 'core/main/dashboard/dashboard.html', {
#         'field_collectors': field_collectors
#     })


# @require_GET
# @login_required
# def field_dashboard_stats(request):
#     """Get field collection statistics"""
#     try:
#         user_id = request.GET.get('user_id', 'all')
#         days = int(request.GET.get('days', 30))
        
#         # Base querysets
#         sessions = Session.objects.filter(deleted_at__isnull=True)
#         polygons = Polygon.objects.all()
#         businesses = Business.objects.filter(is_deleted=False)
        
#         # Filter by user if specified
#         if user_id != 'all':
#             sessions = sessions.filter(collector_id=user_id)
#             polygons = polygons.filter(assigned_to_user_id=user_id)
        
#         # Calculate dates
#         end_date = timezone.now().date()
#         start_date = end_date - timedelta(days=days)
#         pace_start = end_date - timedelta(days=28)
        
#         # Total Passes (total sessions submitted)
#         total_passes = sessions.count()
        
#         # Passed Properties (complete polygons)
#         passed_properties = polygons.filter(status='complete').count()
        
#         # Incomplete Properties (partial polygons)
#         incomplete_properties = polygons.filter(status='partial').count()
        
#         # Submitted Properties (assessed polygons - not unassessed)
#         submitted_properties = polygons.filter(~Q(status='unassessed')).count()
        
#         # BOP Collected (businesses with BOP entries)
#         bop_collected = BOPEntry.objects.filter(
#             session__in=sessions,
#             deleted_at__isnull=True
#         ).values('session').distinct().count()
        
#         # Owners Collected (unique property owners from sessions)
#         owners_collected = PREntry.objects.filter(
#             session__in=sessions,
#             deleted_at__isnull=True,
#             data__has_key='owner_name'
#         ).values('data__owner_name').distinct().count()
        
#         # Pace calculations (last 4 weeks)
#         pace_properties = polygons.filter(
#             updated_at__date__gte=pace_start,
#             status='complete'
#         ).count() / 28 if polygons.filter(updated_at__date__gte=pace_start).exists() else 0
        
#         pace_bop = BOPEntry.objects.filter(
#             session__submitted_at__date__gte=pace_start,
#             deleted_at__isnull=True
#         ).values('session').distinct().count() / 28
        
#         pace_owners = PREntry.objects.filter(
#             session__submitted_at__date__gte=pace_start,
#             deleted_at__isnull=True
#         ).values('data__owner_name').distinct().count() / 28
        
#         # Completion rate
#         total_polygons = polygons.count()
#         if total_polygons > 0:
#             completion_rate = round((submitted_properties / total_polygons) * 100, 1)
#         else:
#             completion_rate = 0
        
#         stats = {
#             'total_passes': total_passes,
#             'passed_properties': passed_properties,
#             'incomplete_properties': incomplete_properties,
#             'submitted_properties': submitted_properties,
#             'bop_collected': bop_collected,
#             'owners_collected': owners_collected,
#             'pace': {
#                 'properties_per_day': round(pace_properties, 1),
#                 'bop_per_day': round(pace_bop, 1),
#                 'owners_per_day': round(pace_owners, 1)
#             },
#             'completion_rate': completion_rate
#         }
        
#         return JsonResponse({'success': True, 'stats': stats})
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @require_GET
# @login_required
# def field_dashboard_collection_trend(request):
#     """Get daily collection trend data"""
#     try:
#         user_id = request.GET.get('user_id', 'all')
#         days = int(request.GET.get('days', 30))
        
#         end_date = timezone.now().date()
#         start_date = end_date - timedelta(days=days)
        
#         trend_data = []
#         current_date = start_date
        
#         # Base querysets
#         sessions = Session.objects.filter(deleted_at__isnull=True)
#         polygons = Polygon.objects.all()
        
#         if user_id != 'all':
#             sessions = sessions.filter(collector_id=user_id)
#             polygons = polygons.filter(assigned_to_user_id=user_id)
        
#         while current_date <= end_date:
#             next_date = current_date + timedelta(days=1)
            
#             # Passes (sessions submitted on this date)
#             passes_count = sessions.filter(
#                 submitted_at__date=current_date
#             ).count()
            
#             # Properties (polygons completed on this date)
#             properties_count = polygons.filter(
#                 updated_at__date=current_date,
#                 status='complete'
#             ).count()
            
#             # BOP (business entries on this date)
#             bop_count = BOPEntry.objects.filter(
#                 session__in=sessions,
#                 session__submitted_at__date=current_date,
#                 deleted_at__isnull=True
#             ).values('session').distinct().count()
            
#             trend_data.append({
#                 'date': current_date.strftime('%b %d'),
#                 'passes': passes_count,
#                 'properties': properties_count,
#                 'bop': bop_count
#             })
            
#             current_date = next_date
        
#         return JsonResponse({
#             'success': True,
#             'trend_data': trend_data
#         })
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @require_GET
# @login_required
# def field_dashboard_activities(request):
#     """Get recent field activities"""
#     try:
#         user_id = request.GET.get('user_id', 'all')
#         limit = int(request.GET.get('limit', 50))
        
#         activities = []
        
#         # Base queryset for sessions
#         sessions = Session.objects.filter(deleted_at__isnull=True).select_related('collector', 'polygon')
        
#         if user_id != 'all':
#             sessions = sessions.filter(collector_id=user_id)
        
#         # Get recent sessions
#         for session in sessions.order_by('-submitted_at')[:limit]:
#             collector_name = session.collector.name if session.collector else 'Unknown'
#             property_id = session.polygon.g_code or session.polygon.property if session.polygon else 'Unknown'
            
#             # Determine type and status
#             entry_type = 'Submit'
#             if session.pr_entries.exists() or session.bop_entries.exists():
#                 if session.status == 'pending':
#                     entry_type = 'Submit'
#                 elif session.status == 'approved':
#                     entry_type = 'Submit'
#                 else:
#                     entry_type = 'Submit'
            
#             status_display = 'Not Approved' if session.status == 'pending' else 'Approved' if session.status == 'approved' else 'Rejected'
            
#             activities.append({
#                 'collector': collector_name,
#                 'property': property_id,
#                 'type': entry_type,
#                 'status': session.status,
#                 'status_display': status_display,
#                 'time': session.submitted_at.isoformat() if session.submitted_at else None
#             })
        
#         return JsonResponse({
#             'success': True,
#             'activities': activities
#         })
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({'success': False, 'error': str(e)}, status=500)


# @require_GET
# @login_required
# def field_dashboard_snapshots(request):
#     """Get end of month snapshots and projections"""
#     try:
#         # Get pace from last 4 weeks
#         pace_start = timezone.now().date() - timedelta(days=28)
        
#         # Calculate current pace
#         current_properties = Polygon.objects.filter(
#             updated_at__date__gte=pace_start,
#             status='complete'
#         ).count()
        
#         current_bop = BOPEntry.objects.filter(
#             session__submitted_at__date__gte=pace_start,
#             deleted_at__isnull=True
#         ).values('session').distinct().count()
        
#         current_owners = PREntry.objects.filter(
#             session__submitted_at__date__gte=pace_start,
#             deleted_at__isnull=True
#         ).values('data__owner_name').distinct().count()
        
#         # Calculate daily rates
#         days_in_pace = 28
#         properties_per_day = current_properties / days_in_pace
#         bop_per_day = current_bop / days_in_pace
#         owners_per_day = current_owners / days_in_pace
        
#         # Get current totals
#         current_properties_total = Polygon.objects.filter(~Q(status='unassessed')).count()
#         current_bop_total = BOPEntry.objects.filter(
#             deleted_at__isnull=True
#         ).values('session').distinct().count()
#         current_owners_total = PREntry.objects.filter(
#             deleted_at__isnull=True
#         ).values('data__owner_name').distinct().count()
        
#         # Project for next months
#         projections = []
#         snapshots = []
        
#         months = ['Mar 2026', 'Apr 2026', 'May 2026', 'Jun 2026']
        
#         for i, month in enumerate(months):
#             days_projection = 30 * (i + 1)  # Days from now
            
#             projected_properties = current_properties_total + (properties_per_day * days_projection)
#             projected_bop = current_bop_total + (bop_per_day * days_projection)
#             projected_owners = current_owners_total + (owners_per_day * days_projection)
            
#             projections.append({
#                 'month': month,
#                 'properties': round(projected_properties),
#                 'bop': round(projected_bop),
#                 'owners': round(projected_owners)
#             })
            
#             # Also create snapshots (actual historical data would be here)
#             snapshots.append({
#                 'month': month,
#                 'properties': round(projected_properties * 0.8),  # Placeholder for actual data
#                 'bop': round(projected_bop * 0.85),
#                 'owners': round(projected_owners * 0.9)
#             })
        
#         return JsonResponse({
#             'success': True,
#             'projections': projections,
#             'snapshots': snapshots,
#             'current_pace': {
#                 'properties_per_day': round(properties_per_day, 1),
#                 'bop_per_day': round(bop_per_day, 1),
#                 'owners_per_day': round(owners_per_day, 1)
#             }
#         })
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return JsonResponse({'success': False, 'error': str(e)}, status=500)











# core/views/dashboard_views.py

from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q, F, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model
import calendar

from core.models import (
    Business, Bill, Session, Polygon, UserModel,
    PropertyRate, BOPEntry, PREntry
)

User = get_user_model()


@login_required
def field_collection_dashboard(request):
    """Render the field collection dashboard"""
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

        # Filter by user if specified
        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)
            polygons = polygons.filter(assigned_to_user_id=user_id)

        # Pace window: last 28 days from today
        today = timezone.now().date()
        pace_start = today - timedelta(days=28)

        # ── Headline stats ──────────────────────────────────────────────────

        # Total Passes: all (filtered) sessions
        total_passes = sessions.count()

        # Passed Properties: polygons with status 'complete'
        passed_properties = polygons.filter(status='complete').count()

        # Incomplete Properties: polygons with status 'partial'
        incomplete_properties = polygons.filter(status='partial').count()

        # Submitted Properties: any polygon that has been assessed (not unassessed)
        submitted_properties = polygons.exclude(status='unassessed').count()

        # BOP Collected: distinct sessions that have at least one BOP entry
        bop_collected = (
            BOPEntry.objects
            .filter(session__in=sessions, deleted_at__isnull=True)
            .values('session')
            .distinct()
            .count()
        )

        # Owners Collected: distinct owner names from PR entries
        owners_collected = (
            PREntry.objects
            .filter(session__in=sessions, deleted_at__isnull=True, data__has_key='owner_name')
            .values('data__owner_name')
            .distinct()
            .count()
        )

        # ── Pace (last 28 days) ─────────────────────────────────────────────

        pace_sessions = sessions.filter(submitted_at__date__gte=pace_start)

        pace_properties_count = polygons.filter(
            updated_at__date__gte=pace_start,
            status='complete'
        ).count()

        pace_bop_count = (
            BOPEntry.objects
            .filter(session__in=pace_sessions, deleted_at__isnull=True)
            .values('session')
            .distinct()
            .count()
        )

        pace_owners_count = (
            PREntry.objects
            .filter(session__in=pace_sessions, deleted_at__isnull=True, data__has_key='owner_name')
            .values('data__owner_name')
            .distinct()
            .count()
        )

        # How many actual days have passed since pace_start (never divide by zero)
        pace_days = max((today - pace_start).days, 1)

        pace = {
            'properties_per_day': round(pace_properties_count / pace_days, 1),
            'bop_per_day': round(pace_bop_count / pace_days, 1),
            'owners_per_day': round(pace_owners_count / pace_days, 1),
        }

        # ── Completion rate ─────────────────────────────────────────────────

        total_polygons = polygons.count()
        completion_rate = (
            round((submitted_properties / total_polygons) * 100, 1)
            if total_polygons > 0 else 0
        )

        stats = {
            'total_passes': total_passes,
            'passed_properties': passed_properties,
            'incomplete_properties': incomplete_properties,
            'submitted_properties': submitted_properties,
            'bop_collected': bop_collected,
            'owners_collected': owners_collected,
            'pace': pace,
            'completion_rate': completion_rate,
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

        today = timezone.now().date()
        start_date = today - timedelta(days=days)

        # Base querysets
        sessions = Session.objects.filter(deleted_at__isnull=True)
        polygons = Polygon.objects.all()

        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)
            polygons = polygons.filter(assigned_to_user_id=user_id)

        trend_data = []
        current_date = start_date

        while current_date <= today:
            passes_count = sessions.filter(submitted_at__date=current_date).count()

            properties_count = polygons.filter(
                updated_at__date=current_date,
                status='complete'
            ).count()

            bop_count = (
                BOPEntry.objects
                .filter(
                    session__in=sessions,
                    session__submitted_at__date=current_date,
                    deleted_at__isnull=True,
                )
                .values('session')
                .distinct()
                .count()
            )

            trend_data.append({
                'date': current_date.strftime('%b %d'),
                'passes': passes_count,
                'properties': properties_count,
                'bop': bop_count,
            })

            current_date += timedelta(days=1)

        return JsonResponse({'success': True, 'trend_data': trend_data})

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

        sessions = (
            Session.objects
            .filter(deleted_at__isnull=True)
            .select_related('collector', 'polygon')
        )

        if user_id != 'all':
            sessions = sessions.filter(collector_id=user_id)

        activities = []
        for session in sessions.order_by('-submitted_at')[:limit]:
            collector_name = session.collector.name if session.collector else 'Unknown'
            polygon = session.polygon
            property_id = (
                (polygon.g_code or polygon.property)
                if polygon else 'Unknown'
            )

            status = session.status or 'pending'
            status_display = {
                'pending': 'Not Approved',
                'approved': 'Approved',
                'rejected': 'Rejected',
            }.get(status, status.capitalize())

            activities.append({
                'collector': collector_name,
                'property': property_id,
                'type': 'Submit',
                'status': status,
                'status_display': status_display,
                'time': session.submitted_at.isoformat() if session.submitted_at else None,
            })

        return JsonResponse({'success': True, 'activities': activities})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
@login_required
def field_dashboard_snapshots(request):
    """
    Returns:
      - projections: cumulative totals projected to the last day of each of
                     the next 4 calendar months, based on the 28-day pace.
      - snapshots:   actual end-of-month totals recorded up to today for the
                     last 4 completed calendar months.
      - current_pace: daily rates used for the projections.
    """
    try:
        today = timezone.now().date()
        pace_start = today - timedelta(days=28)
        pace_days = max((today - pace_start).days, 1)

        # ── Current totals (all time) ───────────────────────────────────────
        current_properties_total = Polygon.objects.exclude(status='unassessed').count()
        current_bop_total = (
            BOPEntry.objects
            .filter(deleted_at__isnull=True)
            .values('session')
            .distinct()
            .count()
        )
        current_owners_total = (
            PREntry.objects
            .filter(deleted_at__isnull=True, data__has_key='owner_name')
            .values('data__owner_name')
            .distinct()
            .count()
        )

        # ── 28-day pace ─────────────────────────────────────────────────────
        pace_properties = Polygon.objects.filter(
            updated_at__date__gte=pace_start,
            status='complete'
        ).count()

        pace_bop = (
            BOPEntry.objects
            .filter(session__submitted_at__date__gte=pace_start, deleted_at__isnull=True)
            .values('session')
            .distinct()
            .count()
        )

        pace_owners = (
            PREntry.objects
            .filter(session__submitted_at__date__gte=pace_start, deleted_at__isnull=True, data__has_key='owner_name')
            .values('data__owner_name')
            .distinct()
            .count()
        )

        properties_per_day = pace_properties / pace_days
        bop_per_day = pace_bop / pace_days
        owners_per_day = pace_owners / pace_days

        # ── Projections: next 4 calendar months ─────────────────────────────
        projections = []
        year, month = today.year, today.month

        for _ in range(4):
            month += 1
            if month > 12:
                month = 1
                year += 1

            last_day_of_month = calendar.monthrange(year, month)[1]
            end_of_month = timezone.datetime(year, month, last_day_of_month).date()
            days_from_today = max((end_of_month - today).days, 0)

            projections.append({
                'month': end_of_month.strftime('%b %Y'),
                'properties': round(current_properties_total + properties_per_day * days_from_today),
                'bop': round(current_bop_total + bop_per_day * days_from_today),
                'owners': round(current_owners_total + owners_per_day * days_from_today),
            })

        # ── Snapshots: last 4 completed calendar months ─────────────────────
        # We use the count of records that existed up to the last day of each month
        # by filtering on updated_at / submitted_at <= end of that month.
        snapshots = []
        snap_year, snap_month = today.year, today.month

        for _ in range(4):
            snap_month -= 1
            if snap_month < 1:
                snap_month = 12
                snap_year -= 1

            last_day = calendar.monthrange(snap_year, snap_month)[1]
            month_end = timezone.datetime(snap_year, snap_month, last_day, 23, 59, 59,
                                          tzinfo=timezone.get_current_timezone())

            snap_properties = Polygon.objects.filter(
                updated_at__lte=month_end
            ).exclude(status='unassessed').count()

            snap_bop = (
                BOPEntry.objects
                .filter(deleted_at__isnull=True, session__submitted_at__lte=month_end)
                .values('session')
                .distinct()
                .count()
            )

            snap_owners = (
                PREntry.objects
                .filter(deleted_at__isnull=True, data__has_key='owner_name',
                        session__submitted_at__lte=month_end)
                .values('data__owner_name')
                .distinct()
                .count()
            )

            snapshots.append({
                'month': month_end.strftime('%b %Y'),
                'properties': snap_properties,
                'bop': snap_bop,
                'owners': snap_owners,
            })

        # Reverse so they appear chronologically (oldest → newest)
        snapshots.reverse()

        return JsonResponse({
            'success': True,
            'projections': projections,
            'snapshots': snapshots,
            'current_pace': {
                'properties_per_day': round(properties_per_day, 1),
                'bop_per_day': round(bop_per_day, 1),
                'owners_per_day': round(owners_per_day, 1),
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)