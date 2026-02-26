# views.py (add these to the existing billing views)
# views.py
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Q
import json
from datetime import datetime, timedelta
from core.models import Bill, Penalty, Property, BillingCycle, PropertyType, TaxRate, Zone

def tax_calculation_page(request):
    """Render the tax calculation page"""
    context = {
        'page_title': 'Tax Calculation',
        'active_menu': 'tax_calculation'
    }
    return render(request, 'core/main/billing/tax-calculation.html', context)

def calculate_tax_for_property(request):
    """Calculate tax for a specific property with detailed breakdown"""
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        billing_cycle_id = data.get('billing_cycle_id')
        include_penalties = data.get('include_penalties', False)
        include_discounts = data.get('include_discounts', False)
        
        if not property_id:
            return JsonResponse({
                'success': False,
                'error': 'Property ID is required'
            }, status=400)
        
        property_obj = Property.objects.select_related('zone', 'property_type').get(id=property_id)
        billing_cycle = None
        if billing_cycle_id:
            billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
        
        # Get current tax rate
        current_date = datetime.now().date()
        tax_rate = TaxRate.objects.filter(
            zone=property_obj.zone,
            property_type=property_obj.property_type,
            effective_from__lte=current_date,
            effective_to__gte=current_date
        ).first()
        
        if not tax_rate:
            return JsonResponse({
                'success': False,
                'error': f'No active tax rate found for {property_obj.zone.name} - {property_obj.property_type.name}'
            }, status=400)
        
        # Calculate base tax
        base_tax = property_obj.assessed_value * (tax_rate.rate / 100)
        
        # Calculate penalties if any
        penalties = Penalty.objects.filter(
            property=property_obj,
            is_paid=False,
            due_date__gte=current_date
        )
        total_penalties = sum(penalty.amount for penalty in penalties) if include_penalties else 0
        
        # Calculate discounts (this would come from discount rules)
        discounts = 0
        if include_discounts:
            # Example discount logic - early payment discount
            if billing_cycle and current_date < billing_cycle.due_date:
                discounts = base_tax * Decimal('0.05')  # 5% early payment discount
        
        # Calculate total
        total_amount = base_tax + total_penalties - discounts
        
        # Prepare detailed breakdown
        calculation_breakdown = {
            'property_details': {
                'property_id': property_obj.property_id,
                'address': property_obj.address,
                'zone': property_obj.zone.name,
                'property_type': property_obj.property_type.name,
                'assessed_value': str(property_obj.assessed_value),
                'market_value': str(property_obj.market_value),
                'total_area': str(property_obj.total_area)
            },
            'tax_rate_details': {
                'rate': str(tax_rate.rate),
                'effective_from': tax_rate.effective_from.strftime('%Y-%m-%d'),
                'effective_to': tax_rate.effective_to.strftime('%Y-%m-%d') if tax_rate.effective_to else 'Indefinite',
                'description': tax_rate.description
            },
            'calculation_details': {
                'base_tax': str(base_tax),
                'penalties': str(total_penalties),
                'discounts': str(discounts),
                'total_amount': str(total_amount),
                'calculation_date': current_date.strftime('%Y-%m-%d')
            },
            'penalty_details': [],
            'billing_cycle': None
        }
        
        # Add penalty details
        for penalty in penalties:
            calculation_breakdown['penalty_details'].append({
                'type': penalty.penalty_type,
                'amount': str(penalty.amount),
                'reason': penalty.reason,
                'applied_date': penalty.applied_date.strftime('%Y-%m-%d'),
                'due_date': penalty.due_date.strftime('%Y-%m-%d')
            })
        
        # Add billing cycle details if provided
        if billing_cycle:
            calculation_breakdown['billing_cycle'] = {
                'name': billing_cycle.name,
                'cycle_type': billing_cycle.cycle_type,
                'start_date': billing_cycle.start_date.strftime('%Y-%m-%d'),
                'end_date': billing_cycle.end_date.strftime('%Y-%m-%d'),
                'due_date': billing_cycle.due_date.strftime('%Y-%m-%d')
            }
        
        return JsonResponse({
            'success': True,
            'calculation': calculation_breakdown
        })
        
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        }, status=404)
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error calculating tax: {str(e)}'
        }, status=500)
