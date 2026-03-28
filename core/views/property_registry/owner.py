from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum, F, Value
from django.db.models.functions import Concat
from decimal import Decimal
import json
import logging

from core.models import PropertyRate, Polygon, Bill, Payment

logger = logging.getLogger(__name__)

@login_required
def owner_management(request):
    """Render the owner management page"""
    # Get all polygons/properties for dropdown
    polygons = Polygon.objects.filter(
       
    ).select_related().values('id', 'division', 'block', 'property', 'location')[:500]
    
    # Prepare polygon display names
    polygon_list = []
    for poly in polygons:
        display_name = f"Div {poly['division']} - Blk {poly['block']} (Prop {poly['property']})"
        if poly['location']:
            display_name += f" - {poly['location']}"
        polygon_list.append({
            'id': poly['id'],
            'display_name': display_name,
            'division': poly['division'],
            'block': poly['block'],
            'property_no': poly['property']
        })
    
    context = {
        'title': 'Owner Management',
        'path': 'Property Management/Owner Management',
        'polygons': polygon_list,
    }
    return render(request, 'core/main/property-registry/property-owners.html', context)

@login_required
@require_http_methods(["GET"])
def get_owners(request):
    """Get all property owners from PropertyRate data"""
    try:
        # Get all property rates with owner information
        owners = PropertyRate.objects.filter(
            Q(surname__isnull=False) | Q(prop_owner__isnull=False)
        ).exclude(
            Q(surname='') & Q(prop_owner='') & Q(first_name='')
        ).select_related('polygon')
        
        # Apply filters
        owner_type = request.GET.get('owner_type', '')
        search = request.GET.get('search', '')
        
        if owner_type:
            # This is a simplified filter - you can enhance based on your data
            if owner_type == 'individual':
                owners = owners.filter(surname__isnull=False).exclude(surname='')
            elif owner_type == 'company':
                owners = owners.filter(prop_owner__isnull=False).exclude(prop_owner='')
        
        if search:
            owners = owners.filter(
                Q(surname__icontains=search) |
                Q(first_name__icontains=search) |
                Q(prop_owner__icontains=search) |
                Q(prop_name__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(email__icontains=search) |
                Q(tin_number__icontains=search)
            )
        
        # Order by surname or prop_owner
        owners = owners.order_by('surname', 'first_name', 'prop_owner')
        
        data = []
        for owner in owners:
            polygon = owner.polygon
            
            # Determine owner type
            owner_type_value = 'individual'
            if owner.prop_owner and owner.prop_owner.strip():
                owner_type_value = 'company'
            elif owner.surname and owner.surname.strip():
                owner_type_value = 'individual'
            
            # Build owner name
            owner_name = ""
            if owner.title:
                owner_name += f"{owner.title} "
            if owner.first_name:
                owner_name += f"{owner.first_name} "
            if owner.surname:
                owner_name += owner.surname
            if not owner_name and owner.prop_owner:
                owner_name = owner.prop_owner
            if not owner_name:
                owner_name = "Unknown Owner"
            
            # Build property display
            property_display = ""
            if polygon:
                property_display = f"Div {polygon.division} / Blk {polygon.block}"
                if polygon.location:
                    property_display += f" - {polygon.location}"
            else:
                if owner.division and owner.block:
                    property_display = f"Div {owner.division} / Blk {owner.block}"
                elif owner.prop_address:
                    property_display = owner.prop_address[:50]
                else:
                    property_display = "No property linked"
            
            # Get bill statistics for this property
            bill_stats = {'total_bills': 0, 'total_amount': 0, 'total_paid': 0}
            if polygon:
                bills = Bill.objects.filter(polygon=polygon,)
                bill_stats['total_bills'] = bills.count()
                bill_stats['total_amount'] = float(bills.aggregate(Sum('amount'))['amount__sum'] or 0)
                bill_stats['total_paid'] = float(bills.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0)
            
            data.append({
                'id': owner.id,
                'owner_name': owner_name,
                'owner_type': owner_type_value,
                'owner_address': owner.prop_address or owner.landmark or '',
                'id_number': owner.tin_number or '',
                'phone_number': owner.mobile_number or '',
                'email': owner.email or '',
                'property_id': polygon.id if polygon else None,
                'property_display': property_display,
                'property_address': owner.prop_address or '',
                'property_zone': owner.area_zone or '',
                'property_type': owner.prop_type or '',
                'division': polygon.division if polygon else owner.division,
                'block': polygon.block if polygon else owner.block,
                'ownership_percentage': 100.0,  # Default to 100% since we don't have multiple owners per property
                'is_primary_owner': True,  # Since each property rate record is one owner
                'start_date': owner.imported_at.strftime('%Y-%m-%d') if owner.imported_at else '',
                'end_date': '',
                'property_status': polygon.status if polygon else 'unknown',
                'rateable_value': float(owner.rateable_value) if owner.rateable_value else 0,
                'total_bills': bill_stats['total_bills'],
                'total_amount': bill_stats['total_amount'],
                'total_paid': bill_stats['total_paid'],
                'payment_rate': (bill_stats['total_paid'] / bill_stats['total_amount'] * 100) if bill_stats['total_amount'] > 0 else 0
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        logger.error(f"Error in get_owners: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_owner_detail(request, owner_id):
    """Get owner details for editing"""
    try:
        owner = get_object_or_404(PropertyRate, id=owner_id)
        polygon = owner.polygon
        
        # Build owner name
        owner_name = ""
        if owner.title:
            owner_name += f"{owner.title} "
        if owner.first_name:
            owner_name += f"{owner.first_name} "
        if owner.surname:
            owner_name += owner.surname
        if not owner_name and owner.prop_owner:
            owner_name = owner.prop_owner
        
        # Build property display
        property_display = ""
        if polygon:
            property_display = f"Div {polygon.division} - Blk {polygon.block} (Prop {polygon.property})"
            if polygon.location:
                property_display += f" - {polygon.location}"
        
        data = {
            'id': owner.id,
            'polygon_id': polygon.id if polygon else None,
            'property_display': property_display,
            'owner_name': owner_name,
            'owner_type': 'company' if owner.prop_owner else 'individual',
            'id_number': owner.tin_number or '',
            'phone_number': owner.mobile_number or '',
            'email': owner.email or '',
            'owner_address': owner.prop_address or owner.landmark or '',
            'ownership_percentage': 100.0,
            'is_primary_owner': True,
            'start_date': owner.imported_at.strftime('%Y-%m-%d') if owner.imported_at else '',
            'end_date': '',
            'prop_type': owner.prop_type or '',
            'area_zone': owner.area_zone or '',
            'suburb': owner.suburb or '',
            'street_name': owner.street_name or '',
            'house_no': owner.house_no or '',
            'prop_name': owner.prop_name or '',
            'rateable_value': float(owner.rateable_value) if owner.rateable_value else 0,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error in get_owner_detail: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_owner(request, owner_id):
    """Update owner details"""
    try:
        owner = get_object_or_404(PropertyRate, id=owner_id)
        data = request.POST.dict()
        
        # Update owner fields
        if 'owner_name' in data:
            # Parse owner name into title, first_name, surname
            name_parts = data['owner_name'].strip().split()
            if len(name_parts) >= 2:
                owner.first_name = name_parts[0]
                owner.surname = ' '.join(name_parts[1:])
            else:
                owner.surname = data['owner_name']
        
        if 'owner_type' in data:
            if data['owner_type'] == 'company' and data.get('owner_name'):
                owner.prop_owner = data['owner_name']
            elif data['owner_type'] == 'individual':
                owner.prop_owner = ''
        
        if 'id_number' in data:
            owner.tin_number = data['id_number']
        if 'phone_number' in data:
            owner.mobile_number = data['phone_number']
        if 'email' in data:
            owner.email = data['email']
        if 'owner_address' in data:
            owner.prop_address = data['owner_address']
        if 'prop_type' in data:
            owner.prop_type = data['prop_type']
        if 'area_zone' in data:
            owner.area_zone = data['area_zone']
        if 'suburb' in data:
            owner.suburb = data['suburb']
        if 'street_name' in data:
            owner.street_name = data['street_name']
        if 'house_no' in data:
            owner.house_no = data['house_no']
        if 'prop_name' in data:
            owner.prop_name = data['prop_name']
        if 'rateable_value' in data and data['rateable_value']:
            owner.rateable_value = Decimal(str(data['rateable_value']))
        
        owner.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Owner details updated successfully!'
        })
        
    except Exception as e:
        logger.error(f"Error in update_owner: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': f'Failed to update owner: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_owner_stats(request):
    """Get owner management statistics"""
    try:
        # Get all property rates with owner info
        all_owners = PropertyRate.objects.filter(
            Q(surname__isnull=False) | Q(prop_owner__isnull=False)
        ).exclude(
            Q(surname='') & Q(prop_owner='')
        )
        
        total_owners = all_owners.count()
        
        # Count by owner type
        individual_owners = all_owners.filter(
            surname__isnull=False
        ).exclude(surname='').count()
        
        company_owners = all_owners.filter(
            prop_owner__isnull=False
        ).exclude(prop_owner='').count()
        
        # Properties with owners
        properties_with_owners = all_owners.filter(
            polygon__isnull=False
        ).values('polygon').distinct().count()
        
        total_properties = Polygon.objects.all().count()
        properties_without_owners = total_properties - properties_with_owners
        
        # Calculate total property value
        total_value = all_owners.aggregate(
            total=Sum('rateable_value')
        )['total'] or 0
        
        # Get bill statistics
        bills = Bill.objects.all()
        total_bills = bills.count()
        total_bill_amount = bills.aggregate(total=Sum('amount'))['total'] or 0
        total_paid_amount = bills.aggregate(total=Sum('amount_paid'))['total'] or 0
        collection_rate = (float(total_paid_amount) / float(total_bill_amount) * 100) if total_bill_amount > 0 else 0
        
        # Ownership distribution by property type
        ownership_by_type = all_owners.values('prop_type').annotate(
            count=Count('id'),
            total_value=Sum('rateable_value')
        ).order_by('-count')[:10]
        
        stats = {
            'total_owners': total_owners,
            'primary_owners': total_owners,  # All are considered primary in current data structure
            'individual_owners': individual_owners,
            'company_owners': company_owners,
            'government_owners': 0,  # Not available in current data
            'trust_owners': 0,  # Not available in current data
            'total_properties': total_properties,
            'properties_with_owners': properties_with_owners,
            'properties_without_owners': properties_without_owners,
            'total_property_value': float(total_value),
            'total_bills': total_bills,
            'total_bill_amount': float(total_bill_amount),
            'total_paid_amount': float(total_paid_amount),
            'collection_rate': round(collection_rate, 2),
            'ownership_distribution': list(ownership_by_type),
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        logger.error(f"Error in get_owner_stats: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def search_owners(request):
    """Search owners by name, ID, or property"""
    try:
        query = request.GET.get('q', '')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Search query required'})
        
        owners = PropertyRate.objects.filter(
            Q(surname__icontains=query) |
            Q(first_name__icontains=query) |
            Q(prop_owner__icontains=query) |
            Q(prop_name__icontains=query) |
            Q(mobile_number__icontains=query) |
            Q(email__icontains=query) |
            Q(tin_number__icontains=query) |
            Q(valuation_no__icontains=query)
        ).select_related('polygon')[:50]
        
        data = []
        for owner in owners:
            polygon = owner.polygon
            
            owner_name = ""
            if owner.title:
                owner_name += f"{owner.title} "
            if owner.first_name:
                owner_name += f"{owner.first_name} "
            if owner.surname:
                owner_name += owner.surname
            if not owner_name and owner.prop_owner:
                owner_name = owner.prop_owner
            
            data.append({
                'id': owner.id,
                'owner_name': owner_name,
                'owner_type': 'company' if owner.prop_owner else 'individual',
                'id_number': owner.tin_number or '',
                'phone_number': owner.mobile_number or '',
                'email': owner.email or '',
                'property_id': polygon.id if polygon else None,
                'property_display': f"Div {polygon.division} / Blk {polygon.block}" if polygon else owner.prop_address,
                'is_primary_owner': True,
                'ownership_percentage': 100.0,
            })
        
        return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        
    except Exception as e:
        logger.error(f"Error in search_owners: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_property_owners(request, property_id):
    """Get all owners for a specific property"""
    try:
        polygon = get_object_or_404(Polygon, id=property_id,)
        
        # Get property rates linked to this polygon
        property_rates = PropertyRate.objects.filter(polygon=polygon)
        
        data = []
        for pr in property_rates:
            owner_name = ""
            if pr.title:
                owner_name += f"{pr.title} "
            if pr.first_name:
                owner_name += f"{pr.first_name} "
            if pr.surname:
                owner_name += pr.surname
            if not owner_name and pr.prop_owner:
                owner_name = pr.prop_owner
            if not owner_name:
                owner_name = "Unknown Owner"
            
            data.append({
                'id': pr.id,
                'owner_name': owner_name,
                'owner_type': 'company' if pr.prop_owner else 'individual',
                'id_number': pr.tin_number or '',
                'phone_number': pr.mobile_number or '',
                'email': pr.email or '',
                'ownership_percentage': 100.0,
                'is_primary_owner': True,
                'start_date': pr.imported_at.strftime('%Y-%m-%d') if pr.imported_at else '',
                'end_date': '',
                'rateable_value': float(pr.rateable_value) if pr.rateable_value else 0,
            })
        
        return JsonResponse({
            'success': True, 
            'data': data, 
            'property_id': polygon.id,
            'property_display': f"Div {polygon.division} - Blk {polygon.block} (Prop {polygon.property})"
        })
        
    except Exception as e:
        logger.error(f"Error in get_property_owners: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': f'Failed to fetch property owners: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def export_owners(request):
    """Export owners data in CSV format"""
    try:
        import csv
        from django.http import HttpResponse
        
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="property_owners_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Owner ID', 'Owner Name', 'Owner Type', 'ID Number', 'Phone Number', 
            'Email', 'Address', 'Property Division', 'Property Block', 
            'Property Address', 'Zone', 'Property Type', 'Rateable Value (GHS)',
            'Total Bills', 'Total Amount (GHS)', 'Total Paid (GHS)', 'Payment Rate (%)'
        ])
        
        # Get data
        owners = PropertyRate.objects.filter(
            Q(surname__isnull=False) | Q(prop_owner__isnull=False)
        ).exclude(
            Q(surname='') & Q(prop_owner='')
        ).select_related('polygon')
        
        for owner in owners:
            polygon = owner.polygon
            
            owner_name = ""
            if owner.title:
                owner_name += f"{owner.title} "
            if owner.first_name:
                owner_name += f"{owner.first_name} "
            if owner.surname:
                owner_name += owner.surname
            if not owner_name and owner.prop_owner:
                owner_name = owner.prop_owner
            
            owner_type = 'company' if owner.prop_owner else 'individual'
            
            # Get bill stats
            bill_stats = {'total_bills': 0, 'total_amount': 0, 'total_paid': 0}
            if polygon:
                bills = Bill.objects.filter(polygon=polygon,)
                bill_stats['total_bills'] = bills.count()
                bill_stats['total_amount'] = float(bills.aggregate(Sum('amount'))['amount__sum'] or 0)
                bill_stats['total_paid'] = float(bills.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0)
            
            payment_rate = (bill_stats['total_paid'] / bill_stats['total_amount'] * 100) if bill_stats['total_amount'] > 0 else 0
            
            writer.writerow([
                owner.id,
                owner_name,
                owner_type,
                owner.tin_number or '',
                owner.mobile_number or '',
                owner.email or '',
                owner.prop_address or '',
                polygon.division if polygon else owner.division or '',
                polygon.block if polygon else owner.block or '',
                owner.prop_address or '',
                owner.area_zone or '',
                owner.prop_type or '',
                float(owner.rateable_value) if owner.rateable_value else 0,
                bill_stats['total_bills'],
                bill_stats['total_amount'],
                bill_stats['total_paid'],
                round(payment_rate, 2)
            ])
        
        return response
        
    except Exception as e:
        logger.error(f"Error in export_owners: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})