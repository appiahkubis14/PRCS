from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from core.models import Property, TaxRate, BillingCycle, Bill
import json

@login_required
def property_valuation(request):
    """Render the property valuation page"""
    context = {
        'title': 'Property Valuation',
        'path': 'Property Management/Property Valuation',
        'properties': Property.objects.filter(is_deleted=False, status='active'),
        'tax_rates': TaxRate.objects.filter(is_deleted=False),
        'billing_cycles': BillingCycle.objects.filter(is_deleted=False, is_active=True),
    }
    return render(request, 'core/main/property-registry/property-valuation.html', context)

@login_required
@require_http_methods(["GET"])
def get_valuations(request):
    """Get all property valuations for DataTable"""
    try:
        # Get valuations from bills since they contain the valuation data
        bills = Bill.objects.filter(is_deleted=False).select_related(
            'property', 'billing_cycle', 'property__zone', 'property__property_type'
        )
        
        data = []
        for bill in bills:
            # Get property details
            prop = bill.property
            
            data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'property_id': prop.property_id,
                'address': prop.address,
                'zone': prop.zone.name if prop.zone else '',
                'property_type': prop.property_type.name if prop.property_type else '',
                'market_value': float(prop.market_value) if prop.market_value else 0,
                'assessed_value': float(prop.assessed_value) if prop.assessed_value else 0,
                'tax_amount': float(bill.tax_amount) if bill.tax_amount else 0,
                'billing_cycle': bill.billing_cycle.name if bill.billing_cycle else '',
                'status': bill.status,
                'due_date': bill.due_date.strftime('%Y-%m-%d') if bill.due_date else '',
                'generated_date': bill.generated_date.strftime('%Y-%m-%d') if bill.generated_date else '',
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def create_valuation(request):
    """Create new property valuation and bill"""
    try:
        data = request.POST.dict()
        
        with transaction.atomic():
            # Get property
            property_obj = get_object_or_404(Property, id=data.get('property'), is_deleted=False)
            
            # Get tax rate for this property's zone and type
            tax_rate = TaxRate.objects.filter(
                zone=property_obj.zone,
                property_type=property_obj.property_type,
                is_deleted=False
            ).first()
            
            if not tax_rate:
                return JsonResponse({
                    'success': False, 
                    'error': f'No tax rate found for {property_obj.zone.name} - {property_obj.property_type.name}'
                })
            
            # Calculate tax amount
            tax_amount = (property_obj.assessed_value * tax_rate.rate) / 100
            
            # Generate bill number
            bill_number = f"BILL-{timezone.now().strftime('%Y%m%d')}-{property_obj.property_id}"
            
            # Create bill
            bill = Bill(
                bill_number=bill_number,
                property=property_obj,
                billing_cycle_id=data.get('billing_cycle'),
                tax_amount=tax_amount,
                penalty_amount=0,
                discount_amount=0,
                total_amount=tax_amount,
                status='generated',
                due_date=data.get('due_date'),
                created_by=request.user
            )
            bill.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Property valuation and bill created successfully!',
            'bill_number': bill_number
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to create valuation: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_valuation_detail(request, bill_id):
    """Get valuation details for editing"""
    try:
        bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
        prop = bill.property
        
        # Get tax rate
        tax_rate = TaxRate.objects.filter(
            zone=prop.zone,
            property_type=prop.property_type,
            is_deleted=False
        ).first()
        
        data = {
            'id': bill.id,
            'bill_number': bill.bill_number,
            'property_id': prop.id,
            'property_display': f"{prop.property_id} - {prop.address}",
            'zone': prop.zone.name if prop.zone else '',
            'property_type': prop.property_type.name if prop.property_type else '',
            'market_value': float(prop.market_value) if prop.market_value else None,
            'assessed_value': float(prop.assessed_value) if prop.assessed_value else None,
            'tax_rate': float(tax_rate.rate) if tax_rate else 0,
            'tax_amount': float(bill.tax_amount) if bill.tax_amount else None,
            'billing_cycle_id': bill.billing_cycle_id,
            'status': bill.status,
            'due_date': bill.due_date.strftime('%Y-%m-%d') if bill.due_date else None,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_valuation(request, bill_id):
    """Update property valuation"""
    try:
        bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
        data = request.POST.dict()
        
        with transaction.atomic():
            # Update bill details
            bill.billing_cycle_id = data.get('billing_cycle', bill.billing_cycle_id)
            bill.status = data.get('status', bill.status)
            bill.due_date = data.get('due_date', bill.due_date)
            bill.modified_by = request.user
            
            # If assessed value changed, recalculate tax
            if data.get('assessed_value'):
                prop = bill.property
                # Convert string to Decimal
                assessed_value = Decimal(data.get('assessed_value'))
                prop.assessed_value = assessed_value
                prop.modified_by = request.user
                prop.save()
                
                # Recalculate tax
                tax_rate = TaxRate.objects.filter(
                    zone=prop.zone,
                    property_type=prop.property_type,
                    is_deleted=False
                ).first()
                
                if tax_rate:
                    new_tax_amount = (assessed_value * tax_rate.rate) / 100
                    bill.tax_amount = new_tax_amount
                    # Also fix this line - bill.tax_amount is already set above
                    bill.total_amount = Decimal(bill.tax_amount) + new_tax_amount + bill.penalty_amount - bill.discount_amount
            
            bill.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Valuation updated successfully!'
        })
        
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False, 
            'error': f'Failed to update valuation: {str(e)}'
        })
    
    

@login_required
@require_http_methods(["DELETE"])
def delete_valuation(request, bill_id):
    """Delete valuation (soft delete)"""
    try:
        bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
        
        bill.is_deleted = True
        bill.deleted_by = request.user
        bill.deleted_at = timezone.now()
        bill.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Valuation deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to delete valuation: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_property_details(request, property_id):
    """Get property details for valuation"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        
        # Get tax rate for this property
        tax_rate = TaxRate.objects.filter(
            zone=property_obj.zone,
            property_type=property_obj.property_type,
            is_deleted=False
        ).first()
        
        data = {
            'property_id': property_obj.property_id,
            'address': property_obj.address,
            'zone': property_obj.zone.name if property_obj.zone else '',
            'property_type': property_obj.property_type.name if property_obj.property_type else '',
            'market_value': float(property_obj.market_value) if property_obj.market_value else 0,
            'assessed_value': float(property_obj.assessed_value) if property_obj.assessed_value else 0,
            'total_area': float(property_obj.total_area) if property_obj.total_area else 0,
            'tax_rate': float(tax_rate.rate) if tax_rate else 0,
            'calculated_tax': float((property_obj.assessed_value * tax_rate.rate) / 100) if tax_rate else 0,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})