# views.py - Add this new function
def get_recent_calculations(request):
    """Get recent tax calculations for the DataTable"""
    try:
        # Get recent bills (last 50) to show in the calculations table
        recent_bills = Bill.objects.select_related(
            'property', 'property__zone', 'property__property_type'
        ).order_by('-generated_date')[:50]


        
        calculations = []
        for bill in recent_bills:
            calculations.append({
                'property_id': bill.property.property_id,
                'address': bill.property.address,
                'zone': bill.property.zone.name,
                'property_type': bill.property.property_type.name,
                'assessed_value': str(bill.property.assessed_value),
                'tax_rate': str((bill.tax_amount / bill.property.assessed_value * 100) if bill.property.assessed_value > 0 else 0),
                'base_tax': str(bill.tax_amount),
                'calculation_date': bill.generated_date.strftime('%Y-%m-%d'),
                'bill_id': bill.id
            })
        
        return JsonResponse({
            'success': True,
            'calculations': calculations
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching recent calculations: {str(e)}'
        }, status=500)

# Update the bulk_tax_calculation function to handle empty property_ids differently
def bulk_tax_calculation(request):
    """Calculate tax for multiple properties"""
    try:
        data = json.loads(request.body)
        property_ids = data.get('property_ids', [])
        billing_cycle_id = data.get('billing_cycle_id')
        
        # If no property IDs provided, return empty results instead of error
        # This allows the DataTable to initialize without errors
        if not property_ids:
            return JsonResponse({
                'success': True,
                'calculations': [],
                'totals': {
                    'property_count': 0,
                    'total_assessed_value': '0',
                    'total_base_tax': '0'
                },
                'errors': []
            })
        
        billing_cycle = None
        if billing_cycle_id:
            billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
        
        calculations = []
        errors = []
        
        for property_id in property_ids:
            try:
                property_obj = Property.objects.select_related('zone', 'property_type').get(id=property_id)
                
                # Get current tax rate
                current_date = datetime.now().date()
                tax_rate = TaxRate.objects.filter(
                    zone=property_obj.zone,
                    property_type=property_obj.property_type,
                    effective_from__lte=current_date,
                    effective_to__gte=current_date
                ).first()
                
                if not tax_rate:
                    errors.append(f'No tax rate for {property_obj.property_id}')
                    continue
                
                # Calculate base tax
                base_tax = property_obj.assessed_value * (tax_rate.rate / 100)
                
                calculation = {
                    'property_id': property_obj.property_id,
                    'address': property_obj.address,
                    'zone': property_obj.zone.name,
                    'property_type': property_obj.property_type.name,
                    'assessed_value': str(property_obj.assessed_value),
                    'tax_rate': str(tax_rate.rate),
                    'base_tax': str(base_tax),
                    'calculation_date': current_date.strftime('%Y-%m-%d')
                }
                
                calculations.append(calculation)
                
            except Property.DoesNotExist:
                errors.append(f'Property {property_id} not found')
            except Exception as e:
                errors.append(f'Error calculating tax for property {property_id}: {str(e)}')
        
        # Calculate totals
        total_assessed_value = sum(Decimal(calc['assessed_value']) for calc in calculations)
        total_base_tax = sum(Decimal(calc['base_tax']) for calc in calculations)
        
        return JsonResponse({
            'success': True,
            'calculations': calculations,
            'totals': {
                'property_count': len(calculations),
                'total_assessed_value': str(total_assessed_value),
                'total_base_tax': str(total_base_tax)
            },
            'errors': errors
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error in bulk calculation: {str(e)}'
        }, status=500)
    

