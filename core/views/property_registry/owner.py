from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Sum
from core.models import PropertyOwner, Property, User
import json

@login_required
def owner_management(request):
    """Render the owner management page"""
    context = {
        'title': 'Owner Management',
        'path': 'Property Management/Owner Management',
        'properties': Property.objects.filter(is_deleted=False),
    }
    return render(request, 'core/main/property-registry/property-owners.html', context)

@login_required
@require_http_methods(["GET"])
def get_owners(request):
    """Get all property owners for DataTable"""
    try:
        owners = PropertyOwner.objects.filter(is_deleted=False).select_related(
            'property', 'property__zone', 'property__property_type'
        )
        
        data = []
        for owner in owners:
            prop = owner.property
            
            data.append({
                'id': owner.id,
                'owner_name': owner.owner_name,
                'owner_type': owner.owner_type,
                # 'property_id': prop.property_id,
                'property_address': prop.address,
                'property_zone': prop.zone.name if prop.zone else '',
                'property_type': prop.property_type.name if prop.property_type else '',
                'id_number': owner.id_number,
                'phone_number': owner.phone_number,
                'email': owner.email,
                'ownership_percentage': float(owner.ownership_percentage),
                'is_primary_owner': owner.is_primary_owner,
                'start_date': owner.start_date.strftime('%Y-%m-%d') if owner.start_date else '',
                'end_date': owner.end_date.strftime('%Y-%m-%d') if owner.end_date else '',
                'owner_address': owner.address,
                # 'property_status': prop.status,
                # 'property_value': float(prop.market_value) if prop.market_value else 0,
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def add_owner(request):
    """Add new property owner"""
    try:
        data = request.POST.dict()
        
        with transaction.atomic():
            # If setting as primary owner, remove existing primary owners for this property
            if data.get('is_primary_owner') == 'true':
                PropertyOwner.objects.filter(
                    property_id=data.get('property'),
                    is_primary_owner=True,
                    is_deleted=False
                ).update(is_primary_owner=False)
            
            # Create new owner
            owner = PropertyOwner(
                property_id=data.get('property'),
                owner_name=data.get('owner_name'),
                owner_type=data.get('owner_type'),
                id_number=data.get('id_number', ''),
                phone_number=data.get('phone_number', ''),
                email=data.get('email', ''),
                address=data.get('owner_address', ''),
                ownership_percentage=data.get('ownership_percentage', 100.00),
                is_primary_owner=data.get('is_primary_owner') == 'true',
                start_date=data.get('start_date'),
                end_date=data.get('end_date') or None,
                added_by=request.user
            )
            owner.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Property owner added successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to add owner: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_owner_detail(request, owner_id):
    """Get owner details for editing"""
    try:
        owner = get_object_or_404(PropertyOwner, id=owner_id, is_deleted=False)
        prop = owner.property
        
        data = {
            'id': owner.id,
            'property_id': prop.id,
            'property_display': f"{prop.property_id} - {prop.address}",
            'owner_name': owner.owner_name,
            'owner_type': owner.owner_type,
            'id_number': owner.id_number,
            'phone_number': owner.phone_number,
            'email': owner.email,
            'owner_address': owner.address,
            'ownership_percentage': float(owner.ownership_percentage),
            'is_primary_owner': owner.is_primary_owner,
            'start_date': owner.start_date.strftime('%Y-%m-%d') if owner.start_date else '',
            'end_date': owner.end_date.strftime('%Y-%m-%d') if owner.end_date else '',
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_owner(request, owner_id):
    """Update property owner details"""
    try:
        owner = get_object_or_404(PropertyOwner, id=owner_id, is_deleted=False)
        data = request.POST.dict()
        
        with transaction.atomic():
            # If setting as primary owner, remove existing primary owners for this property
            if data.get('is_primary_owner') == 'true' and not owner.is_primary_owner:
                PropertyOwner.objects.filter(
                    property=owner.property,
                    is_primary_owner=True,
                    is_deleted=False
                ).exclude(id=owner_id).update(is_primary_owner=False)
            
            # Update owner details
            owner.owner_name = data.get('owner_name', owner.owner_name)
            owner.owner_type = data.get('owner_type', owner.owner_type)
            owner.id_number = data.get('id_number', owner.id_number)
            owner.phone_number = data.get('phone_number', owner.phone_number)
            owner.email = data.get('email', owner.email)
            owner.address = data.get('owner_address', owner.address)
            owner.ownership_percentage = data.get('ownership_percentage', owner.ownership_percentage)
            owner.is_primary_owner = data.get('is_primary_owner') == 'true'
            owner.start_date = data.get('start_date', owner.start_date)
            owner.end_date = data.get('end_date') or None
            owner.modified_by = request.user
            
            owner.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Owner details updated successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to update owner: {str(e)}'
        })

@login_required
@require_http_methods(["DELETE"])
def delete_owner(request, owner_id):
    """Delete property owner (soft delete)"""
    try:
        owner = get_object_or_404(PropertyOwner, id=owner_id, is_deleted=False)
        
        owner.is_deleted = True
        owner.deleted_by = request.user
        owner.deleted_at = timezone.now()
        owner.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Owner deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to delete owner: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_owner_stats(request):
    """Get owner management statistics"""
    try:
        total_owners = PropertyOwner.objects.filter(is_deleted=False).count()
        primary_owners = PropertyOwner.objects.filter(is_primary_owner=True, is_deleted=False).count()
        individual_owners = PropertyOwner.objects.filter(owner_type='individual', is_deleted=False).count()
        company_owners = PropertyOwner.objects.filter(owner_type='company', is_deleted=False).count()
        government_owners = PropertyOwner.objects.filter(owner_type='government', is_deleted=False).count()
        trust_owners = PropertyOwner.objects.filter(owner_type='trust', is_deleted=False).count()
        
        # Properties without owners
        properties_with_owners = Property.objects.filter(
            is_deleted=False,
            owners__is_deleted=False
        ).distinct().count()
        
        total_properties = Property.objects.filter(is_deleted=False).count()
        properties_without_owners = total_properties - properties_with_owners
        
        # Ownership distribution
        ownership_stats = PropertyOwner.objects.filter(
            is_deleted=False
        ).values('owner_type').annotate(
            count=Count('id'),
            total_value=Sum('property__market_value')
        )
        
        stats = {
            'total_owners': total_owners,
            'primary_owners': primary_owners,
            'individual_owners': individual_owners,
            'company_owners': company_owners,
            'government_owners': government_owners,
            'trust_owners': trust_owners,
            'total_properties': total_properties,
            'properties_with_owners': properties_with_owners,
            'properties_without_owners': properties_without_owners,
            'ownership_distribution': list(ownership_stats),
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def search_owners(request):
    """Search owners by name, ID, or property"""
    try:
        query = request.GET.get('q', '')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Search query required'})
        
        owners = PropertyOwner.objects.filter(
            Q(owner_name__icontains=query) |
            Q(id_number__icontains=query) |
            Q(property__property_id__icontains=query) |
            Q(property__address__icontains=query),
            is_deleted=False
        ).select_related('property')[:50]  # Limit results
        
        data = []
        for owner in owners:
            prop = owner.property
            data.append({
                'id': owner.id,
                'owner_name': owner.owner_name,
                'owner_type': owner.owner_type,
                'id_number': owner.id_number,
                'phone_number': owner.phone_number,
                'property_id': prop.property_id,
                'property_address': prop.address,
                'is_primary_owner': owner.is_primary_owner,
                'ownership_percentage': float(owner.ownership_percentage),
            })
        
        return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def get_property_owners(request, property_id):
    """Get all owners for a specific property"""
    try:
        print(f"Fetching owners for property ID: {property_id}")
        
        # Correct way to get the property object
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        print(f"Found property: {property_obj.property_id} - {property_obj.address}")
        
        owners = PropertyOwner.objects.filter(property=property_obj, is_deleted=False)
        print(f"Found {owners.count()} owners for this property")
        
        data = []
        for owner in owners:
            data.append({
                'id': owner.id,
                'owner_name': owner.owner_name,
                'owner_type': owner.owner_type,
                'id_number': owner.id_number,
                'phone_number': owner.phone_number,
                'email': owner.email,
                'ownership_percentage': float(owner.ownership_percentage),
                'is_primary_owner': owner.is_primary_owner,
                'start_date': owner.start_date.strftime('%Y-%m-%d') if owner.start_date else '',
                'end_date': owner.end_date.strftime('%Y-%m-%d') if owner.end_date else '',
            })
        
        return JsonResponse({
            'success': True, 
            'data': data, 
            'property_id': property_obj.property_id,
            'property_address': property_obj.address
        })
        
    except Property.DoesNotExist:
        print(f"Property with ID {property_id} does not exist")
        return JsonResponse({
            'success': False, 
            'error': f'Property with ID {property_id} not found'
        })
    except Exception as e:
        print(f"Error fetching property owners: {str(e)}")
        return JsonResponse({
            'success': False, 
            'error': f'Failed to fetch property owners: {str(e)}'
        })