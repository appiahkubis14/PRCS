# views.py - Dashboard Views

from django.shortcuts import render
from django.db.models import Count, Sum, Q, Avg, Max, Min
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
from core.models import Bops, BopsBills, PaymentTransaction, PaymentLinkClick
import json

def revenue_dashboard(request):
    """Main revenue collection dashboard"""
    context = {
        'page_title': 'Revenue Collection Dashboard',
        'active_page': 'dashboard',
        'current_year': timezone.now().year
    }
    return render(request, 'core/main/dashboard/dashboard.html', context)

def get_dashboard_stats(request):
    """Get all dashboard statistics"""
    try:
        now = timezone.now()
        current_year = now.year
        current_month = now.month
        thirty_days_ago = now - timedelta(days=30)
        
        # Basic stats
        total_businesses = Bops.objects.filter(is_deleted=False).count()
        
        # Bill statistics
        bills = BopsBills.objects.filter(is_deleted=False)
        total_bills = bills.count()
        total_bill_amount = bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Status breakdown
        status_counts = {
            'draft': bills.filter(status='draft').count(),
            'generated': bills.filter(status='generated').count(),
            'sent': bills.filter(status='sent').count(),
            'paid': bills.filter(status='paid').count(),
            'overdue': bills.filter(status='overdue').count(),
            'cancelled': bills.filter(status='cancelled').count(),
        }
        
        # Paid bills
        paid_bills = bills.filter(status='paid')
        paid_count = paid_bills.count()
        paid_amount = paid_bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Overdue bills
        overdue_bills = bills.filter(
            status__in=['generated', 'sent'],
            due_date__lt=now.date()
        )
        overdue_count = overdue_bills.count()
        overdue_amount = overdue_bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # This month's bills
        month_bills = bills.filter(
            generated_date__year=current_year,
            generated_date__month=current_month
        )
        month_count = month_bills.count()
        month_amount = month_bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # This month's payments
        month_payments = PaymentTransaction.objects.filter(
            bill_type='business',
            status='completed',
            completed_at__year=current_year,
            completed_at__month=current_month
        )
        month_payment_amount = month_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Payment success rate
        total_payment_attempts = PaymentTransaction.objects.filter(bill_type='business').count()
        successful_payments = PaymentTransaction.objects.filter(bill_type='business', status='completed').count()
        payment_success_rate = round((successful_payments / total_payment_attempts * 100), 1) if total_payment_attempts > 0 else 0
        
        # Collection rate
        collection_rate = round((paid_amount / total_bill_amount * 100), 1) if total_bill_amount > 0 else 0
        
        # Click tracking stats
        total_clicks = PaymentLinkClick.objects.filter(
            bill_type='business',
            clicked_at__gte=thirty_days_ago
        ).count()
        
        visited_not_paid = BopsBills.objects.filter(
            is_deleted=False,
            click_count__gt=0
        ).exclude(status='paid').count()
        
        # Revenue by year
        revenue_by_year = []
        for year in range(current_year - 3, current_year + 1):
            year_bills = bills.filter(billing_year=year)
            year_paid = year_bills.filter(status='paid')
            revenue_by_year.append({
                'year': year,
                'total': float(year_bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
                'collected': float(year_paid.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
                'pending': float(year_bills.exclude(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
            })
        
        # Status distribution for chart
        status_distribution = [
            {'status': 'Paid', 'count': status_counts['paid'], 'color': '#28a745'},
            {'status': 'Pending', 'count': status_counts['generated'] + status_counts['sent'], 'color': '#ffc107'},
            {'status': 'Overdue', 'count': status_counts['overdue'], 'color': '#dc3545'},
            {'status': 'Draft', 'count': status_counts['draft'], 'color': '#6c757d'},
        ]
        
        # Recent activity
        recent_activity = []
        
        # Recent payments
        recent_payments = PaymentTransaction.objects.filter(
            bill_type='business',
            status='completed'
        ).select_related('business_bill', 'business_bill__business').order_by('-completed_at')[:5]
        
        for payment in recent_payments:
            if payment.business_bill:
                recent_activity.append({
                    'type': 'payment',
                    'description': f"Payment of GH₵{payment.amount:,.2f} from {payment.business_bill.business.business_name}",
                    'time': payment.completed_at,
                    'icon': 'check-circle',
                    'color': 'success'
                })
        
        # Recent clicks
        recent_clicks = PaymentLinkClick.objects.filter(
            bill_type='business'
        ).select_related('business_bill', 'business_bill__business').order_by('-clicked_at')[:5]
        
        for click in recent_clicks:
            if click.business_bill:
                recent_activity.append({
                    'type': 'click',
                    'description': f"{click.business_bill.business.business_name} viewed bill via {click.get_link_type_display()}",
                    'time': click.clicked_at,
                    'icon': 'eye',
                    'color': 'info'
                })
        
        # Sort by time and take latest
        recent_activity.sort(key=lambda x: x['time'], reverse=True)
        recent_activity = recent_activity[:10]
        
        # Format times
        for activity in recent_activity:
            activity['time'] = activity['time'].strftime('%Y-%m-%d %H:%M')
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_businesses': total_businesses,
                'total_bills': total_bills,
                'total_bill_amount': float(total_bill_amount),
                'paid_count': paid_count,
                'paid_amount': float(paid_amount),
                'overdue_count': overdue_count,
                'overdue_amount': float(overdue_amount),
                'month_count': month_count,
                'month_amount': float(month_amount),
                'month_payment_amount': float(month_payment_amount),
                'collection_rate': collection_rate,
                'payment_success_rate': payment_success_rate,
                'total_clicks_30d': total_clicks,
                'visited_not_paid': visited_not_paid,
                'status_counts': status_counts,
                'revenue_by_year': revenue_by_year,
                'status_distribution': status_distribution,
            },
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        import traceback
        print(f"Dashboard error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def get_revenue_trends(request):
    """Get revenue trends for charts"""
    try:
        days = int(request.GET.get('days', 30))
        now = timezone.now()
        start_date = now - timedelta(days=days)
        
        # Daily revenue for the period
        daily_revenue = []
        
        for i in range(days):
            day = start_date + timedelta(days=i)
            next_day = day + timedelta(days=1)
            
            # Payments completed on this day
            day_payments = PaymentTransaction.objects.filter(
                bill_type='business',
                status='completed',
                completed_at__date=day.date()
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            daily_revenue.append({
                'date': day.strftime('%Y-%m-%d'),
                'amount': float(day_payments)
            })
        
        # Revenue by business category
        category_revenue = []
        categories = Bops.objects.filter(
            is_deleted=False,
            business_category__isnull=False
        ).exclude(business_category='').values('business_category').annotate(
            total=Sum('bills__total_amount', filter=Q(bills__status='paid')),
            count=Count('bills', filter=Q(bills__status='paid'))
        ).order_by('-total')[:10]
        
        for cat in categories:
            if cat['business_category'] and cat['total']:
                category_revenue.append({
                    'category': cat['business_category'][:30],
                    'amount': float(cat['total']),
                    'count': cat['count']
                })
        
        return JsonResponse({
            'success': True,
            'daily_revenue': daily_revenue,
            'category_revenue': category_revenue
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_top_performers(request):
    """Get top paying businesses and overdue lists"""
    try:
        # Top paying businesses
        top_payers = Bops.objects.filter(
            is_deleted=False,
            bills__status='paid'
        ).annotate(
            total_paid=Sum('bills__total_amount'),
            bill_count=Count('bills', filter=Q(bills__status='paid'))
        ).filter(total_paid__isnull=False).order_by('-total_paid')[:10]
        
        top_payers_data = []
        for business in top_payers:
            top_payers_data.append({
                'name': business.business_name,
                'account': business.account_number,
                'amount': float(business.total_paid),
                'count': business.bill_count
            })
        
        # Most overdue
        most_overdue = BopsBills.objects.filter(
            is_deleted=False,
            status__in=['generated', 'sent'],
            due_date__lt=timezone.now().date()
        ).select_related('business').order_by('due_date')[:10]
        
        overdue_data = []
        for bill in most_overdue:
            overdue_data.append({
                'business': bill.business.business_name,
                'bill_number': bill.bill_number,
                'amount': float(bill.total_amount),
                'due_date': bill.due_date.strftime('%Y-%m-%d'),
                'days_overdue': (timezone.now().date() - bill.due_date).days
            })
        
        # Recent clicks without payment
        recent_clicks_no_payment = PaymentLinkClick.objects.filter(
            bill_type='business',
            payment__isnull=True
        ).select_related('business_bill', 'business_bill__business').order_by('-clicked_at')[:10]
        
        clicks_data = []
        for click in recent_clicks_no_payment:
            if click.business_bill:
                clicks_data.append({
                    'business': click.business_bill.business.business_name,
                    'clicked_at': click.clicked_at.strftime('%Y-%m-%d %H:%M'),
                    'link_type': click.get_link_type_display()
                })
        
        return JsonResponse({
            'success': True,
            'top_payers': top_payers_data,
            'most_overdue': overdue_data,
            'recent_clicks_no_payment': clicks_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)