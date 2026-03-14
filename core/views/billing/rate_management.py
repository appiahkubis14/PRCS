# views.py (add these to the existing billing views)

# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Q
import json
from datetime import datetime
from core.models import Property, PropertyType, TaxRate, Zone
def rate_management_page(request):
    """Render the rate management page"""
    context = {
        'page_title': 'Rate Management',
        'active_menu': 'rate_management'
    }
    return render(request, 'core/main/billing/rate-management.html', context)

def get_tax_rates(request):
    """Get all tax rates for DataTable"""
    try:
        # # Get pagination parameters from DataTables
        # draw = int(request.GET.get('draw', 1))
        # start = int(request.GET.get('start', 0))
        # length = int(request.GET.get('length', 10))
        # search_value = request.GET.get('search[value]', '')
        
        # Base queryset
        tax_rates = TaxRate.objects.select_related(
            'zone', 
            'property_type',
            'created_by'
        ).all()
        print(tax_rates)
        # Apply search filter
        # if search_value:
        #     tax_rates = tax_rates.filter(
        #         Q(zone__name__icontains=search_value) |
        #         Q(property_type__name__icontains=search_value) |
        #         Q(rate__icontains=search_value) |
        #         Q(description__icontains=search_value)
        #     )
        
        # Get total count
        total_records = tax_rates.count()
        
        # Apply ordering and pagination
        order_column = int(request.GET.get('order[0][column]', 0))
        order_dir = request.GET.get('order[0][dir]', 'asc')
        
        # Map column index to field name
        column_mapping = {
            0: 'id',
            1: 'zone__name',
            2: 'property_type__name',
            3: 'rate',
            4: 'effective_from',
            5: 'effective_to',
            6: 'created_at'
        }
        
        order_field = column_mapping.get(order_column, 'id')
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        
        tax_rates = tax_rates.order_by(order_field)
        
        # Prepare data for DataTables
        data = []
        for rate in tax_rates:
            data.append({
                'id': rate.id,
                'zone_name': rate.zone.name,
                'zone_id': rate.zone.id,
                'zone_type': rate.zone.zone_type,
                'property_type_name': rate.property_type.name,
                'property_type_id': rate.property_type.id,
                'rate': str(rate.rate),
                'effective_from': rate.effective_from.strftime('%Y-%m-%d'),
                'effective_to': rate.effective_to.strftime('%Y-%m-%d') if rate.effective_to else 'Indefinite',
                'description': rate.description,
                'is_active': rate.effective_to is None or rate.effective_to >= datetime.now().date(),
                'created_by': rate.created_by.get_full_name() or rate.created_by.username,
                'created_at': rate.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
            print(data)
        
        response = {
            
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        }
        
        return JsonResponse(response)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Error fetching tax rates: {str(e)}'
        }, status=500)

