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
        from django.db.models import Count, Sum, Q, F
        from django.utils import timezone
        
        # Get query parameters
        status = request.GET.get('status', '')
        year = request.GET.get('year', '')
        search = request.GET.get('search', '')
        
        # Base queryset - use BopsBills directly
        bills = BopsBills.objects.select_related('business').all()
        
        # Debug: Print first bill to see fields
        first_bill = bills.first()
        if first_bill:
            print(f"First bill click_count: {first_bill.click_count}")
            print(f"First bill last_clicked_at: {first_bill.last_clicked_at}")
            print(f"First bill hasattr click_count: {hasattr(first_bill, 'click_count')}")
        
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
        
        # Annotate with payment stats (if PaymentTransaction exists)
        # But don't use annotations that might interfere with existing fields
        bills = bills.order_by('-last_clicked_at')  # Show most recent clicks first
        
        # Prepare data
        data = []
        for bill in bills:
            # Calculate days since last click
            days_since_click = None
            if bill.last_clicked_at:
                days_since_click = (timezone.now() - bill.last_clicked_at).days
            
            # Determine if visited but not paid
            visited_not_paid = (bill.click_count or 0) > 0 and bill.status not in ['paid', 'cancelled']
            
            # Get click details from PaymentLinkClick table for this bill
            recent_clicks = PaymentLinkClick.objects.filter(bill=bill).order_by('-clicked_at')[:5]
            click_details = []
            for click in recent_clicks:
                click_details.append({
                    'clicked_at': click.clicked_at.strftime('%Y-%m-%d %H:%M'),
                    'link_type': click.link_type,
                    'ip_address': click.ip_address
                })
            
            data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'business_name': bill.business.business_name if hasattr(bill.business, 'business_name') else "",
                'account_number': bill.business.account_number if hasattr(bill.business, 'account_number') else "",
                'owner_name': bill.business.owner_name if hasattr(bill.business, 'owner_name') else "",
                'billing_year': bill.billing_year,
                'tax_amount': float(bill.tax_amount),
                'penalty_amount': float(bill.penalty_amount),
                'discount_amount': float(bill.discount_amount),
                'total_amount': float(bill.total_amount),
                'status': bill.status,
                'generated_date': bill.issued_at.strftime('%Y-%m-%d %H:%M') if bill.issued_at else '',
                'due_date': bill.due_date.strftime('%Y-%m-%d') if bill.due_date else '',
                'sent_date': bill.sent_date.strftime('%Y-%m-%d %H:%M') if bill.sent_date else '',
                'click_count': bill.click_count or 0,  # This should come from the Bill model
                'last_clicked_at': bill.last_clicked_at.strftime('%Y-%m-%d %H:%M') if bill.last_clicked_at else 'Never',
                'last_click_ip': bill.last_click_ip or '',
                'days_since_click': days_since_click if days_since_click is not None else -1,
                'visited_not_paid': visited_not_paid,
                'recent_clicks': click_details,  # Add recent click details for debugging
                'payment_status': 'Paid' if bill.status == 'paid' else 'Pending',
                'phone_number': bill.business.phone_number if hasattr(bill.business, 'phone_number') else "",
                'business_email': bill.business.business_email if hasattr(bill.business, 'business_email') else "",
            })
        
        # Get summary stats - use direct database queries
        total_bills = BopsBills.objects.count()
        total_amount = BopsBills.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        paid_bills = BopsBills.objects.filter(status='paid').count()
        paid_amount = BopsBills.objects.filter(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        overdue_bills = BopsBills.objects.filter(status='overdue').count()
        sent_bills = BopsBills.objects.filter(status='sent').count()
        visited_not_paid = BopsBills.objects.filter(click_count__gt=0).exclude(status='paid').count()
        
        summary = {
            'total_bills': total_bills,
            'total_amount': float(total_amount),
            'paid_bills': paid_bills,
            'paid_amount': float(paid_amount),
            'overdue_bills': overdue_bills,
            'sent_bills': sent_bills,
            'visited_not_paid': visited_not_paid,
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
        bill = BopsBills.objects.get(id=bill_id, )
        
        # Get all link clicks
        clicks = PaymentLinkClick.objects.filter(
            bill_type='business',
            bill=bill
        ).order_by('-clicked_at')
        
        # Get all payments
        payments = PaymentTransaction.objects.filter(
            bill=bill
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
                'generated_date': bill.issued_at.strftime('%Y-%m-%d %H:%M'),
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
        print(f"Error in get_bops_bill_detail: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_dashboard_stats(request):
    """Get dashboard statistics"""
    try:
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Overall stats
        total_bills = BopsBills.objects.all().count()
        total_amount = BopsBills.objects.all().aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Payment stats
        paid_bills = BopsBills.objects.filter(status='paid').count()
        paid_amount = BopsBills.objects.filter(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Overdue stats
        overdue_bills = BopsBills.objects.filter(
            
            status__in=['generated', 'sent'],
            due_date__lt=now.date()
        ).count()
        
        # Click stats
        total_clicks = PaymentLinkClick.objects.filter(
            bill_type='business',
            created_at__gte=thirty_days_ago
        ).count()
        
        visited_not_paid = BopsBills.objects.filter(
            
            click_count__gt=0
        ).exclude(status='paid').count()
        
        # Recent activity
        recent_clicks = PaymentLinkClick.objects.filter(
            bill_type='business'
        ).select_related('bill').order_by('-clicked_at')[:10]
        
        recent_activity = []
        for click in recent_clicks:
            recent_activity.append({
                'bill_number': click.bill.bill_number,
                'business_name': click.bill.business.business_name,
                'link_type': click.link_type,
                'clicked_at': click.clicked_at.strftime('%Y-%m-%d %H:%M'),
                'status': click.bill.status,
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
        print(f"Error in get_dashboard_stats: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)