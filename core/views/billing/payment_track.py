# views.py - Add this endpoint to track link clicks

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
import json
from datetime import datetime, timedelta
from core.models import Bill, BopsBills, PaymentLinkClick

@csrf_exempt
def track_payment_link_click(request):
    """Track when a user clicks on a payment link"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_type = data.get('bill_type')
        bill_id = data.get('bill_id')
        link_type = data.get('link_type', 'web')
        
        if not bill_type or not bill_id:
            return JsonResponse({'error': 'Bill type and ID required'}, status=400)
        
        # Get the bill
        if bill_type == 'business':
            bill = get_object_or_404(BopsBills, id=bill_id)
        elif bill_type == 'property':
            bill = get_object_or_404(Bill, id=bill_id)
        else:
            return JsonResponse({'error': 'Invalid bill type'}, status=400)
        
        # Record the click
        click = bill.record_click(link_type, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Click tracked',
            'click_id': click.id,
            'click_count': bill.click_count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def payment_link_redirect(request, bill_type, bill_number, link_type='web'):
    """Redirect endpoint for payment links that tracks clicks"""
    try:
        # Find the bill
        if bill_type == 'business':
            bill = get_object_or_404(BopsBills, bill_number=bill_number)
        elif bill_type == 'property':
            bill = get_object_or_404(Bill, bill_number=bill_number)
        else:
            return HttpResponseRedirect('/')
        
        # Record the click
        bill.record_click(link_type, request)
        
        # Redirect to actual payment page
        if bill_type == 'business':
            return HttpResponseRedirect(f'/bopeasycollectible/?bill_id={bill.id}')
        else:
            return HttpResponseRedirect(f'/pay/bill/{bill_number}')
            
    except Exception as e:
        print(f"Error in payment link redirect: {e}")
        return HttpResponseRedirect('/')