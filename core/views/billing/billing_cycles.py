# views.py (add these to the existing billing views)

# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Q
import json
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from core.models import Bill, Property, BillingCycle, PropertyType, TaxRate, Zone



# views.py (add these to the existing billing views)
def billing_cycles_page(request):
    """Render the billing cycles management page"""
    context = {
        'page_title': 'Billing Cycles',
        'active_menu': 'billing_cycles'
    }
    return render(request, 'core/main/billing/billing-cycle.html', context)
def get_billing_cycles_list(request):
    print("get_billing_cycles_list")
    """Get all billing cycles for DataTable"""
    try:
        print("Fetching billing cycles...")
        
        # Base queryset - get all billing cycles
        billing_cycles = BillingCycle.objects.all()
        print(f"Found {billing_cycles.count()} billing cycles")
        
        # Get total count
        total_records = billing_cycles.count()
        print(f"Total records found: {total_records}")
        
        # Prepare data for DataTables
        data = []
        for cycle in billing_cycles:
            # Count bills in this cycle
            bill_count = cycle.bills.count()
            
            # Calculate days remaining until due date
            today = datetime.now().date()
            days_remaining = (cycle.due_date - today).days if cycle.due_date > today else 0
            
            cycle_data = {
                'id': cycle.id,
                'name': cycle.name,
                'cycle_type': cycle.cycle_type,
                'start_date': cycle.start_date.strftime('%Y-%m-%d'),
                'end_date': cycle.end_date.strftime('%Y-%m-%d'),
                'due_date': cycle.due_date.strftime('%Y-%m-%d'),
                'is_active': cycle.is_active,
                'bill_count': bill_count,
                'days_remaining': days_remaining,
                'description': cycle.description or '',
                'created_at': cycle.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            data.append(cycle_data)
            print(f"Added cycle: {cycle.name}")
        
        print(f"Total data prepared: {len(data)}")
        
        response = {
            'draw': 1,  # Required by DataTables
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        }
        
        return JsonResponse(response)
        
    except Exception as e:
        print(f"Error in get_billing_cycles_list: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'error': f'Error fetching billing cycles: {str(e)}'
        }, status=500)
    