def get_tax_calculation_history(request, property_id):
    """Get tax calculation history for a property"""
    try:
        property_obj = Property.objects.get(id=property_id)
        
        # Get all bills for this property
        bills = Bill.objects.filter(property=property_obj).select_related(
            'billing_cycle', 'created_by'
        ).order_by('-generated_date')
        
        history = []
        for bill in bills:
            history.append({
                'bill_number': bill.bill_number,
                'billing_cycle': bill.billing_cycle.name if bill.billing_cycle else 'N/A',
                'tax_amount': str(bill.tax_amount),
                'penalty_amount': str(bill.penalty_amount),
                'discount_amount': str(bill.discount_amount),
                'total_amount': str(bill.total_amount),
                'status': bill.status,
                'generated_date': bill.generated_date.strftime('%Y-%m-%d'),
                'due_date': bill.due_date.strftime('%Y-%m-%d'),
                'generated_by': bill.created_by.get_full_name() or bill.created_by.username
            })
        
        return JsonResponse({
            'success': True,
            'property_id': property_obj.property_id,
            'property_address': property_obj.address,
            'history': history
        })
        
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        }, status=404)
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'error': f'Error fetching calculation history: {str(e)}'
        }, status=500)

def simulate_tax_scenario(request):
    """Simulate tax calculation with different parameters"""
    try:
        data = json.loads(request.body)
        
        assessed_value = Decimal(data.get('assessed_value', 0))
        zone_id = data.get('zone_id')
        property_type_id = data.get('property_type_id')
        proposed_rate = data.get('proposed_rate')
        include_penalties = data.get('include_penalties', False)
        penalty_amount = Decimal(data.get('penalty_amount', 0))
        include_discounts = data.get('include_discounts', False)
        discount_percentage = Decimal(data.get('discount_percentage', 0))
        
        if not all([assessed_value, zone_id, property_type_id]):
            return JsonResponse({
                'success': False,
                'error': 'Assessed value, zone, and property type are required'
            }, status=400)
        
        zone = Zone.objects.get(id=zone_id)
        property_type = PropertyType.objects.get(id=property_type_id)
        
        # Get current rate for comparison
        current_date = datetime.now().date()
        current_tax_rate = TaxRate.objects.filter(
            zone=zone,
            property_type=property_type,
            effective_from__lte=current_date,
            effective_to__gte=current_date
        ).first()
        
        # Use proposed rate if provided, otherwise use current rate
        tax_rate = Decimal(proposed_rate) if proposed_rate else current_tax_rate.rate
        
        # Calculate taxes
        current_tax = assessed_value * (current_tax_rate.rate / 100) if current_tax_rate else Decimal(0)
        proposed_tax = assessed_value * (tax_rate / 100)
        
        # Apply discounts
        discount_amount = proposed_tax * (discount_percentage / 100) if include_discounts else Decimal(0)
        final_tax = proposed_tax + penalty_amount - discount_amount
        
        # Calculate difference
        tax_difference = proposed_tax - current_tax
        percentage_change = (tax_difference / current_tax * 100) if current_tax > 0 else Decimal(100)
        
        scenario_results = {
            'current_scenario': {
                'tax_rate': str(current_tax_rate.rate) if current_tax_rate else 'N/A',
                'tax_amount': str(current_tax),
                'description': 'Current tax rate' if current_tax_rate else 'No current rate'
            },
            'proposed_scenario': {
                'tax_rate': str(tax_rate),
                'tax_amount': str(proposed_tax),
                'penalty_amount': str(penalty_amount),
                'discount_amount': str(discount_amount),
                'final_amount': str(final_tax),
                'description': 'Proposed scenario'
            },
            'comparison': {
                'amount_difference': str(tax_difference),
                'percentage_change': str(percentage_change),
                'is_increase': tax_difference > 0
            },
            'parameters': {
                'assessed_value': str(assessed_value),
                'zone': zone.name,
                'property_type': property_type.name,
                'include_penalties': include_penalties,
                'include_discounts': include_discounts
            }
        }
        
        return JsonResponse({
            'success': True,
            'scenario': scenario_results
        })
        
    except Zone.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Zone not found'
        }, status=404)
    except PropertyType.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property type not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error simulating tax scenario: {str(e)}'
        }, status=500)

