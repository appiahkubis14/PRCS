# views.py - Add monitoring dashboard views

from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from datetime import timedelta
import json
from core.models import BopsBills, PaymentLinkClick, PaymentTransaction

def payment_monitoring_dashboard(request):
    """Main payment monitoring dashboard"""
    context = {
        'page_title': 'Payment Monitoring Dashboard',
        'active_page': 'payment_monitoring'
    }
    return render(request, 'core/main/billing/payment_monitoring.html', context)

def get_bops_bills_with_tracking(request):
    """API endpoint to get BOPs bills with tracking data"""
    try:
        # Get query parameters
        status = request.GET.get('status', '')
        year = request.GET.get('year', '')
        search = request.GET.get('search', '')
        
        # Base queryset
        bills = BopsBills.objects.filter(is_deleted=False).select_related('business')
        
        # Apply filters
        if status:
            bills = bills.filter(status=status)
        if year:
            bills = bills.filter(billing_year=year)
        if search:
            bills = bills.filter(
                Q(bill_number__icontains=search) |
                Q(business__business_name__icontains=search) |
                Q(business__account_number__icontains=search)
            )
        
        # Annotate with payment and click stats
        bills = bills.annotate(
            payment_count=Count('payments', filter=Q(payments__status='completed')),
            total_paid=Sum('payments__amount', filter=Q(payments__status='completed')),
            click_count_value=F('click_count'),
            last_click=F('last_clicked_at')
        )
        
        # Prepare data
        data = []
        for bill in bills:
            # Calculate days since last click
            days_since_click = None
            if bill.last_clicked_at:
                days_since_click = (timezone.now() - bill.last_clicked_at).days
            
            # Determine if visited but not paid
            visited_not_paid = bill.click_count > 0 and bill.status not in ['paid', 'cancelled']
            
            data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'business_name': bill.business.business_name,
                'account_number': bill.business.account_number,
                'owner_name': bill.business.owner_name,
                'billing_year': bill.billing_year,
                'tax_amount': float(bill.tax_amount),
                'penalty_amount': float(bill.penalty_amount),
                'discount_amount': float(bill.discount_amount),
                'total_amount': float(bill.total_amount),
                'status': bill.status,
                'generated_date': bill.generated_date.strftime('%Y-%m-%d %H:%M') if bill.generated_date else '',
                'due_date': bill.due_date.strftime('%Y-%m-%d') if bill.due_date else '',
                'sent_date': bill.sent_date.strftime('%Y-%m-%d %H:%M') if bill.sent_date else '',
                'click_count': bill.click_count or 0,
                'last_clicked_at': bill.last_clicked_at.strftime('%Y-%m-%d %H:%M') if bill.last_clicked_at else 'Never',
                'last_click_ip': bill.last_click_ip or '',
                'days_since_click': days_since_click,
                'visited_not_paid': visited_not_paid,
                'payment_count': bill.payment_count or 0,
                'total_paid': float(bill.total_paid) if bill.total_paid else 0,
                'payment_status': 'Paid' if bill.status == 'paid' else 'Pending',
                'phone_number': bill.business.phone_number,
                'business_email': bill.business.business_email,
            })
        
        # Get summary stats
        summary = {
            'total_bills': bills.count(),
            'total_amount': float(bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
            'paid_bills': bills.filter(status='paid').count(),
            'paid_amount': float(bills.filter(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
            'overdue_bills': bills.filter(status='overdue').count(),
            'sent_bills': bills.filter(status='sent').count(),
            'visited_not_paid': bills.filter(click_count__gt=0).exclude(status='paid').count(),
        }
        
        return JsonResponse({
            'success': True,
            'data': data,
            'summary': summary,
            'total_records': len(data)
        })
        
    except Exception as e:
        import traceback
        print(f"Error in get_bops_bills_with_tracking: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def get_bops_bill_detail(request, bill_id):
    """Get detailed tracking information for a specific bill"""
    try:
        bill = BopsBills.objects.get(id=bill_id, is_deleted=False)
        
        # Get all link clicks
        clicks = PaymentLinkClick.objects.filter(
            bill_type='business',
            business_bill=bill
        ).order_by('-clicked_at')
        
        # Get all payments
        payments = PaymentTransaction.objects.filter(
            business_bill=bill
        ).order_by('-initiated_at')
        
        click_data = []
        for click in clicks:
            click_data.append({
                'id': click.id,
                'link_type': click.link_type,
                'clicked_at': click.clicked_at.strftime('%Y-%m-%d %H:%M:%S'),
                'ip_address': click.ip_address,
                'user_agent': click.user_agent[:100] + '...' if len(click.user_agent) > 100 else click.user_agent,
                'referer': click.referer,
                'payment_made': click.payment is not None
            })
        
        payment_data = []
        for payment in payments:
            payment_data.append({
                'id': payment.id,
                'transaction_id': payment.transaction_id,
                'amount': float(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'initiated_at': payment.initiated_at.strftime('%Y-%m-%d %H:%M:%S'),
                'completed_at': payment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.completed_at else None,
            })
        
        return JsonResponse({
            'success': True,
            'bill': {
                'id': bill.id,
                'bill_number': bill.bill_number,
                'business_name': bill.business.business_name,
                'account_number': bill.business.account_number,
                'owner_name': bill.business.owner_name,
                'phone_number': bill.business.phone_number,
                'email': bill.business.business_email,
                'billing_year': bill.billing_year,
                'total_amount': float(bill.total_amount),
                'status': bill.status,
                'due_date': bill.due_date.strftime('%Y-%m-%d'),
                'generated_date': bill.generated_date.strftime('%Y-%m-%d %H:%M'),
                'sent_date': bill.sent_date.strftime('%Y-%m-%d %H:%M') if bill.sent_date else None,
                'click_count': bill.click_count or 0,
                'last_clicked_at': bill.last_clicked_at.strftime('%Y-%m-%d %H:%M') if bill.last_clicked_at else None,
                'last_click_ip': bill.last_click_ip,
            },
            'clicks': click_data,
            'payments': payment_data,
            'clicks_count': len(click_data),
            'payments_count': len(payment_data)
        })
        
    except BopsBills.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bill not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_dashboard_stats(request):
    """Get dashboard statistics"""
    try:
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Overall stats
        total_bills = BopsBills.objects.filter(is_deleted=False).count()
        total_amount = BopsBills.objects.filter(is_deleted=False).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Payment stats
        paid_bills = BopsBills.objects.filter(is_deleted=False, status='paid').count()
        paid_amount = BopsBills.objects.filter(is_deleted=False, status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Overdue stats
        overdue_bills = BopsBills.objects.filter(
            is_deleted=False,
            status__in=['generated', 'sent'],
            due_date__lt=now.date()
        ).count()
        
        # Click stats
        total_clicks = PaymentLinkClick.objects.filter(
            bill_type='business',
            created_at__gte=thirty_days_ago
        ).count()
        
        visited_not_paid = BopsBills.objects.filter(
            is_deleted=False,
            click_count__gt=0
        ).exclude(status='paid').count()
        
        # Recent activity
        recent_clicks = PaymentLinkClick.objects.filter(
            bill_type='business'
        ).select_related('business_bill').order_by('-clicked_at')[:10]
        
        recent_activity = []
        for click in recent_clicks:
            recent_activity.append({
                'bill_number': click.business_bill.bill_number,
                'business_name': click.business_bill.business.business_name,
                'link_type': click.link_type,
                'clicked_at': click.clicked_at.strftime('%Y-%m-%d %H:%M'),
                'status': click.business_bill.status,
                'paid': click.payment is not None
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_bills': total_bills,
                'total_amount': float(total_amount),
                'paid_bills': paid_bills,
                'paid_amount': float(paid_amount),
                'paid_percentage': round((paid_bills / total_bills * 100), 1) if total_bills > 0 else 0,
                'overdue_bills': overdue_bills,
                'total_clicks_30d': total_clicks,
                'visited_not_paid': visited_not_paid,
                'collection_rate': round((paid_amount / total_amount * 100), 1) if total_amount > 0 else 0,
            },
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)