from datetime import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.contrib import messages
from core.models import Property, PropertyOwner, Zone, PropertyType, Region, District
import json
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Q


@login_required
def property_registry(request):
    """Render the property registry page"""
    context = {
        'title': 'Property Registry',
        'path': 'Property Management/Property Registry',
        'zones': Zone.objects.filter(is_deleted=False),
        'property_types': PropertyType.objects.filter(is_deleted=False),
        'regions': Region.objects.filter(is_deleted=False),
        'districts': District.objects.filter(is_deleted=False),
    }
    return render(request, 'core/main/property-registry/property-registry.html', context)

@login_required
@require_http_methods(["GET"])
def get_properties(request):
    """Get all properties for DataTable"""
    try:
        properties = Property.objects.filter(is_deleted=False).select_related(
            'zone', 'property_type'
        )
        
        data = []
        for prop in properties:
            # Get primary owner
            primary_owner = prop.owners.filter(
                is_primary_owner=True, 
                is_deleted=False
            ).first()
            
            owner_name = primary_owner.owner_name if primary_owner else "No Owner"
            
            data.append({
                'id': prop.id,
                'property_id': prop.property_id,
                'address': prop.address,
                'zone': prop.zone.name if prop.zone else '',
                'property_type': prop.property_type.name if prop.property_type else '',
                'total_area': float(prop.total_area) if prop.total_area else 0,
                'market_value': float(prop.market_value) if prop.market_value else 0,
                'assessed_value': float(prop.assessed_value) if prop.assessed_value else 0,
                'status': prop.status,
                'owner_name': owner_name,
                'region': prop.region,
                'district': prop.district,
                'year_built': prop.year_built,
                'floor_count': prop.floor_count,
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def add_property(request):
    """Add new property"""
    try:
        data = request.POST.dict()
        files = request.FILES
        print(data)
        
        with transaction.atomic():
            # Create property
            property_obj = Property(
                property_id=data.get('property_id'),
                address=data.get('address'),
                zone_id=data.get('zone'),
                property_type_id=data.get('property_type'),
                total_area=data.get('total_area'),
                built_up_area=data.get('built_up_area') or None,
                floor_count=data.get('floor_count', 1),
                year_built=data.get('year_built') or None,
                market_value=data.get('market_value'),
                assessed_value=data.get('assessed_value'),
                status=data.get('status', 'active'),
                region=data.get('region'),
                district=data.get('district'),
                postcode=data.get('postcode'),
                street=data.get('street'),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                added_by=request.user
            )
            
            # Handle coordinates
            if data.get('latitude') and data.get('longitude'):
                property_obj.coordinates = {
                    'lat': float(data.get('latitude')),
                    'lng': float(data.get('longitude'))
                }
            
            property_obj.save()
            
            # Create primary owner if provided
            owner_name = data.get('owner_name')
            if owner_name:
                PropertyOwner.objects.create(
                    property=property_obj,
                    owner_name=owner_name,
                    owner_type=data.get('owner_type', 'individual'),
                    id_number=data.get('id_number', ''),
                    phone_number=data.get('phone_number', ''),
                    email=data.get('email', ''),
                    address=data.get('owner_address', ''),
                    ownership_percentage=100.00,
                    is_primary_owner=True,
                    start_date=data.get('start_date'),
                    added_by=request.user
                )
        
        return JsonResponse({
            'success': True, 
            'message': 'Property added successfully!'
        })
        
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False, 
            'error': f'Failed to add property: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_property_detail(request, property_id):
    """Get property details for editing"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        primary_owner = property_obj.owners.filter(
            is_primary_owner=True, 
            is_deleted=False
        ).first()
        
        data = {
            'id': property_obj.id,
            'property_id': property_obj.property_id,
            'address': property_obj.address,
            'zone_id': property_obj.zone_id,
            'property_type_id': property_obj.property_type_id,
            'total_area': float(property_obj.total_area) if property_obj.total_area else None,
            'built_up_area': float(property_obj.built_up_area) if property_obj.built_up_area else None,
            'floor_count': property_obj.floor_count,
            'year_built': property_obj.year_built,
            'market_value': float(property_obj.market_value) if property_obj.market_value else None,
            'assessed_value': float(property_obj.assessed_value) if property_obj.assessed_value else None,
            'status': property_obj.status,
            'region': property_obj.region,
            'district': property_obj.district,
            'postcode': property_obj.postcode,
            'street': property_obj.street,
            'latitude': float(property_obj.latitude) if property_obj.latitude else None,
            'longitude': float(property_obj.longitude) if property_obj.longitude else None,
            'coordinates': property_obj.coordinates,
        }
        
        if primary_owner:
            data.update({
                'owner_name': primary_owner.owner_name,
                'owner_type': primary_owner.owner_type,
                'id_number': primary_owner.id_number,
                'phone_number': primary_owner.phone_number,
                'email': primary_owner.email,
                'owner_address': primary_owner.address,
                'start_date': primary_owner.start_date.strftime('%Y-%m-%d') if primary_owner.start_date else None,
            })
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_property(request, property_id):
    """Update property details"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        data = request.POST.dict()
        files = request.FILES
        
        with transaction.atomic():
            # Update property fields
            property_obj.address = data.get('address', property_obj.address)
            property_obj.zone_id = data.get('zone', property_obj.zone_id)
            property_obj.property_type_id = data.get('property_type', property_obj.property_type_id)
            property_obj.total_area = data.get('total_area', property_obj.total_area)
            property_obj.built_up_area = data.get('built_up_area') or None
            property_obj.floor_count = data.get('floor_count', property_obj.floor_count)
            property_obj.year_built = data.get('year_built') or None
            property_obj.market_value = data.get('market_value', property_obj.market_value)
            property_obj.assessed_value = data.get('assessed_value', property_obj.assessed_value)
            property_obj.status = data.get('status', property_obj.status)
            property_obj.region = data.get('region', property_obj.region)
            property_obj.district = data.get('district', property_obj.district)
            property_obj.postcode = data.get('postcode', property_obj.postcode)
            property_obj.street = data.get('street', property_obj.street)
            property_obj.latitude = data.get('latitude', property_obj.latitude)
            property_obj.longitude = data.get('longitude', property_obj.longitude)
            property_obj.modified_by = request.user
            
            # Update coordinates
            if data.get('latitude') and data.get('longitude'):
                property_obj.coordinates = {
                    'lat': float(data.get('latitude')),
                    'lng': float(data.get('longitude'))
                }
            
            property_obj.save()
            
            # Update or create primary owner
            owner_name = data.get('owner_name')
            primary_owner = property_obj.owners.filter(
                is_primary_owner=True, 
                is_deleted=False
            ).first()
            
            if owner_name:
                if primary_owner:
                    primary_owner.owner_name = owner_name
                    primary_owner.owner_type = data.get('owner_type', primary_owner.owner_type)
                    primary_owner.id_number = data.get('id_number', primary_owner.id_number)
                    primary_owner.phone_number = data.get('phone_number', primary_owner.phone_number)
                    primary_owner.email = data.get('email', primary_owner.email)
                    primary_owner.address = data.get('owner_address', primary_owner.address)
                    primary_owner.start_date = data.get('start_date', primary_owner.start_date)
                    primary_owner.modified_by = request.user
                    primary_owner.save()
                else:
                    PropertyOwner.objects.create(
                        property=property_obj,
                        owner_name=owner_name,
                        owner_type=data.get('owner_type', 'individual'),
                        id_number=data.get('id_number', ''),
                        phone_number=data.get('phone_number', ''),
                        email=data.get('email', ''),
                        address=data.get('owner_address', ''),
                        ownership_percentage=100.00,
                        is_primary_owner=True,
                        start_date=data.get('start_date'),
                        added_by=request.user
                    )
        
        return JsonResponse({
            'success': True, 
            'message': 'Property updated successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to update property: {str(e)}'
        })

@login_required
@require_http_methods(["DELETE"])
def delete_property(request, property_id):
    """Soft delete property"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        
        property_obj.is_deleted = True
        property_obj.deleted_by = request.user
        property_obj.deleted_at = timezone.now()
        property_obj.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Property deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to delete property: {str(e)}'
        })