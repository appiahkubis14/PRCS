# views.py
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Q
import json
from django.http import HttpRequest
from django.utils import timezone
from datetime import datetime
from core.models import Property, TaxRate, Bops, BopsBills


def bill_generation_page(request):
    """Render the main bill generation page"""
    context = {
        'page_title': 'Bill Generation',
        'active_menu': 'billing_generation'
    }
    return render(request, 'core/main/billing/bill-generation.html', context)

# def get_bills(request):
#     """Get all bills for DataTable"""
#     try:
#         # Get pagination parameters from DataTables
#         draw = int(request.GET.get('draw', 1))
#         start = int(request.GET.get('start', 0))
#         length = int(request.GET.get('length', 10))
#         search_value = request.GET.get('search[value]', '')
        
#         # Base queryset
#         bills = Bill.objects.select_related(
#             'property', 
#             'billing_cycle', 
#             'created_by'
#         ).all()
        
#         # Apply search filter
#         if search_value:
#             bills = bills.filter(
#                 Q(bill_number__icontains=search_value) |
#                 Q(property__property_id__icontains=search_value) |
#                 Q(property__address__icontains=search_value) |
#                 Q(status__icontains=search_value)
#             )
        
#         # Get total count
#         total_records = bills.count()
        
#         # Apply ordering and pagination
#         order_column = int(request.GET.get('order[0][column]', 0))
#         order_dir = request.GET.get('order[0][dir]', 'asc')
        
#         # Map column index to field name
#         column_mapping = {
#             0: 'id',
#             1: 'bill_number',
#             2: 'property__property_id',
#             3: 'property__address',
#             4: 'billing_cycle__name',
#             5: 'total_amount',
#             6: 'status',
#             7: 'generated_date',
#             8: 'due_date'
#         }
        
#         order_field = column_mapping.get(order_column, 'id')
#         if order_dir == 'desc':
#             order_field = f'-{order_field}'
        
#         bills = bills.order_by(order_field)[start:start + length]
        
#         # Prepare data for DataTables
#         data = []
#         for bill in bills:
#             # Get primary owner
#             primary_owner = bill.property.owners.filter(is_primary_owner=True).first()
#             owner_name = primary_owner.owner_name if primary_owner else 'N/A'
            
#             data.append({
#                 'id': bill.id,
#                 'bill_number': bill.bill_number,
#                 'property_id': bill.property.property_id,
#                 'address': bill.property.address,
#                 'owner_name': owner_name,
#                 'billing_cycle': bill.billing_cycle.name if bill.billing_cycle else 'N/A',
#                 'tax_amount': str(bill.tax_amount),
#                 'penalty_amount': str(bill.penalty_amount),
#                 'discount_amount': str(bill.discount_amount),
#                 'total_amount': str(bill.total_amount),
#                 'status': bill.status,
#                 'generated_date': bill.generated_date.strftime('%Y-%m-%d %H:%M:%S'),
#                 'due_date': bill.due_date.strftime('%Y-%m-%d'),
#                 'created_by': bill.created_by.get_full_name() or bill.created_by.username,
#             })
        
#         response = {
#             'draw': draw,
#             'recordsTotal': total_records,
#             'recordsFiltered': total_records,
#             'data': data
#         }
        
#         return JsonResponse(response)
        
#     except Exception as e:
#         return JsonResponse({
#             'error': f'Error fetching bills: {str(e)}'
#         }, status=500)

def get_properties_for_billing(request):
    """Get properties that can be billed"""
    try:
        properties = Property.objects.select_related('zone', 'property_type').filter(
            is_deleted=False
        ).prefetch_related('owners')
        
        property_data = []
        for prop in properties:
            primary_owner = prop.owners.filter(is_primary_owner=True).first() if hasattr(prop, 'owners') else None
            
            # Get property ID - use id if property_id doesn't exist
            property_id = getattr(prop, 'property_id', None) or f"PROP-{prop.id}"
            
            property_data.append({
                'id': prop.id,
                'property_id': property_id,
                'address': prop.address or '',
                'zone_id': prop.zone.id if prop.zone else None,
                'zone_name': prop.zone.name if prop.zone else '',
                'property_type_id': prop.property_type.id if prop.property_type else None,
                'property_type_name': prop.property_type.name if prop.property_type else '',
                'assessed_value': str(getattr(prop, 'assessed_value', 0) or 0),
                'market_value': str(getattr(prop, 'market_value', 0) or 0),
                'total_area': str(getattr(prop, 'total_area', getattr(prop, 'area', 0)) or 0),
                'owner_name': primary_owner.owner_name if primary_owner and hasattr(primary_owner, 'owner_name') else 'N/A',
                'owner_id': primary_owner.id if primary_owner else None
            })
        
        return JsonResponse({
            'success': True,
            'properties': property_data
        })
        
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'error': f'Error fetching properties: {str(e)}'
        }, status=500)

def get_billing_cycles(request):
    """Get active billing cycles"""
    try:
        cycles = BillingCycle.objects.filter(is_active=True)
        
        cycle_data = []
        for cycle in cycles:
            cycle_data.append({
                'id': cycle.id,
                'name': cycle.name,
                'cycle_type': cycle.cycle_type,
                'start_date': cycle.start_date.strftime('%Y-%m-%d'),
                'end_date': cycle.end_date.strftime('%Y-%m-%d'),
                'due_date': cycle.due_date.strftime('%Y-%m-%d')
            })
        
        return JsonResponse({
            'success': True,
            'billing_cycles': cycle_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching billing cycles: {str(e)}'
        }, status=500)