def get_zones_and_property_types(request):
    """Get zones and property types for dropdowns"""
    try:
        zones = Zone.objects.filter(is_active=True)
        property_types = PropertyType.objects.filter(is_active=True)
        
        zones_data = [{'id': zone.id, 'name': zone.name, 'zone_type': zone.zone_type} for zone in zones]
        property_types_data = [{'id': pt.id, 'name': pt.name, 'base_rate': str(pt.base_rate)} for pt in property_types]
        
        return JsonResponse({
            'success': True,
            'zones': zones_data,
            'property_types': property_types_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching data: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_tax_rate(request):
    """Create a new tax rate"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            
            zone_id = data.get('zone_id')
            property_type_id = data.get('property_type_id')
            rate = data.get('rate')
            effective_from = data.get('effective_from')
            effective_to = data.get('effective_to')
            description = data.get('description', '')
            
            # Validate required fields
            if not all([zone_id, property_type_id, rate, effective_from]):
                return JsonResponse({
                    'success': False,
                    'error': 'Zone, property type, rate, and effective from date are required'
                }, status=400)
            
            # Check if rate already exists for this zone and property type
            existing_rate = TaxRate.objects.filter(
                zone_id=zone_id,
                property_type_id=property_type_id,
                effective_from__lte=effective_from,
                effective_to__gte=effective_from
            ).first()
            
            if existing_rate:
                return JsonResponse({
                    'success': False,
                    'error': 'A tax rate already exists for this zone and property type during the specified period'
                }, status=400)
            
            # Create tax rate
            tax_rate = TaxRate.objects.create(
                zone_id=zone_id,
                property_type_id=property_type_id,
                rate=rate,
                effective_from=effective_from,
                effective_to=effective_to if effective_to else None,
                description=description,
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Tax rate created successfully for {tax_rate.zone.name} - {tax_rate.property_type.name}',
                'tax_rate_id': tax_rate.id
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
            'error': f'Error creating tax rate: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_tax_rate(request, rate_id):
    """Update an existing tax rate"""
    try:
        with transaction.atomic():
            tax_rate = TaxRate.objects.get(id=rate_id)
            data = json.loads(request.body)
            
            # Check if this rate is being referenced by any bills
            if tax_rate.bills.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot update tax rate that is being used by existing bills'
                }, status=400)
            
            # Update fields
            if 'rate' in data:
                tax_rate.rate = data['rate']
            if 'effective_from' in data:
                tax_rate.effective_from = data['effective_from']
            if 'effective_to' in data:
                tax_rate.effective_to = data['effective_to'] if data['effective_to'] else None
            if 'description' in data:
                tax_rate.description = data['description']
            
            tax_rate.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Tax rate updated successfully'
            })
            
    except TaxRate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Tax rate not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error updating tax rate: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_tax_rate(request, rate_id):
    """Delete a tax rate"""
    try:
        tax_rate = TaxRate.objects.get(id=rate_id)
        
        # Check if this rate is being referenced by any bills
        if tax_rate.bills.exists():
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete tax rate that is being used by existing bills'
            }, status=400)
        
        zone_name = tax_rate.zone.name
        property_type_name = tax_rate.property_type.name
        tax_rate.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Tax rate for {zone_name} - {property_type_name} deleted successfully'
        })
        
    except TaxRate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Tax rate not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error deleting tax rate: {str(e)}'
        }, status=500)

def get_tax_rate_history(request, zone_id, property_type_id):
    """Get tax rate history for a specific zone and property type"""
    try:
        tax_rates = TaxRate.objects.filter(
            zone_id=zone_id,
            property_type_id=property_type_id
        ).order_by('-effective_from')
        
        history_data = []
        for rate in tax_rates:
            history_data.append({
                'id': rate.id,
                'rate': str(rate.rate),
                'effective_from': rate.effective_from.strftime('%Y-%m-%d'),
                'effective_to': rate.effective_to.strftime('%Y-%m-%d') if rate.effective_to else 'Present',
                'description': rate.description,
                'created_by': rate.created_by.get_full_name() or rate.created_by.username,
                'created_at': rate.created_at.strftime('%Y-%m-%d')
            })
        
        return JsonResponse({
            'success': True,
            'history': history_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching tax rate history: {str(e)}'
        }, status=500)

def get_current_rates_report(request):
    """Get report of current active tax rates"""
    try:
        current_date = datetime.now().date()
        current_rates = TaxRate.objects.filter(
            effective_from__lte=current_date,
            effective_to__gte=current_date
        ).select_related('zone', 'property_type')
        
        report_data = []
        for rate in current_rates:
            report_data.append({
                'zone_name': rate.zone.name,
                'zone_type': rate.zone.zone_type,
                'property_type_name': rate.property_type.name,
                'rate': f"{rate.rate}%",
                'effective_from': rate.effective_from.strftime('%Y-%m-%d'),
                'effective_to': rate.effective_to.strftime('%Y-%m-%d') if rate.effective_to else 'Indefinite'
            })
        
        return JsonResponse({
            'success': True,
            'current_rates': report_data,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_rates': len(report_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error generating report: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def bulk_update_rates(request):
    """Bulk update tax rates for multiple zones or property types"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            updates = data.get('updates', [])
            effective_from = data.get('effective_from')
            effective_to = data.get('effective_to')
            description = data.get('description', 'Bulk update')
            
            if not updates or not effective_from:
                return JsonResponse({
                    'success': False,
                    'error': 'Updates and effective from date are required'
                }, status=400)
            
            created_count = 0
            errors = []
            
            for update in updates:
                try:
                    zone_id = update.get('zone_id')
                    property_type_id = update.get('property_type_id')
                    rate = update.get('rate')
                    
                    if not all([zone_id, property_type_id, rate]):
                        errors.append(f'Missing required fields for update: {update}')
                        continue
                    
                    # Check for existing overlapping rates
                    existing_rates = TaxRate.objects.filter(
                        zone_id=zone_id,
                        property_type_id=property_type_id,
                        effective_from__lte=effective_from,
                        effective_to__gte=effective_from
                    )
                    
                    if existing_rates.exists():
                        errors.append(f'Rate already exists for zone {zone_id} and property type {property_type_id}')
                        continue
                    
                    # Create new tax rate
                    TaxRate.objects.create(
                        zone_id=zone_id,
                        property_type_id=property_type_id,
                        rate=rate,
                        effective_from=effective_from,
                        effective_to=effective_to if effective_to else None,
                        description=description,
                        created_by=request.user
                    )
                    
                    created_count += 1
                    
                except Exception as e:
                    errors.append(f'Error creating rate for {update}: {str(e)}')
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully created {created_count} tax rates',
                'created_count': created_count,
                'errors': errors
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error in bulk update: {str(e)}'
        }, status=500)