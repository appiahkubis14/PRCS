# views/dashboard_views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q, F, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
import json
from collections import defaultdict

from core.models import Bops, BopsBills, District, PaymentTransaction
from django.contrib.gis.db.models import GeometryField

@login_required
def revenue_dashboard(request):
    """Render the main dashboard view"""
    return render(request, 'core/main/dashboard/dashboard.html')

@require_GET
@login_required
def dashboard_performance_stats(request):
    """Get performance statistics for dashboard (no amounts)"""
    try:
        # Get date ranges
        today = timezone.now().date()
        first_day_month = today.replace(day=1)
        
        # Base querysets
        businesses = Bops.objects.filter(is_deleted=False)
        bills = BopsBills.objects.filter(is_deleted=False)
        
        # Business statistics
        total_businesses = businesses.count()
        new_businesses_month = businesses.filter(
            created_at__date__gte=first_day_month
        ).count()
        
        # Bills statistics
        total_bills = bills.count()
        paid_bills = bills.filter(status='paid').count()
        pending_bills = bills.filter(status__in=['generated', 'sent']).count()
        overdue_bills = bills.filter(
            status='overdue',
            due_date__lt=today
        ).count()
        
        # Payment statistics
        payments = PaymentTransaction.objects.filter(
            status='completed',
            business_bill__isnull=False
        )
        
        total_payments = payments.count()
        successful_payments = payments.filter(status='completed').count()
        
        # Average payment time (days from bill generation to payment)
        paid_bills_with_dates = bills.filter(
            status='paid',
            paid_date__isnull=False,
            generated_date__isnull=False
        )
        
        if paid_bills_with_dates.exists():
            total_days = sum(
                (bill.paid_date.date() - bill.generated_date.date()).days 
                for bill in paid_bills_with_dates
                if bill.paid_date
            )
            avg_payment_days = round(total_days / paid_bills_with_dates.count(), 1)
        else:
            avg_payment_days = 0
        
        # Bill status breakdown for pie chart
        bill_status = []
        status_counts = bills.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        status_colors = {
            'draft': '#858796',
            'generated': '#36b9cc',
            'sent': '#f6c23e',
            'paid': '#1cc88a',
            'overdue': '#e74a3b',
            'cancelled': '#858796'
        }
        
        for item in status_counts:
            status = item['status'] or 'unknown'
            bill_status.append({
                'status': status,
                'count': item['count'],
                'color': status_colors.get(status, '#858796')
            })
        
        stats = {
            'total_businesses': total_businesses,
            'new_businesses_month': new_businesses_month,
            'active_businesses': businesses.filter(
                bills__status='paid'
            ).distinct().count(),
            'total_bills': total_bills,
            'paid_bills': paid_bills,
            'pending_bills': pending_bills,
            'overdue_bills': overdue_bills,
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'avg_payment_days': avg_payment_days,
            'bill_status': bill_status
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_growth_trend(request):
    """Get business growth and payment trend data"""
    try:
        days = int(request.GET.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Initialize data structure
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        growth_data = []
        
        for date in date_range:
            next_date = date + timedelta(days=1)
            
            # New businesses on this date
            new_businesses = Bops.objects.filter(
                created_at__date=date,
                is_deleted=False
            ).count()
            
            # Payments on this date
            payments = PaymentTransaction.objects.filter(
                status='completed',
                completed_at__date=date,
                business_bill__isnull=False
            ).count()
            
            growth_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'new_businesses': new_businesses,
                'payments': payments
            })
        
        return JsonResponse({
            'success': True,
            'growth_data': growth_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_category_distribution(request):
    """Get business distribution by category"""
    try:
        # Get business categories with counts
        categories = Bops.objects.filter(
            is_deleted=False,
            business_category__isnull=False
        ).exclude(
            business_category=''
        ).values('business_category').annotate(
            count=Count('id')
        ).order_by('-count')[:10]  # Top 10 categories
        
        category_data = []
        for item in categories:
            category_name = item['business_category']
            if len(category_name) > 20:  # Truncate long names
                category_name = category_name[:18] + '...'
            
            category_data.append({
                'name': category_name,
                'count': item['count'],
                'original_name': item['business_category']
            })
        
        return JsonResponse({
            'success': True,
            'categories': category_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_district_performance(request):
    """Get district-wise business and payment performance"""
    try:
        # Get all districts with business counts
        districts_data = []
        
        # Use distinct districts from Bops model
        districts = Bops.objects.filter(
            is_deleted=False,
            division__isnull=False
        ).exclude(
            division=''
        ).values('division').annotate(
            business_count=Count('id')
        ).order_by('-business_count')[:10]
        
        for district in districts:
            district_name = district['division']
            business_count = district['business_count']
            
            # Get bills for businesses in this district
            businesses_in_district = Bops.objects.filter(
                division=district_name,
                is_deleted=False
            ).values_list('id', flat=True)
            
            bills = BopsBills.objects.filter(
                business_id__in=list(businesses_in_district),
                is_deleted=False
            )
            
            total_bills = bills.count()
            paid_bills = bills.filter(status='paid').count()
            
            # Calculate collection rate
            if total_bills > 0:
                collection_rate = round((paid_bills / total_bills) * 100)
            else:
                collection_rate = 0
            
            districts_data.append({
                'district': district_name,
                'business_count': business_count,
                'total_bills': total_bills,
                'paid_bills': paid_bills,
                'collection_rate': collection_rate
            })
        
        return JsonResponse({
            'success': True,
            'districts': districts_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_recent_activity(request):
    """Get recent activities (payments and new registrations)"""
    try:
        activities = []
        
        # Recent payments (last 10)
        recent_payments = PaymentTransaction.objects.filter(
            status='completed',
            business_bill__isnull=False
        ).select_related('business_bill__business').order_by('-completed_at')[:5]
        
        for payment in recent_payments:
            if payment.business_bill and payment.business_bill.business:
                activities.append({
                    'type': 'payment',
                    'description': f"Payment received from {payment.business_bill.business.business_name}",
                    'details': f"Bill #{payment.business_bill.bill_number}",
                    'time': payment.completed_at.strftime('%Y-%m-%d %H:%M') if payment.completed_at else 'N/A'
                })
        
        # Recent business registrations
        recent_businesses = Bops.objects.filter(
            is_deleted=False
        ).order_by('-created_at')[:5]
        
        for business in recent_businesses:
            activities.append({
                'type': 'registration',
                'description': f"New business registered: {business.business_name}",
                'details': f"Account: {business.account_number}",
                'time': business.created_at.strftime('%Y-%m-%d %H:%M') if business.created_at else 'N/A'
            })
        
        # Recent bill generations
        recent_bills = BopsBills.objects.filter(
            is_deleted=False
        ).select_related('business').order_by('-generated_date')[:5]
        
        for bill in recent_bills:
            if bill.business:
                activities.append({
                    'type': 'bill',
                    'description': f"Bill generated for {bill.business.business_name}",
                    'details': f"Year: {bill.billing_year}",
                    'time': bill.generated_date.strftime('%Y-%m-%d %H:%M') if bill.generated_date else 'N/A'
                })
        
        # Sort by time (most recent first) and limit to 10
        activities.sort(key=lambda x: x['time'], reverse=True)
        activities = activities[:10]
        
        return JsonResponse({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_payment_patterns(request):
    """Get payment patterns for heatmap and insights"""
    try:
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        # Get payments in last 30 days
        payments = PaymentTransaction.objects.filter(
            status='completed',
            completed_at__date__gte=thirty_days_ago,
            completed_at__date__lte=today,
            business_bill__isnull=False
        )
        
        # Group by day of week for heatmap
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        heatmap_data = []
        
        for i, day_name in enumerate(day_names):
            day_count = payments.filter(
                completed_at__week_day=i+2  # Django week_day: 1=Sunday, 2=Monday, etc.
            ).count()
            
            heatmap_data.append({
                'day': day_name,
                'count': day_count
            })
        
        # Find peak day
        peak_day = max(heatmap_data, key=lambda x: x['count'])
        
        # Get top business category
        top_category = Bops.objects.filter(
            is_deleted=False,
            business_category__isnull=False
        ).exclude(
            business_category=''
        ).values('business_category').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        # Calculate average payment time
        paid_bills = BopsBills.objects.filter(
            status='paid',
            paid_date__isnull=False,
            generated_date__isnull=False
        )
        
        if paid_bills.exists():
            total_days = 0
            count = 0
            for bill in paid_bills:
                if bill.paid_date and bill.generated_date:
                    days_diff = (bill.paid_date.date() - bill.generated_date.date()).days
                    if days_diff >= 0:
                        total_days += days_diff
                        count += 1
            
            avg_payment_days = round(total_days / count, 1) if count > 0 else 0
        else:
            avg_payment_days = 0
        
        # Calculate compliance rate (bills paid on time vs total bills)
        total_bills = BopsBills.objects.filter(is_deleted=False).count()
        on_time_payments = BopsBills.objects.filter(
            status='paid',
            paid_date__lte=F('due_date')
        ).count()
        
        compliance_rate = round((on_time_payments / total_bills * 100), 1) if total_bills > 0 else 0
        
        insights = {
            'peak_day': peak_day['day'] if peak_day else 'N/A',
            'peak_day_value': f"{peak_day['count']} payments" if peak_day else '0 payments',
            'top_category': top_category['business_category'][:20] + '...' if top_category and len(top_category['business_category']) > 20 else (top_category['business_category'] if top_category else 'N/A'),
            'top_category_value': f"{top_category['count']} businesses" if top_category else '0 businesses',
            'avg_payment_days': avg_payment_days,
            'compliance_rate': compliance_rate
        }
        
        return JsonResponse({
            'success': True,
            'heatmap': heatmap_data,
            'insights': insights
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_quick_stats(request):
    """Get quick statistics for dashboard widgets"""
    try:
        # Total businesses
        total_businesses = Bops.objects.filter(is_deleted=False).count()
        
        # Businesses with bills this year
        current_year = timezone.now().year
        businesses_with_bills = Bops.objects.filter(
            bills__billing_year=current_year,
            is_deleted=False
        ).distinct().count()
        
        # Payment success rate
        total_payments = PaymentTransaction.objects.filter(
            business_bill__isnull=False
        ).count()
        
        successful_payments = PaymentTransaction.objects.filter(
            status='completed',
            business_bill__isnull=False
        ).count()
        
        payment_rate = round((successful_payments / total_payments * 100), 1) if total_payments > 0 else 0
        
        # Overdue rate
        overdue_bills = BopsBills.objects.filter(
            status='overdue',
            is_deleted=False
        ).count()
        
        total_bills = BopsBills.objects.filter(is_deleted=False).count()
        overdue_rate = round((overdue_bills / total_bills * 100), 1) if total_bills > 0 else 0
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_businesses': total_businesses,
                'businesses_with_bills': businesses_with_bills,
                'coverage_rate': round((businesses_with_bills / total_businesses * 100), 1) if total_businesses > 0 else 0,
                'payment_success_rate': payment_rate,
                'overdue_rate': overdue_rate
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def dashboard_export_data(request):
    """Export dashboard data as JSON"""
    try:
        # Gather all dashboard data for export
        data = {
            'export_date': timezone.now().isoformat(),
            'businesses': list(Bops.objects.filter(is_deleted=False).values(
                'id', 'business_name', 'account_number', 'business_category', 
                'division', 'created_at'
            )),
            'bills': list(BopsBills.objects.filter(is_deleted=False).values(
                'id', 'bill_number', 'billing_year', 'status',
                'generated_date', 'due_date', 'paid_date'
            )),
            'payments': list(PaymentTransaction.objects.filter(
                status='completed'
            ).values(
                'id', 'transaction_id', 'amount', 'completed_at',
                'payment_method'
            )[:1000])  # Limit to last 1000 payments for performance
        }
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    







####################################################################################################################


# views/field_dashboard_views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model
from collections import defaultdict
import calendar

from core.models import Property, Bops, BopsBills, PropertyOwner, User

User = get_user_model()

@login_required
def field_collection_dashboard(request):
    """Render the field collection dashboard"""
    # Get all field collectors (users with roles in UserProfile if available)
    try:
        from core.models import UserProfile
        field_collectors = User.objects.filter(
            userprofile__role__name__in=['assessment_team', 'field_collector'],
            is_active=True
        ).distinct()
    except:
        # Fallback if UserProfile not available
        field_collectors = User.objects.filter(is_active=True)[:10]
    
    return render(request, 'dashboard/field_collection_dashboard.html', {
        'field_collectors': field_collectors
    })
# views/field_dashboard_views.py

@require_GET
@login_required
def field_dashboard_stats(request):
    """Get field collection statistics"""
    try:
        user_id = request.GET.get('user_id', 'all')
        days = int(request.GET.get('days', 30))
        
        # Base querysets
        properties = Property.objects.filter(is_deleted=False)
        bops = Bops.objects.filter(is_deleted=False)
        owners = PropertyOwner.objects.filter(is_deleted=False)
        
        # Filter by user if specified
        if user_id != 'all':
            properties = properties.filter(added_by_id=user_id)
            bops = bops.filter(added_by_id=user_id)
            owners = owners.filter(added_by_id=user_id)
        
        # Calculate statistics
        stats = {
            'total_properties': properties.count(),
            'submitted_properties': properties.filter(
                created_at__isnull=False
            ).count(),
            
            'total_bops': bops.count(),
            'bops_with_bills': BopsBills.objects.filter(
                business__in=bops,
                is_deleted=False
            ).values('business').distinct().count(),
            
            'total_passes': 0,  # You'll need to track passes in your model
            'passed_properties': 0,
            'incomplete_passes': 0,
            
            'total_owners': owners.count(),
            'unique_owners': owners.values('owner_name').distinct().count(),
        }
        
        # Calculate pace data (last 4 weeks)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=28)
        
        properties_last_4w = properties.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()
        
        bops_last_4w = bops.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()
        
        owners_last_4w = owners.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()
        
        pace = {
            'properties_per_day': round(properties_last_4w / 28, 1) if properties_last_4w > 0 else 0,
            'bops_per_day': round(bops_last_4w / 28, 1) if bops_last_4w > 0 else 0,
            'owners_per_day': round(owners_last_4w / 28, 1) if owners_last_4w > 0 else 0
        }
        
        # Calculate projections
        projections = []
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        for i in range(4):
            month = current_month + i
            year = current_year
            if month > 12:
                month -= 12
                year += 1
            
            days_in_month = calendar.monthrange(year, month)[1]
            
            projections.append({
                'month': datetime(year, month, 1).strftime('%b %Y'),
                'properties': int(pace['properties_per_day'] * days_in_month * (i + 1)),
                'bops': int(pace['bops_per_day'] * days_in_month * (i + 1)),
                'owners': int(pace['owners_per_day'] * days_in_month * (i + 1))
            })
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'pace': pace,
            'projections': projections
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

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
        properties = Property.objects.filter(is_deleted=False)
        bops = Bops.objects.filter(is_deleted=False)
        
        if user_id != 'all':
            properties = properties.filter(added_by_id=user_id)
            bops = bops.filter(added_by_id=user_id)
        
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            # Properties created on this date
            properties_count = properties.filter(
                created_at__date=current_date
            ).count()
            
            # BOPs created on this date
            bops_count = bops.filter(
                created_at__date=current_date
            ).count()
            
            # Passes (you'll need to track these in your model)
            passes_count = 0
            
            trend_data.append({
                'date': current_date.strftime('%b %d'),
                'properties': properties_count,
                'bops': bops_count,
                'passes': passes_count
            })
            
            current_date = next_date
        
        return JsonResponse({
            'success': True,
            'trend_data': trend_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def field_dashboard_activities(request):
    """Get recent field activities"""
    try:
        user_id = request.GET.get('user_id', 'all')
        limit = int(request.GET.get('limit', 50))
        
        activities = []
        
        # Property creation activities
        properties = Property.objects.filter(is_deleted=False)
        if user_id != 'all':
            properties = properties.filter(added_by_id=user_id)
        
        for prop in properties.order_by('-created_at')[:20]:
            activities.append({
                'type': 'submit' if prop.id else 'save',
                'collector': prop.added_by.username if prop.added_by else 'Unknown',
                'property_id': prop.id,
                'property_part': prop.property_type.name if hasattr(prop, 'property_type') and prop.property_type else 'Property',
                'status': 'Not Approved',
                'visited_at': prop.created_at.strftime('%Y-%m-%d %H:%M') if prop.created_at else 'N/A'
            })
        
        # BOP creation activities
        bops = Bops.objects.filter(is_deleted=False)
        if user_id != 'all':
            bops = bops.filter(added_by_id=user_id)
        
        for bop in bops.order_by('-created_at')[:20]:
            activities.append({
                'type': 'submit',
                'collector': bop.added_by.username if bop.added_by else 'Unknown',
                'property_id': bop.account_number,
                'property_part': 'Business',
                'status': 'Not Approved',
                'visited_at': bop.created_at.strftime('%Y-%m-%d %H:%M') if bop.created_at else 'N/A'
            })
        
        # Sort by date and limit
        activities.sort(key=lambda x: x['visited_at'], reverse=True)
        activities = activities[:limit]
        
        return JsonResponse({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def field_dashboard_projections(request):
    """Get monthly projections based on current pace"""
    try:
        user_id = request.GET.get('user_id', 'all')
        
        # Calculate current pace from last 4 weeks
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=28)
        
        properties = Property.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        bops = Bops.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        owners = PropertyOwner.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        if user_id != 'all':
            properties = properties.filter(added_by_id=user_id)
            bops = bops.filter(added_by_id=user_id)
            owners = owners.filter(added_by__id=user_id)
        
        properties_per_day = properties.count() / 28
        bops_per_day = bops.count() / 28
        owners_per_day = owners.count() / 28
        
        # Generate monthly projections
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        projections = []
        for i in range(4):
            month = current_month + i
            year = current_year
            if month > 12:
                month -= 12
                year += 1
            
            days_in_month = calendar.monthrange(year, month)[1]
            
            projections.append({
                'month': datetime(year, month, 1).strftime('%b %Y'),
                'properties': int(properties_per_day * days_in_month * (i + 1)),
                'bops': int(bops_per_day * days_in_month * (i + 1)),
                'owners': int(owners_per_day * days_in_month * (i + 1))
            })
        
        return JsonResponse({
            'success': True,
            'projections': projections
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
@login_required
def field_dashboard_snapshots(request):
    """Get end of month snapshots"""
    try:
        snapshots = []
        
        # Get last 6 months
        for i in range(6, 0, -1):
            month = timezone.now().month - i
            year = timezone.now().year
            if month <= 0:
                month += 12
                year -= 1
            
            month_start = datetime(year, month, 1).date()
            if month == 12:
                month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
            # Get counts for this month
            properties_count = Property.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end,
                is_deleted=False
            ).count()
            
            bops_count = Bops.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end,
                is_deleted=False
            ).count()
            
            owners_count = PropertyOwner.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end,
                is_deleted=False
            ).count()
            
            snapshots.append({
                'month': month_start.strftime('%b %Y'),
                'properties': properties_count,
                'bops': bops_count,
                'owners': owners_count,
                'target': 50000  # Set your target here
            })
        
        return JsonResponse({
            'success': True,
            'snapshots': snapshots
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)