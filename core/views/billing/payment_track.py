# views.py - Add this endpoint to track link clicks

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
import json
from datetime import datetime, timedelta
from core.models import BopsBills, PaymentLinkClick

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
        print(f"Payment link redirect called: bill_type={bill_type}, bill_number={bill_number}, link_type={link_type}")
        
        # Find the bill
        if bill_type == 'business' or bill_type == 'bop':
            # Try to find in BopsBills (which is a proxy to Bill)
            bill = get_object_or_404(BopsBills, bill_number=bill_number)
            print(f"Found bill: {bill.bill_number}, current click_count: {bill.click_count}")
            
            # Record the click
            try:
                click = bill.record_click(link_type, request)
                print(f"Click recorded successfully. New click_count: {bill.click_count}")
                print(f"Click ID: {click.id}")
            except Exception as e:
                print(f"Error recording click: {e}")
                import traceback
                traceback.print_exc()
            
            # Redirect to the bill view
            return HttpResponseRedirect(f'/bopeasycollectible/?bill_id={bill.id}')
        else:
            return HttpResponseRedirect('/')
            
    except Exception as e:
        print(f"Error in payment link redirect: {e}")
        import traceback
        traceback.print_exc()
        return HttpResponseRedirect('/')