@csrf_exempt
@require_http_methods(["POST"])
def create_billing_cycle(request):
    """Create a new billing cycle"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            
            name = data.get('name')
            cycle_type = data.get('cycle_type')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            due_date = data.get('due_date')
            description = data.get('description', '')
            
            # Validate required fields
            if not all([name, cycle_type, start_date, end_date, due_date]):
                return JsonResponse({
                    'success': False,
                    'error': 'All fields are required except description'
                }, status=400)
            
            # Validate dates
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
            
            if start_date_obj >= end_date_obj:
                return JsonResponse({
                    'success': False,
                    'error': 'Start date must be before end date'
                }, status=400)
            
            if due_date_obj < end_date_obj:
                return JsonResponse({
                    'success': False,
                    'error': 'Due date must be on or after end date'
                }, status=400)
            
            # Check for overlapping cycles of the same type
            overlapping_cycles = BillingCycle.objects.filter(
                cycle_type=cycle_type,
                start_date__lte=end_date_obj,
                end_date__gte=start_date_obj,
                is_active=True
            )
            
            if overlapping_cycles.exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Overlapping {cycle_type} billing cycle exists for this period'
                }, status=400)
            
            # Create billing cycle
            billing_cycle = BillingCycle.objects.create(
                name=name,
                cycle_type=cycle_type,
                start_date=start_date_obj,
                end_date=end_date_obj,
                due_date=due_date_obj,
                description=description,
                is_active=True
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Billing cycle "{name}" created successfully',
                'billing_cycle_id': billing_cycle.id
            })
            
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': 'Invalid date format. Use YYYY-MM-DD'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error creating billing cycle: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def update_billing_cycle(request, cycle_id):
    """Update an existing billing cycle"""
    try:
        with transaction.atomic():
            billing_cycle = BillingCycle.objects.get(id=cycle_id)
            data = json.loads(request.body)
            
            # Check if cycle has bills (restrict certain changes)
            has_bills = billing_cycle.bills.exists()
            
            # Update fields
            if 'name' in data:
                billing_cycle.name = data['name']
            
            if 'description' in data:
                billing_cycle.description = data['description']
            
            if 'is_active' in data:
                # Only allow deactivation if no bills exist
                if not data['is_active'] and has_bills:
                    return JsonResponse({
                        'success': False,
                        'error': 'Cannot deactivate billing cycle with existing bills'
                    }, status=400)
                billing_cycle.is_active = data['is_active']
            
            # Only allow date changes if no bills exist
            if not has_bills:
                if 'start_date' in data:
                    billing_cycle.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
                if 'end_date' in data:
                    billing_cycle.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
                if 'due_date' in data:
                    billing_cycle.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                
                # Validate dates if any were changed
                if any(key in data for key in ['start_date', 'end_date', 'due_date']):
                    if billing_cycle.start_date >= billing_cycle.end_date:
                        return JsonResponse({
                            'success': False,
                            'error': 'Start date must be before end date'
                        }, status=400)
                    
                    if billing_cycle.due_date < billing_cycle.end_date:
                        return JsonResponse({
                            'success': False,
                            'error': 'Due date must be on or after end date'
                        }, status=400)
            
            billing_cycle.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Billing cycle "{billing_cycle.name}" updated successfully'
            })
            
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': 'Invalid date format. Use YYYY-MM-DD'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error updating billing cycle: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_billing_cycle(request, cycle_id):
    """Delete a billing cycle"""
    try:
        billing_cycle = BillingCycle.objects.get(id=cycle_id)
        
        # Check if cycle has bills
        if billing_cycle.bills.exists():
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete billing cycle with existing bills'
            }, status=400)
        
        cycle_name = billing_cycle.name
        billing_cycle.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Billing cycle "{cycle_name}" deleted successfully'
        })
        
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error deleting billing cycle: {str(e)}'
        }, status=500)

def get_billing_cycle_details(request, cycle_id):
    """Get detailed information about a specific billing cycle"""
    try:
        billing_cycle = BillingCycle.objects.get(id=cycle_id)
        
        # Get bills in this cycle
        bills = billing_cycle.bills.select_related('property', 'created_by')
        bill_summary = {
            'total_bills': bills.count(),
            'draft_bills': bills.filter(status='draft').count(),
            'generated_bills': bills.filter(status='generated').count(),
            'sent_bills': bills.filter(status='sent').count(),
            'paid_bills': bills.filter(status='paid').count(),
            'overdue_bills': bills.filter(status='overdue').count(),
            'total_amount': sum(bill.total_amount for bill in bills),
            'collected_amount': sum(bill.total_amount for bill in bills.filter(status='paid'))
        }
        
        cycle_data = {
            'id': billing_cycle.id,
            'name': billing_cycle.name,
            'cycle_type': billing_cycle.cycle_type,
            'start_date': billing_cycle.start_date.strftime('%Y-%m-%d'),
            'end_date': billing_cycle.end_date.strftime('%Y-%m-%d'),
            'due_date': billing_cycle.due_date.strftime('%Y-%m-%d'),
            'is_active': billing_cycle.is_active,
            'description': billing_cycle.description,
            'created_at': billing_cycle.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'bill_summary': bill_summary
        }
        
        return JsonResponse({
            'success': True,
            'billing_cycle': cycle_data
        })
        
    except BillingCycle.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Billing cycle not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching billing cycle details: {str(e)}'
        }, status=500)

def get_upcoming_cycles(request):
    """Get upcoming billing cycles"""
    try:
        today = datetime.now().date()
        
        # Get active cycles with future start dates
        upcoming_cycles = BillingCycle.objects.filter(
            is_active=True,
            start_date__gte=today
        ).order_by('start_date')[:10]  # Limit to next 10 cycles
        
        cycles_data = []
        for cycle in upcoming_cycles:
            days_until_start = (cycle.start_date - today).days
            cycles_data.append({
                'id': cycle.id,
                'name': cycle.name,
                'cycle_type': cycle.cycle_type,
                'start_date': cycle.start_date.strftime('%Y-%m-%d'),
                'end_date': cycle.end_date.strftime('%Y-%m-%d'),
                'due_date': cycle.due_date.strftime('%Y-%m-%d'),
                'days_until_start': days_until_start,
                'description': cycle.description
            })
        
        return JsonResponse({
            'success': True,
            'upcoming_cycles': cycles_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching upcoming cycles: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def generate_cycles_batch(request):
    """Generate multiple billing cycles at once"""
    try:
        with transaction.atomic():
            data = json.loads(request.body)
            base_name = data.get('base_name')
            cycle_type = data.get('cycle_type')
            start_year = int(data.get('start_year'))
            number_of_cycles = int(data.get('number_of_cycles', 4))
            due_date_offset = int(data.get('due_date_offset', 30))  # days after end date
            
            if not all([base_name, cycle_type, start_year]):
                return JsonResponse({
                    'success': False,
                    'error': 'Base name, cycle type, and start year are required'
                }, status=400)
            
            # Define cycle periods based on type
            cycle_periods = {
                'annual': 12,
                'semi_annual': 6,
                'quarterly': 3,
                'monthly': 1
            }
            
            if cycle_type not in cycle_periods:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid cycle type. Must be one of: {", ".join(cycle_periods.keys())}'
                }, status=400)
            
            months_per_cycle = cycle_periods[cycle_type]
            generated_cycles = []
            errors = []
            
            for i in range(number_of_cycles):
                try:
                    # Calculate dates
                    start_month = i * months_per_cycle
                    start_date = date(start_year, 1, 1) + relativedelta(months=start_month)
                    
                    if cycle_type == 'annual':
                        end_date = start_date + relativedelta(years=1, days=-1)
                        cycle_name = f"{base_name} {start_date.year}"
                    elif cycle_type == 'semi_annual':
                        end_date = start_date + relativedelta(months=6, days=-1)
                        half = 'H1' if start_date.month <= 6 else 'H2'
                        cycle_name = f"{base_name} {start_date.year} {half}"
                    elif cycle_type == 'quarterly':
                        end_date = start_date + relativedelta(months=3, days=-1)
                        quarter = (start_date.month - 1) // 3 + 1
                        cycle_name = f"{base_name} {start_date.year} Q{quarter}"
                    else:  # monthly
                        end_date = start_date + relativedelta(months=1, days=-1)
                        cycle_name = f"{base_name} {start_date.strftime('%B %Y')}"
                    
                    due_date = end_date + timedelta(days=due_date_offset)
                    
                    # Check if cycle already exists
                    existing_cycle = BillingCycle.objects.filter(
                        cycle_type=cycle_type,
                        start_date=start_date,
                        end_date=end_date
                    ).exists()
                    
                    if existing_cycle:
                        errors.append(f'Cycle already exists for {cycle_name}')
                        continue
                    
                    # Create billing cycle
                    billing_cycle = BillingCycle.objects.create(
                        name=cycle_name,
                        cycle_type=cycle_type,
                        start_date=start_date,
                        end_date=end_date,
                        due_date=due_date,
                        description=f'Auto-generated {cycle_type} cycle',
                        is_active=True
                    )
                    
                    generated_cycles.append(cycle_name)
                    
                except Exception as e:
                    errors.append(f'Error generating cycle {i+1}: {str(e)}')
            
            return JsonResponse({
                'success': True,
                'message': f'Generated {len(generated_cycles)} billing cycles',
                'generated_cycles': generated_cycles,
                'errors': errors
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error generating cycles batch: {str(e)}'
        }, status=500)

def get_cycle_performance(request):
    """Get performance metrics for billing cycles"""
    try:
        # Get cycles from the last 2 years
        two_years_ago = datetime.now().date() - timedelta(days=730)
        
        cycles = BillingCycle.objects.filter(
            end_date__gte=two_years_ago
        ).prefetch_related('bills')
        
        performance_data = []
        
        for cycle in cycles:
            bills = cycle.bills.all()
            total_bills = bills.count()
            
            if total_bills == 0:
                continue
            
            paid_bills = bills.filter(status='paid').count()
            overdue_bills = bills.filter(status='overdue').count()
            total_amount = sum(bill.total_amount for bill in bills)
            collected_amount = sum(bill.total_amount for bill in bills.filter(status='paid'))
            
            collection_rate = (collected_amount / total_amount * 100) if total_amount > 0 else 0
            
            performance_data.append({
                'cycle_id': cycle.id,
                'cycle_name': cycle.name,
                'cycle_type': cycle.cycle_type,
                'period': f"{cycle.start_date.strftime('%b %Y')} - {cycle.end_date.strftime('%b %Y')}",
                'total_bills': total_bills,
                'paid_bills': paid_bills,
                'overdue_bills': overdue_bills,
                'total_amount': str(total_amount),
                'collected_amount': str(collected_amount),
                'collection_rate': round(collection_rate, 2),
                'completion_rate': round((paid_bills / total_bills * 100), 2) if total_bills > 0 else 0
            })
        
        # Sort by cycle end date (most recent first)
        performance_data.sort(key=lambda x: x['cycle_name'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'performance_data': performance_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error fetching cycle performance: {str(e)}'
        }, status=500)