def calculate_tax_amount(request):
    """Calculate tax amount for a property"""
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        billing_cycle_id = data.get('billing_cycle_id')
        
        if not property_id or not billing_cycle_id:
            return JsonResponse({
                'success': False,
                'error': 'Property ID and Billing Cycle ID are required'
            }, status=400)
        
        property_obj = Property.objects.get(id=property_id)
        billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
        
        # Get current tax rate for the property's zone and type
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
                'error': f'No tax rate found for {property_obj.zone.name} - {property_obj.property_type.name}'
            }, status=400)
        
        # Calculate tax amount (assessed_value * tax_rate)
        tax_amount = property_obj.assessed_value * (tax_rate.rate / 100)
        
        return JsonResponse({
            'success': True,
            'tax_amount': str(tax_amount),
            'tax_rate': str(tax_rate.rate),
            'assessed_value': str(property_obj.assessed_value)
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

# @csrf_exempt
# @require_http_methods(["POST"])
# def generate_bill(request):
#     """Generate a new bill"""
#     try:
#         with transaction.atomic():
#             data = json.loads(request.body)
            
#             property_id = data.get('property_id')
#             billing_cycle_id = data.get('billing_cycle_id')
#             tax_amount = data.get('tax_amount')
#             penalty_amount = data.get('penalty_amount', 0)
#             discount_amount = data.get('discount_amount', 0)
#             notes = data.get('notes', '')
            
#             # Validate required fields
#             if not all([property_id, billing_cycle_id, tax_amount]):
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Property, billing cycle, and tax amount are required'
#                 }, status=400)
            
#             property_obj = Property.objects.get(id=property_id)
#             billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
#             # Generate unique bill number
#             bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            
#             # Calculate total amount
#             total_amount = float(tax_amount) + float(penalty_amount) - float(discount_amount)
            
#             # Create bill
#             bill = Bill.objects.create(
#                 bill_number=bill_number,
#                 property=property_obj,
#                 billing_cycle=billing_cycle,
#                 tax_amount=tax_amount,
#                 penalty_amount=penalty_amount,
#                 discount_amount=discount_amount,
#                 total_amount=total_amount,
#                 status='generated',
#                 due_date=billing_cycle.due_date,
#                 created_by=request.user
#             )
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f'Bill {bill_number} generated successfully',
#                 'bill_id': bill.id,
#                 'bill_number': bill_number
#             })
            
#     except Property.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Property not found'
#         }, status=404)
#     except BillingCycle.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Billing cycle not found'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': f'Error generating bill: {str(e)}'
#         }, status=500)

# Update your generate_bill function to include payment reference

# @csrf_exempt
# @require_http_methods(["POST"])
# def generate_bill(request):
#     """Generate a new bill with payment integration"""
#     try:
#         with transaction.atomic():
#             data = json.loads(request.body)
            
#             property_id = data.get('property_id')
#             billing_cycle_id = data.get('billing_cycle_id')
#             tax_amount = data.get('tax_amount')
#             penalty_amount = data.get('penalty_amount', 0)
#             discount_amount = data.get('discount_amount', 0)
#             notes = data.get('notes', '')
            
#             # Validate required fields
#             if not all([property_id, billing_cycle_id, tax_amount]):
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Property, billing cycle, and tax amount are required'
#                 }, status=400)
            
#             property_obj = Property.objects.get(id=property_id)
#             billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
#             # Generate unique bill number
#             bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            
#             # Calculate total amount
#             total_amount = float(tax_amount) + float(penalty_amount) - float(discount_amount)
            
#             # Create bill
#             bill = Bill.objects.create(
#                 bill_number=bill_number,
#                 property=property_obj,
#                 billing_cycle=billing_cycle,
#                 tax_amount=tax_amount,
#                 penalty_amount=penalty_amount,
#                 discount_amount=discount_amount,
#                 total_amount=total_amount,
#                 status='generated',
#                 due_date=billing_cycle.due_date,
#                 created_by=request.user
#             )
            
#             # Generate payment links for different channels
#             host = request.get_host()
#             scheme = request.scheme
            
#             payment_links = {
#                 'web': f"https://collections.kowri.app/130/{bill_number}",
#                 'ussd': f"*227*130*{bill_number}#",
#                 'qr_code': f"{scheme}://{host}/api/payments/qr/{bill_number}",
#                 'direct_link': f"{scheme}://{host}/pay/bill/{bill_number}"
#             }
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f'Bill {bill_number} generated successfully',
#                 'bill_id': bill.id,
#                 'bill_number': bill_number,
#                 'payment_links': payment_links
#             })
            
#     except Property.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Property not found'
#         }, status=404)
#     except BillingCycle.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Billing cycle not found'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': f'Error generating bill: {str(e)}'
#         }, status=500)
    




@csrf_exempt
@require_http_methods(["POST"])
def update_bill(request, bill_id):
    """Update an existing bill"""
    try:
        with transaction.atomic():
            bill = Bill.objects.get(id=bill_id)
            data = json.loads(request.body)
            
            # Only allow updates to certain fields
            if 'penalty_amount' in data:
                bill.penalty_amount = data['penalty_amount']
            if 'discount_amount' in data:
                bill.discount_amount = data['discount_amount']
            if 'status' in data:
                bill.status = data['status']
            if 'notes' in data:
                bill.notes = data['notes']
            
            # Recalculate total amount
            bill.total_amount = bill.tax_amount + bill.penalty_amount - bill.discount_amount
            bill.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Bill {bill.bill_number} updated successfully'
            })
            
    except Bill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bill not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error updating bill: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_bill(request, bill_id):
    """Delete a bill"""
    try:
        bill = Bill.objects.get(id=bill_id)
        bill_number = bill.bill_number
        bill.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Bill {bill_number} deleted successfully'
        })
        
    except Bill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bill not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error deleting bill: {str(e)}'
        }, status=500)