def get_tax_summary_report(request):
    """Generate tax summary report by zone and property type"""
    try:
        current_date = datetime.now().date()
        
        # Get all active properties
        active_properties = Property.objects.filter(status='active').select_related('zone', 'property_type')
        
        # Group by zone and property type
        summary_data = {}
        total_assessed_value = Decimal(0)
        total_expected_tax = Decimal(0)
        
        for property_obj in active_properties:
            zone_name = property_obj.zone.name
            property_type_name = property_obj.property_type.name
            key = f"{zone_name}_{property_type_name}"
            
            if key not in summary_data:
                summary_data[key] = {
                    'zone': zone_name,
                    'property_type': property_type_name,
                    'property_count': 0,
                    'total_assessed_value': Decimal(0),
                    'total_expected_tax': Decimal(0)
                }
            
            # Get tax rate
            tax_rate = TaxRate.objects.filter(
                zone=property_obj.zone,
                property_type=property_obj.property_type,
                effective_from__lte=current_date,
                effective_to__gte=current_date
            ).first()
            
            expected_tax = property_obj.assessed_value * (tax_rate.rate / 100) if tax_rate else Decimal(0)
            
            summary_data[key]['property_count'] += 1
            summary_data[key]['total_assessed_value'] += property_obj.assessed_value
            summary_data[key]['total_expected_tax'] += expected_tax
            
            total_assessed_value += property_obj.assessed_value
            total_expected_tax += expected_tax
        
        # Convert to list and sort by total expected tax
        summary_list = sorted(
            summary_data.values(), 
            key=lambda x: x['total_expected_tax'], 
            reverse=True
        )
        
        # Format numbers for display
        for item in summary_list:
            item['total_assessed_value'] = str(item['total_assessed_value'])
            item['total_expected_tax'] = str(item['total_expected_tax'])
        
        return JsonResponse({
            'success': True,
            'summary': summary_list,
            'totals': {
                'total_properties': active_properties.count(),
                'total_assessed_value': str(total_assessed_value),
                'total_expected_tax': str(total_expected_tax)
            },
            'report_date': current_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error generating tax summary: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def save_calculation_as_draft(request):
    """Save tax calculation as a draft bill"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            
            property_id = data.get('property_id')
            billing_cycle_id = data.get('billing_cycle_id')
            tax_amount = data.get('tax_amount')
            penalty_amount = data.get('penalty_amount', 0)
            discount_amount = data.get('discount_amount', 0)
            notes = data.get('notes', '')
            
            if not all([property_id, tax_amount]):
                return JsonResponse({
                    'success': False,
                    'error': 'Property and tax amount are required'
                }, status=400)
            
            property_obj = Property.objects.get(id=property_id)
            billing_cycle = None
            if billing_cycle_id:
                billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
            # Generate draft bill number
            bill_number = f"DRAFT-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            
            # Calculate total amount
            total_amount = Decimal(tax_amount) + Decimal(penalty_amount) - Decimal(discount_amount)
            
            # Create draft bill
            bill = Bill.objects.create(
                bill_number=bill_number,
                property=property_obj,
                billing_cycle=billing_cycle,
                tax_amount=tax_amount,
                penalty_amount=penalty_amount,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status='draft',
                due_date=billing_cycle.due_date if billing_cycle else datetime.now().date() + timedelta(days=30),
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Draft bill {bill_number} created successfully',
                'bill_id': bill.id,
                'bill_number': bill_number
            })
            
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        }, status=404)
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error saving draft bill: {str(e)}'
        }, status=500)