def get_bill_details(request, bill_id):
    """Get detailed information about a specific bill"""
    try:
        bill = Bill.objects.select_related(
            'property', 
            'billing_cycle', 
            'created_by'
        ).prefetch_related('property__owners').get(id=bill_id)
        
        primary_owner = bill.property.owners.filter(is_primary_owner=True).first()
        
        bill_data = {
            'id': bill.id,
            'bill_number': bill.bill_number,
            'property': {
                'id': bill.property.id,
                'property_id': bill.property.property_id,
                'address': bill.property.address,
                'zone': bill.property.zone.name,
                'property_type': bill.property.property_type.name,
                'assessed_value': str(bill.property.assessed_value),
                'market_value': str(bill.property.market_value)
            },
            'owner': {
                'name': primary_owner.owner_name if primary_owner else 'N/A',
                'type': primary_owner.owner_type if primary_owner else 'N/A',
                'phone': primary_owner.phone_number if primary_owner else 'N/A'
            },
            'billing_cycle': {
                'name': bill.billing_cycle.name if bill.billing_cycle else 'N/A',
                'cycle_type': bill.billing_cycle.cycle_type if bill.billing_cycle else 'N/A',
                'start_date': bill.billing_cycle.start_date.strftime('%Y-%m-%d') if bill.billing_cycle else 'N/A',
                'end_date': bill.billing_cycle.end_date.strftime('%Y-%m-%d') if bill.billing_cycle else 'N/A',
                'due_date': bill.billing_cycle.due_date.strftime('%Y-%m-%d') if bill.billing_cycle else 'N/A'
            },
            'amounts': {
                'tax_amount': str(bill.tax_amount),
                'penalty_amount': str(bill.penalty_amount),
                'discount_amount': str(bill.discount_amount),
                'total_amount': str(bill.total_amount)
            },
            'status': bill.status,
            'generated_date': bill.generated_date.strftime('%Y-%m-%d %H:%M:%S'),
            'due_date': bill.due_date.strftime('%Y-%m-%d'),
            'created_by': bill.created_by.get_full_name() or bill.created_by.username
        }
        
        return JsonResponse({
            'success': True,
            'bill': bill_data
        })
        
    except Bill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bill not found'
        }, status=404)
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'error': f'Error fetching bill details: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def bulk_generate_bills(request):
    """Generate bills for multiple properties"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            property_ids = data.get('property_ids', [])
            billing_cycle_id = data.get('billing_cycle_id')
            
            if not property_ids or not billing_cycle_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Property IDs and billing cycle are required'
                }, status=400)
            
            billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            generated_bills = []
            errors = []
            
            for property_id in property_ids:
                try:
                    property_obj = Property.objects.get(id=property_id)
                    
                    # Calculate tax amount
                    current_date = datetime.now().date()
                    tax_rate = TaxRate.objects.filter(
                        zone=property_obj.zone,
                        property_type=property_obj.property_type,
                        effective_from__lte=current_date,
                        effective_to__gte=current_date
                    ).first()
                    
                    if not tax_rate:
                        errors.append(f'No tax rate found for {property_obj.property_id}')
                        continue
                    
                    tax_amount = property_obj.assessed_value * (tax_rate.rate / 100)
                    
                    # Generate bill number
                    bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
                    
                    # Create bill
                    bill = Bill.objects.create(
                        bill_number=bill_number,
                        property=property_obj,
                        billing_cycle=billing_cycle,
                        tax_amount=tax_amount,
                        penalty_amount=0,
                        discount_amount=0,
                        total_amount=tax_amount,
                        status='generated',
                        due_date=billing_cycle.due_date,
                        created_by=request.user
                    )
                    
                    generated_bills.append(bill_number)
                    
                except Property.DoesNotExist:
                    errors.append(f'Property {property_id} not found')
                except Exception as e:
                    errors.append(f'Error generating bill for property {property_id}: {str(e)}')
            
            return JsonResponse({
                'success': True,
                'message': f'Generated {len(generated_bills)} bills successfully',
                'generated_bills': generated_bills,
                'errors': errors
            })
            
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error in bulk bill generation: {str(e)}'
        }, status=500)



def bop_easy_collectible_list(request):
    """Display BopsBills in the bopbill.html template"""
    # Get billing year from request, default to current year
    from django.utils import timezone
    from django.http import HttpResponse
    try:
        billing_year = request.GET.get('billing_year', timezone.now().year)
        block = request.GET.get('block', '').strip()
        division = request.GET.get('division', '').strip()
        business_ids = request.GET.get('business_ids', '')  # Comma-separated IDs
        bill_id = request.GET.get('bill_id', '').strip()  # Single bill ID for viewing/downloading
        download = request.GET.get('download', '').strip()  # Download flag
        
        try:
            billing_year = int(billing_year)
        except (ValueError, TypeError):
            billing_year = timezone.now().year
        
        # If bill_id is provided, show only that bill
        if bill_id:
            try:
                bill_id_int = int(bill_id)
                bop_easy_collectibles = BopsBills.objects.filter(
                    id=bill_id_int,
                    is_deleted=False
                ).select_related('business')
            except (ValueError, TypeError):
                bop_easy_collectibles = BopsBills.objects.none()
        else:
            # Start with base queryset
            bop_easy_collectibles = BopsBills.objects.filter(
                billing_year=billing_year,
                is_deleted=False
            ).select_related('business')
            
            # Apply filters only if values are provided
            if block:
                bop_easy_collectibles = bop_easy_collectibles.filter(business__block=block)
            
            if division:
                bop_easy_collectibles = bop_easy_collectibles.filter(business__division=division)
            
            # Filter by business IDs if provided
            if business_ids:
                try:
                    business_id_list = [int(id.strip()) for id in business_ids.split(',') if id.strip()]
                    if business_id_list:
                        bop_easy_collectibles = bop_easy_collectibles.filter(business__id__in=business_id_list)
                except (ValueError, TypeError):
                    pass
        
        # Order by bill number
        bop_easy_collectibles = bop_easy_collectibles.order_by('bill_number')
        
        # If download flag is set, return PDF response
        if download:
            # The bopbill.html template has its own download functionality via JavaScript
            # So we just render the page and let the JavaScript handle the download
            return render(request, 'core/main/billing/newbop.html', {
                'bop_easy_collectibles': bop_easy_collectibles,
                'billing_year': billing_year,
                'auto_download': True  # Flag to trigger auto-download
            })
        
        return render(request, 'core/main/billing/newbop.html', {
            'bop_easy_collectibles': bop_easy_collectibles,
            'billing_year': billing_year
        })
    except Exception as e:
        # Return empty list if there's an error
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error loading bills: {error_trace}")
        from django.utils import timezone
        return render(request, 'core/main/billing/bopbill.html', {
            'bop_easy_collectibles': [],
            'billing_year': timezone.now().year,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def generate_bops_bills(request):
    """Generate BopsBills for selected businesses and billing year"""
    try:
        # Log request for debugging
        print(f"Bill generation request body: {request.body}")
        print(f"Request method: {request.method}")
        print(f"Content type: {request.content_type}")
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON data: {str(e)}'
            }, status=400)
        
        # Extract data from request
        business_ids = data.get('business_ids', [])
        billing_year = data.get('billing_year')
        tax_amount = data.get('tax_amount', 0)
        penalty_amount = data.get('penalty_amount', 0)
        discount_amount = data.get('discount_amount', 0)
        due_date_str = data.get('due_date')
        notes = data.get('notes', '')
        
        # Validate required fields
        if not business_ids or not isinstance(business_ids, list):
            return JsonResponse({
                'success': False,
                'error': 'business_ids is required and must be a list'
            }, status=400)
        
        if not billing_year:
            return JsonResponse({
                'success': False,
                'error': 'billing_year is required'
            }, status=400)
        
        try:
            billing_year = int(billing_year)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'billing_year must be a valid integer'
            }, status=400)
        
        # Parse due_date
        from datetime import timedelta
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid due_date format. Expected YYYY-MM-DD'
                }, status=400)
        else:
            due_date = datetime.now().date() + timedelta(days=30)
        
        # Calculate total amount
        total_amount = float(tax_amount) - float(discount_amount) + float(penalty_amount)
        
        generated_bills = []
        errors = []
        
        # Process each business in its own transaction to avoid transaction abort issues
        for business_id in business_ids:
            try:
                # Use a savepoint for each business so one failure doesn't abort the whole transaction
                with transaction.atomic():
                    try:
                        business = Bops.objects.get(id=business_id, is_deleted=False)
                    except Bops.DoesNotExist:
                        errors.append(f"Business with ID {business_id} not found")
                        continue
                    except Exception as e:
                        errors.append(f"Error fetching business ID {business_id}: {str(e)}")
                        continue
                    
                    # Check if bill already exists for this business and year
                    try:
                        existing_bill = BopsBills.objects.filter(
                            business=business,
                            billing_year=billing_year,
                            is_deleted=False
                        ).exclude(status='cancelled').first()
                        
                        if existing_bill:
                            # If a bill already exists, don't create a new one.
                            # Instead, treat it as a "read" of the existing record and include it in the response.
                            generated_bills.append({
                                'id': existing_bill.id,
                                'bill_number': existing_bill.bill_number,
                                'business_name': business.business_name,
                                'account_number': business.account_number,
                                'total_amount': str(existing_bill.total_amount),
                                'existing': True
                            })
                            continue
                    except Exception as e:
                        errors.append(f"Error checking existing bill for {business.business_name}: {str(e)}")
                        continue
                    
                    # Use flat_rate from business if tax_amount not provided or is 0
                    try:
                        if tax_amount and float(tax_amount) > 0:
                            bill_tax_amount = float(tax_amount)
                        else:
                            bill_tax_amount = float(business.flat_rate) if business.flat_rate else 0
                        
                        bill_total_amount = bill_tax_amount - float(discount_amount) + float(penalty_amount)
                        
                        # Validate total amount is not negative
                        if bill_total_amount < 0:
                            errors.append(f"Total amount cannot be negative for {business.business_name}. Tax: {bill_tax_amount}, Discount: {discount_amount}, Penalty: {penalty_amount}")
                            continue
                    except (ValueError, TypeError) as e:
                        errors.append(f"Error calculating amounts for {business.business_name}: {str(e)}")
                        continue
                    
                    # Create the bill (bill_number will be auto-generated)
                    # Note: Let exceptions propagate so transaction.atomic() can rollback properly
                    bill = BopsBills.objects.create(
                        business=business,
                        billing_year=billing_year,
                        tax_amount=bill_tax_amount,
                        penalty_amount=float(penalty_amount),
                        discount_amount=float(discount_amount),
                        total_amount=bill_total_amount,
                        due_date=due_date,
                        status='generated',
                        notes=notes,
                        added_by=request.user if request.user.is_authenticated else None
                    )
                    
                    generated_bills.append({
                        'id': bill.id,
                        'bill_number': bill.bill_number,
                        'business_name': business.business_name,
                        'account_number': business.account_number,
                        'total_amount': str(bill.total_amount)
                    })
                        
            except Bops.DoesNotExist:
                errors.append(f"Business with ID {business_id} not found")
            except Exception as e:
                import traceback
                from django.db import DatabaseError, IntegrityError
                error_details = traceback.format_exc()
                print(f"Error processing business ID {business_id}: {error_details}")
                
                # Format error message based on error type
                if isinstance(e, IntegrityError):
                    error_msg = f"Database constraint violation for business ID {business_id}: {str(e)}"
                elif isinstance(e, DatabaseError):
                    error_msg = f"Database error for business ID {business_id}: {str(e)}"
                else:
                    error_msg = f"Error processing business ID {business_id}: {str(e)}"
                
                errors.append(error_msg)
                # Transaction already rolled back automatically
                continue
        
        if generated_bills:
            # At least one bill was processed (new or existing)
            return JsonResponse({
                'success': True,
                'message': f'Successfully processed {len(generated_bills)} bill(s)',
                'bills': generated_bills,
                'errors': errors if errors else None
            })
        else:
            # No bills were processed at all
            return JsonResponse({
                'success': False,
                'error': 'No bills were generated',
                'errors': errors
            }, status=400)
            
    except json.JSONDecodeError as je:
        return JsonResponse({
            'success': False,
            'error': f'Invalid JSON data: {str(je)}'
        }, status=400)
    except ValueError as ve:
        return JsonResponse({
            'success': False,
            'error': f'Invalid data format: {str(ve)}'
        }, status=400)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error generating bills: {error_trace}")
        return JsonResponse({
            'success': False,
            'error': f'Error generating bills: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_bops_list(request):
    """Get all Bops for dropdown"""
    try:
        search = request.GET.get('search', '').strip()
        
        # Get all Bops (not deleted)
        bops = Bops.objects.filter(is_deleted=False)
        
        # Apply search filter if provided
        # Now also searchable by block and division
        if search:
            bops = bops.filter(
                Q(account_number__icontains=search) |
                Q(business_name__icontains=search) |
                Q(owner_name__icontains=search) |
                Q(location__icontains=search) |
                Q(block__icontains=search) |
                Q(division__icontains=search)
            )
        
        # Limit results for performance (can be adjusted)
        bops = bops
        
        bops_list = []
        for bop in bops:
            # Get business_name - handle both None and empty string
            business_name = bop.business_name
            if not business_name or business_name.strip() == '':
                business_name = 'Unnamed Business'
            
            account_number = bop.account_number or 'N/A'
            
            # Debug first few items
            if len(bops_list) < 3:
                print(f"Bop {bop.id}: business_name='{bop.business_name}', account_number='{account_number}'")
            
            bops_list.append({
                'id': bop.id,
                'account_number': account_number,
                'business_name': business_name,
                'owner_name': bop.owner_name or '',
                'location': bop.location or '',
                'block': getattr(bop, 'block', '') or '',
                'division': getattr(bop, 'division', '') or '',
                'display_text': f"{account_number} - {business_name}"
            })
        
        # Debug response
        if bops_list:
            print(f"Returning {len(bops_list)} bops. First item: {bops_list[0]}")
        
        return JsonResponse({
            'success': True,
            'bops': bops_list,
            'total': len(bops_list)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error loading businesses: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_billing_years(request):
    """Get unique billing years from BopsBills"""
    try:
        from django.utils import timezone
        current_year = timezone.now().year
        next_year = current_year + 1
        
        # Try to get distinct billing years from BopsBills (not deleted)
        try:
            years = BopsBills.objects.filter(
                is_deleted=False
            ).values_list('billing_year', flat=True).distinct().order_by('-billing_year')
            
            years_list = list(years)
        except Exception:
            # If table doesn't exist or query fails, return just current and next year
            years_list = []
        
        # Always include current year and next year if not already present
        if current_year not in years_list:
            years_list.insert(0, current_year)
        if next_year not in years_list:
            years_list.insert(0, next_year)
        
        # Sort descending and remove duplicates
        years_list = sorted(set(years_list), reverse=True)
        
        return JsonResponse({
            'success': True,
            'years': years_list
        })
    except Exception as e:
        # Fallback: return at least current and next year
        from django.utils import timezone
        current_year = timezone.now().year
        return JsonResponse({
            'success': True,
            'years': [current_year + 1, current_year]
        })


@require_http_methods(["GET"])
def get_bops_blocks(request):
    """Get distinct blocks from BopsBills (via related businesses) for populating blockSelect."""
    try:
        # Get distinct non-empty blocks from businesses that have bills
        blocks = (
            Bops.objects.filter(is_deleted=False).order_by('block')
            
            .values_list('block', flat=True)
            .distinct()
        )

        # Clean and sort the list (remove None/empty)
        blocks_list = sorted(
            {b.strip() for b in blocks if b and str(b).strip() != ''}
        )

        return JsonResponse({
            'success': True,
            'blocks': blocks_list,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error loading blocks: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_bops_divisions(request):
    """Get distinct divisions from Bops. Optionally filter by block."""
    try:
        block = request.GET.get('block', '').strip()

        # Base queryset: only businesses with a non-empty division
        qs = Bops.objects.filter(is_deleted=False).exclude(division__isnull=True).exclude(division__exact='')

        # If a block is provided, filter by it
        if block:
            qs = qs.filter(block=block)

        divisions = qs.values_list('division', flat=True).distinct()

        divisions_list = sorted(
            {d.strip() for d in divisions if d and str(d).strip() != ''}
        )

        return JsonResponse({
            'success': True,
            'divisions': divisions_list,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error loading divisions: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_bops_blocks_by_division(request):
    """Get distinct blocks for a given division from Bops."""
    try:
        division = request.GET.get('division', '').strip()

        # Base queryset: only businesses with a non-empty block
        qs = Bops.objects.filter(is_deleted=False).exclude(block__isnull=True).exclude(block__exact='')

        # If a division is provided, filter by it (case-insensitive)
        if division:
            qs = qs.filter(division__iexact=division)

        blocks = qs.values_list('block', flat=True).distinct()

        blocks_list = sorted(
            {b.strip() for b in blocks if b and str(b).strip() != ''}
        )

        return JsonResponse({
            'success': True,
            'blocks': blocks_list,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error loading blocks: {str(e)}'
        }, status=500)


def bops_bills_list_page(request):
    """Render the BopsBills list page"""
    context = {
        'page_title': 'BOP Bills Management',
        'active_menu': 'bops_bills'
    }
    return render(request, 'core/main/billing/bops-bills-list.html', context)


def bops_bill_receipt(request, bill_id):
    """Render the BOP bill receipt (newbop.html) for a single bill by ID."""
    bill = get_object_or_404(
        BopsBills.objects.filter(is_deleted=False).select_related('business'),
        id=bill_id
    )
    return render(request, 'core/main/billing/newbop.html', {
        'bop_easy_collectibles': [bill],
        'billing_year': bill.billing_year,
    })


@require_http_methods(["GET"])
def get_bops_bills_list(request):
    """Get all BopsBills for DataTable"""
    try:
        # Get pagination parameters from DataTables
        draw = int(request.GET.get('draw', 1))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '')
        
        # Base queryset
        bills = BopsBills.objects.filter(is_deleted=False).select_related('business')
        
        # Apply search filter
        if search_value:
            bills = bills.filter(
                Q(bill_number__icontains=search_value) |
                Q(business__business_name__icontains=search_value) |
                Q(business__account_number__icontains=search_value) |
                Q(business__owner_name__icontains=search_value) |
                Q(status__icontains=search_value)
            )
        
        # Get total count
        total_records = bills.count()
        
        # Apply ordering
        order_column = int(request.GET.get('order[0][column]', 0))
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        # Map column index to field name (matching frontend column order)
        column_mapping = {
            0: 'id',  # Hidden column
            1: 'bill_number',
            2: 'business__business_name',
            3: 'business__account_number',
            4: 'business__owner_name',
            5: 'billing_year',
            6: 'tax_amount',
            7: 'penalty_amount',
            8: 'discount_amount',
            9: 'total_amount',
            10: 'status',
            11: 'generated_date',
            12: 'due_date'
            # Column 13 is Actions (not sortable)
        }
        
        # Apply ordering
        order_field = column_mapping.get(order_column, 'id')
        if order_field:
            if order_dir == 'desc':
                order_field = f'-{order_field}'
            bills = bills.order_by(order_field)
        else:
            bills = bills.order_by('-id')  # Default ordering
        
        # For client-side pagination, return all data
        # DataTables will handle pagination, sorting, and filtering on the client side
        all_bills = list(bills)
        
        # Prepare data for DataTables
        data = []
        for bill in all_bills:
            data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'business_name': bill.business.business_name or '',
                'account_number': bill.business.account_number or '',
                'owner_name': bill.business.owner_name or '',
                'billing_year': bill.billing_year,
                'tax_amount': str(bill.tax_amount),
                'penalty_amount': str(bill.penalty_amount),
                'discount_amount': str(bill.discount_amount),
                'total_amount': str(bill.total_amount),
                'status': bill.status,
                'generated_date': bill.generated_date.strftime('%Y-%m-%d %H:%M') if bill.generated_date else '',
                'due_date': bill.due_date.strftime('%Y-%m-%d') if bill.due_date else '',
                'business_id': bill.business.id
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error fetching BopsBills: {error_trace}")
        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerate_bops_bill(request, bill_id):
    """Regenerate a specific BopsBill"""
    try:
        bill = BopsBills.objects.get(id=bill_id, is_deleted=False)
        
        # Check if bill already exists for this business and year
        existing_bill = BopsBills.objects.filter(
            business=bill.business,
            billing_year=bill.billing_year,
            is_deleted=False
        ).exclude(id=bill_id).exclude(status='cancelled').first()
        
        if existing_bill:
            return JsonResponse({
                'success': False,
                'error': f'Bill already exists for {bill.business.business_name} for year {bill.billing_year}. Bill: {existing_bill.bill_number}'
            }, status=400)
        
        # Update the bill (this will trigger bill_number regeneration if needed)
        bill.status = 'generated'
        bill.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Bill {bill.bill_number} regenerated successfully',
            'bill_number': bill.bill_number
        })
    except BopsBills.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bill not found'
        }, status=404)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error regenerating bill: {error_trace}")
        return JsonResponse({
            'success': False,
            'error': f'Error regenerating bill: {str(e)}'
        }, status=500)




# import urllib.parse
# import requests
# from django.http import HttpRequest
# def sendsmsView(contact,messagebody,sender):
# 	message = urllib.parse.quote_plus(messagebody)
# 	if not sender :
# 		sender ="COCOAREHAB"
# 	send = 'https://api.smsonlinegh.com/v4/message/sms/send?key=cc37ca2903ecf3cf5d6ea90026d45a20b12dd20853c099839be7c68549f4a322&text='+message+'&type=0&sender='+sender+'&to='+contact

# 	return requests.get(send)

# @csrf_exempt
# @require_http_methods(["POST"])
# def send_bops_bill_message(request, bill_id):
#     """Send message/notification for a BopsBill"""
#     try:
#         bill = BopsBills.objects.get(id=bill_id, is_deleted=False)
#         contact = bill.business.phone_number
#         host = request.get_host()
#         messagebody = f"Your BOP bill for {bill.billing_year} is due on {bill.due_date}. Please pay it online at {host}/bopeasycollectible/?bill_id={bill.id}"
#         sender = "COCOAREHAB"
#         # Update bill status to 'sent' and set sent_date
#         bill.status = 'sent'

      
#         bill.sent_date = timezone.now()
#         bill.save()
        
#         # TODO: Implement actual message sending (SMS, Email, etc.)
#         # For now, just update the status
#         asd = sendsmsView(contact,messagebody,sender)
#         print(asd)
        
#         return JsonResponse({
#             'success': True,
#             'message': f'Message sent for bill {bill.bill_number}',
#             'bill_number': bill.bill_number
#         })
#     except BopsBills.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Bill not found'
#         }, status=404)
#     except Exception as e:
#         import traceback
#         error_trace = traceback.format_exc()
#         print(f"Error sending message: {error_trace}")
#         return JsonResponse({
#             'success': False,
#             'error': f'Error sending message: {str(e)}'
#         }, status=500)




import urllib.parse
import requests
from django.http import HttpRequest
from django.utils import timezone
import json
from datetime import datetime

def send_sms(contact, message, sender="COCOAREHAB"):
    """Send SMS using SMSOnlineGH API"""
    try:
        encoded_message = urllib.parse.quote_plus(message)
        api_key = "cc37ca2903ecf3cf5d6ea90026d45a20b12dd20853c099839be7c68549f4a322"
        
        url = f'https://api.smsonlinegh.com/v4/message/sms/send?key={api_key}&text={encoded_message}&type=0&sender={sender}&to={contact}'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Log successful send
        print(f"SMS sent to {contact}: {response.status_code}")
        return True, response.json() if response.text else {}
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending SMS: {str(e)}")
        return False, str(e)
    except Exception as e:
        print(f"Unexpected error sending SMS: {str(e)}")
        return False, str(e)

def get_payment_message_template(bill, payment_links, recipient_name=""):
    """Generate a nice SMS message template for bill payment"""
    
    # Format amounts with commas for better readability
    formatted_amount = f"GH₵{bill.total_amount:,.2f}"
    formatted_due_date = bill.due_date.strftime('%d %B, %Y') if bill.due_date else "N/A"
    
    # Personalize if we have recipient name
    greeting = f"Dear {recipient_name},\n" if recipient_name else ""
    
    # Main message template
    message = f"""{greeting}Your property tax bill ({bill.bill_number}) of {formatted_amount} is ready.

🏠 Property: {bill.property.property_name if hasattr(bill.property, 'property_name') else bill.property.address}
📅 Due Date: {formatted_due_date}

💳 Quick Payment Options:
• Web: {payment_links['web']}
• Mobile Money: Dial {payment_links['ussd']}
• Scan QR: {payment_links['qr_code']}

Thank you for your prompt payment.
COCOAREHAB Revenue Collection"""

    return message

def get_bops_bill_message_template(bill, host, recipient_name=""):
    """Generate message template for BopsBill"""
    
    formatted_amount = f"GH₵{bill.amount_due:,.2f}" if hasattr(bill, 'amount_due') else "N/A"
    formatted_due_date = bill.due_date.strftime('%d %B, %Y') if bill.due_date else "N/A"
    
    greeting = f"Dear {recipient_name},\n" if recipient_name else ""
    
    message = f"""{greeting}Your BOP bill for {bill.billing_year} of {formatted_amount} is now available.

📋 Bill Reference: {bill.bill_number}
📅 Due Date: {formatted_due_date}

🔗 Pay online: https://collections.kowri.app/130/{bill.bill_number}
📱 USSD: *227*130*{bill.bill_number}#

Please pay before the due date to avoid penalties.

COCOAREHAB Revenue Collection"""

    return message


# Update the sendsmsView function or create a new one

def get_tracked_payment_link(bill_type, bill_number, link_type='web'):
    """Generate a tracked payment link"""
    base_url = settings.BASE_URL or 'https://yourdomain.com'
    return f"{base_url}/pay/l/{bill_type}/{bill_number}/{link_type}/"



# Update your send_bops_bill_message function
def send_bops_bill_message(request, bill_id):
    """Send message/notification for a BopsBill with tracked links"""
    try:
        print(f"Sending message for bill ID: {bill_id}")
        bill = BopsBills.objects.get(id=bill_id, is_deleted=False)
        contact = bill.business.phone_number
        host = request.get_host()
        scheme = request.scheme
        
        # Generate tracked payment links
        tracked_web_link = get_tracked_payment_link('business', bill.bill_number, 'web')
        tracked_ussd = f"*227*130*{bill.bill_number}#"  # USSD can't be tracked directly
        
        # Create nice message with tracked links
        messagebody = f"""Dear {bill.business.business_name},

Your BOP bill for {bill.billing_year} of GH₵{bill.total_amount:,.2f} is due on {bill.due_date.strftime('%d %B, %Y')}.

🔗 Quick Pay Online: {tracked_web_link}
📱 USSD: {tracked_ussd}

Please pay before due date to avoid penalties.

COCOAREHAB Revenue Collection"""
        
        sender = "COCOAREHAB"
        
        # Update bill status
        bill.status = 'sent'
        bill.sent_date = timezone.now()
        bill.save()
        
        # Send SMS
        response = send_sms(contact, messagebody, sender)
        
        return JsonResponse({
            'success': True,
            'message': f'Message sent for bill {bill.bill_number}',
            'bill_number': bill.bill_number,
            'tracked_link': tracked_web_link
        })
        
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# @csrf_exempt
# @require_http_methods(["POST"])
# def send_bops_bill_message(request, bill_id):
#     """Send message/notification for a BopsBill"""
#     try:
#         bill = BopsBills.objects.get(id=bill_id, is_deleted=False)
#         contact = bill.business.phone_number
#         business_name = bill.business.business_name if hasattr(bill.business, 'business_name') else ""
        
#         host = request.get_host()
#         message = get_bops_bill_message_template(bill, host, business_name)
#         sender = "COCOAREHAB"
        
#         # Update bill status
#         bill.status = 'sent'
#         bill.sent_date = timezone.now()
#         bill.save()
        
#         # Send SMS
#         success, response = send_sms(contact, message, sender)
        
#         if success:
#             return JsonResponse({
#                 'success': True,
#                 'message': f'Message sent successfully for bill {bill.bill_number}',
#                 'bill_number': bill.bill_number,
#                 'sms_response': response
#             })
#         else:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'SMS sending failed: {response}',
#                 'bill_number': bill.bill_number
#             }, status=500)
            
#     except BopsBills.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Bill not found'
#         }, status=404)
#     except Exception as e:
#         import traceback
#         error_trace = traceback.format_exc()
#         print(f"Error sending message: {error_trace}")
#         return JsonResponse({
#             'success': False,
#             'error': f'Error sending message: {str(e)}'
#         }, status=500)

# @csrf_exempt
# @require_http_methods(["POST"])
# def generate_bill(request):
#     """Generate a new bill with payment integration and SMS notification"""
#     try:
#         with transaction.atomic():
#             data = json.loads(request.body)
            
#             property_id = data.get('property_id')
#             billing_cycle_id = data.get('billing_cycle_id')
#             tax_amount = data.get('tax_amount')
#             penalty_amount = data.get('penalty_amount', 0)
#             discount_amount = data.get('discount_amount', 0)
#             notes = data.get('notes', '')
#             send_sms_notification = data.get('send_sms', True)  # Option to send SMS
            
#             # Validate required fields
#             if not all([property_id, billing_cycle_id, tax_amount]):
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Property, billing cycle, and tax amount are required'
#                 }, status=400)
            
#             property_obj = Property.objects.get(id=property_id)
#             billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
#             # Generate unique bill number
#             bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            
#             # Calculate total amount
#             total_amount = float(tax_amount) + float(penalty_amount) - float(discount_amount)
            
#             # Create bill
#             bill = Bill.objects.create(
#                 bill_number=bill_number,
#                 property=property_obj,
#                 billing_cycle=billing_cycle,
#                 tax_amount=tax_amount,
#                 penalty_amount=penalty_amount,
#                 discount_amount=discount_amount,
#                 total_amount=total_amount,
#                 status='generated',
#                 due_date=billing_cycle.due_date,
#                 created_by=request.user,
#                 notes=notes
#             )
            
#             # Generate payment links for different channels
#             host = request.get_host()
#             scheme = request.scheme
            
#             payment_links = {
#                 'web': f"https://collections.kowri.app/130/{bill_number}",
#                 'ussd': f"*227*130*{bill_number}#",
#                 'qr_code': f"{scheme}://{host}/api/payments/qr/{bill_number}",
#                 'direct_link': f"{scheme}://{host}/pay/bill/{bill_number}"
#             }
            
#             # Prepare response
#             response_data = {
#                 'success': True,
#                 'message': f'Bill {bill_number} generated successfully',
#                 'bill_id': bill.id,
#                 'bill_number': bill_number,
#                 'total_amount': total_amount,
#                 'payment_links': payment_links
#             }
            
#             # Send SMS notification if requested and property has contact info
#             if send_sms_notification and property_obj.contact_number:
#                 # Get property owner name if available
#                 owner_name = ""
#                 if hasattr(property_obj, 'owner') and property_obj.owner:
#                     owner_name = property_obj.owner.get_full_name() if hasattr(property_obj.owner, 'get_full_name') else str(property_obj.owner)
                
#                 # Generate nice message
#                 sms_message = get_payment_message_template(bill, payment_links, owner_name)
                
#                 # Send SMS
#                 sms_success, sms_response = send_sms(property_obj.contact_number, sms_message)
                
#                 # Add SMS status to response
#                 response_data['sms_notification'] = {
#                     'sent': sms_success,
#                     'to': property_obj.contact_number,
#                     'response': sms_response if sms_success else str(sms_response)
#                 }
                
#                 # If SMS was sent successfully, update bill status
#                 if sms_success:
#                     bill.status = 'notification_sent'
#                     bill.sent_date = timezone.now()
#                     bill.save()
#                     response_data['message'] = f'Bill {bill_number} generated and SMS notification sent'
            
#             return JsonResponse(response_data)
            
#     except Property.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Property not found'
#         }, status=404)
#     except BillingCycle.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Billing cycle not found'
#         }, status=404)
#     except json.JSONDecodeError:
#         return JsonResponse({
#             'success': False,
#             'error': 'Invalid JSON data'
#         }, status=400)
#     except Exception as e:
#         import traceback
#         error_trace = traceback.format_exc()
#         print(f"Error generating bill: {error_trace}")
#         return JsonResponse({
#             'success': False,
#             'error': f'Error generating bill: {str(e)}'
#         }, status=500)

# Optional: Add a separate endpoint to resend SMS for existing bills
@csrf_exempt
@require_http_methods(["POST"])
def resend_bill_sms(request, bill_id):
    """Resend SMS notification for an existing bill"""
    try:
        bill = Bill.objects.get(id=bill_id)
        
        if not bill.property.contact_number:
            return JsonResponse({
                'success': False,
                'error': 'Property has no contact number'
            }, status=400)
        
        # Generate payment links
        host = request.get_host()
        scheme = request.scheme
        bill_number = bill.bill_number
        
        payment_links = {
            'web': f"https://collections.kowri.app/130/{bill_number}",
            'ussd': f"*227*130*{bill_number}#",
            'qr_code': f"{scheme}://{host}/api/payments/qr/{bill_number}",
            'direct_link': f"{scheme}://{host}/pay/bill/{bill_number}"
        }
        
        # Get owner name
        owner_name = ""
        if hasattr(bill.property, 'owner') and bill.property.owner:
            owner_name = bill.property.owner.get_full_name() if hasattr(bill.property.owner, 'get_full_name') else str(bill.property.owner)
        
        # Generate message
        sms_message = get_payment_message_template(bill, payment_links, owner_name)
        
        # Send SMS
        success, response = send_sms(bill.property.contact_number, sms_message)
        
        if success:
            bill.sent_date = timezone.now()
            bill.save()
            
            return JsonResponse({
                'success': True,
                'message': f'SMS resent successfully for bill {bill.bill_number}',
                'sms_response': response
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'SMS sending failed: {response}'
            }, status=500)
            
    except Bill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Bill not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=500)
    








############################################################################################################################################################


# views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime
import json
import traceback
from weasyprint import HTML
import tempfile
import os

@csrf_exempt
@require_http_methods(["POST"])
def generate_bill(request):
    print("Received request to generate bill")
    """Generate a new bill with payment integration and SMS notification"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            
            property_id = data.get('property_id')
            billing_cycle_id = data.get('billing_cycle_id')
            tax_amount = data.get('tax_amount')
            penalty_amount = data.get('penalty_amount', 0)
            discount_amount = data.get('discount_amount', 0)
            notes = data.get('notes', '')
            send_sms_notification = data.get('send_sms', True)
            
            # Validate required fields
            if not all([property_id, billing_cycle_id, tax_amount]):
                return JsonResponse({
                    'success': False,
                    'error': 'Property, billing cycle, and tax amount are required'
                }, status=400)
            
            property_obj = Property.objects.select_related('owner').get(id=property_id)
            billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
            # Generate unique bill number
            bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            
            # Calculate total amount
            total_amount = float(tax_amount) + float(penalty_amount) - float(discount_amount)
            
            # Create bill
            bill = Bill.objects.create(
                bill_number=bill_number,
                property=property_obj,
                billing_cycle=billing_cycle,
                tax_amount=tax_amount,
                penalty_amount=penalty_amount,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status='generated',
                due_date=billing_cycle.due_date,
                created_by=request.user,
                notes=notes
            )
            
            # Generate payment links
            host = request.get_host()
            scheme = request.scheme
            
            payment_links = {
                'web': f"https://collections.kowri.app/130/{bill_number}",
                'ussd': f"*227*130*{bill_number}#",
                'qr_code': f"{scheme}://{host}/api/payments/qr/{bill_number}",
                'direct_link': f"{scheme}://{host}/pay/bill/{bill_number}"
            }
            
            response_data = {
                'success': True,
                'message': f'Bill {bill_number} generated successfully',
                'bill_id': bill.id,
                'bill_number': bill_number,
                'total_amount': total_amount,
                'payment_links': payment_links
            }
            
            # Send SMS notification if requested
            if send_sms_notification and property_obj.contact_number:
                owner_name = property_obj.owner.get_full_name() if property_obj.owner else ""
                sms_message = get_payment_message_template(bill, payment_links, owner_name)
                sms_success, sms_response = send_sms(property_obj.contact_number, sms_message)
                
                response_data['sms_notification'] = {
                    'sent': sms_success,
                    'to': property_obj.contact_number,
                    'response': sms_response if sms_success else str(sms_response)
                }
                
                if sms_success:
                    bill.status = 'notification_sent'
                    bill.sent_date = timezone.now()
                    bill.save()
                    response_data['message'] = f'Bill {bill_number} generated and SMS notification sent'
            
            return JsonResponse(response_data)
            
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Property not found'}, status=404)
    except BillingCycle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Billing cycle not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error generating bill: {error_trace}")
        return JsonResponse({'success': False, 'error': f'Error generating bill: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def view_bill(request, bill_number):
    """View a bill in HTML format"""
    try:
        bill = Bill.objects.select_related('property', 'property__owner', 'billing_cycle').get(bill_number=bill_number)
        
        # Prepare bill data for template
        bill_data = prepare_bill_data(bill)
        
        return render(request, 'billing/bill_template.html', bill_data)
        
    except Bill.DoesNotExist:
        return HttpResponse("Bill not found", status=404)


@require_http_methods(["GET"])
def download_bill_pdf(request, bill_number):
    """Download bill as PDF"""
    try:
        bill = Bill.objects.select_related('property', 'property__owner', 'billing_cycle').get(bill_number=bill_number)
        
        # Prepare bill data
        bill_data = prepare_bill_data(bill)
        
        # Render HTML template
        html_string = render_to_string('billing/bill_template.html', bill_data)
        
        # Generate PDF
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
        
        # Create response
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bill_{bill_number}.pdf"'
        
        return response
        
    except Bill.DoesNotExist:
        return HttpResponse("Bill not found", status=404)


def prepare_bill_data(bill):
    """Prepare bill data for template population"""
    property_obj = bill.property
    
    # Get owner information
    owner_name = ""
    owner_contact = ""
    if property_obj.owner:
        owner_name = property_obj.owner.get_full_name() if hasattr(property_obj.owner, 'get_full_name') else str(property_obj.owner)
        owner_contact = getattr(property_obj.owner, 'phone_number', '')
    
    # Format dates
    bill_date = bill.created_at.strftime('%d/%m/%Y') if bill.created_at else datetime.now().strftime('%d/%m/%Y')
    due_date = bill.due_date.strftime('%d/%m/%Y') if bill.due_date else ''
    
    # Format currency amounts
    def format_currency(amount):
        return f"GH₵ {float(amount):,.2f}"
    
    # Prepare data structure matching template fields
    return {
        'bill': bill,
        'property': property_obj,
        'bill_number': bill.bill_number,
        'bill_date': bill_date,
        'due_date': due_date,
        'owner_name': owner_name,
        'owner_contact': owner_contact,
        
        # Property details for template fields
        'serial_no': bill.bill_number.split('-')[-1] if '-' in bill.bill_number else bill.bill_number,
        'account_number': property_obj.property_id or property_obj.id,
        'suburb': property_obj.suburb or property_obj.location or '',
        'property_number': property_obj.property_number or property_obj.id,
        'property_address': property_obj.address or property_obj.location or '',
        'property_description': property_obj.description or '',
        
        # Amounts formatted
        'rateable_value': format_currency(property_obj.rateable_value or bill.tax_amount * 10),  # Example calculation
        'rate_impost': format_currency(bill.tax_amount),
        'rate_amount_charged': format_currency(bill.tax_amount),
        'arrears': format_currency(0),  # You can implement arrears calculation
        'payment': format_currency(0),  # No payment yet
        'adjustment': format_currency(bill.discount_amount),
        'total_amount': format_currency(bill.total_amount),
        'penalty_amount': format_currency(bill.penalty_amount),
        
        # Additional data
        'notes': bill.notes,
        'status': bill.get_status_display() if hasattr(bill, 'get_status_display') else bill.status,
        'billing_cycle': bill.billing_cycle.name if bill.billing_cycle else '',
    }


# Alternative: API endpoint that returns HTML for frontend to display
@csrf_exempt
@require_http_methods(["POST"])
def generate_and_render_bill(request):
    """Generate bill and return rendered HTML"""
    try:
        # First generate the bill using the existing logic
        data = json.loads(request.body)
        
        # Similar to generate_bill but instead of returning JSON, return HTML
        with transaction.atomic():
            property_id = data.get('property_id')
            billing_cycle_id = data.get('billing_cycle_id')
            tax_amount = data.get('tax_amount')
            penalty_amount = data.get('penalty_amount', 0)
            discount_amount = data.get('discount_amount', 0)
            notes = data.get('notes', '')
            
            property_obj = Property.objects.get(id=property_id)
            billing_cycle = BillingCycle.objects.get(id=billing_cycle_id)
            
            bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{Bill.objects.count() + 1:06d}"
            total_amount = float(tax_amount) + float(penalty_amount) - float(discount_amount)
            
            bill = Bill.objects.create(
                bill_number=bill_number,
                property=property_obj,
                billing_cycle=billing_cycle,
                tax_amount=tax_amount,
                penalty_amount=penalty_amount,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status='generated',
                due_date=billing_cycle.due_date,
                created_by=request.user,
                notes=notes
            )
            
            # Prepare data for template
            bill_data = prepare_bill_data(bill)
            
            # Render the template
            return render(request, 'billing/bill_template.html', bill_data)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)