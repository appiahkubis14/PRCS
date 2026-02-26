from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from core.models import Property, PropertyType, Zone
import json

@login_required
def property_classification(request):
    """Render the property classification page"""
    context = {
        'title': 'Property Classification',
        'path': 'Property Management/Property Classification',
        'properties': Property.objects.filter(is_deleted=False),
        'property_types': PropertyType.objects.filter(is_deleted=False),
        'zones': Zone.objects.filter(is_deleted=False),
    }
    return render(request, 'core/main/property-registry/property-classification.html', context)

@login_required
@require_http_methods(["GET"])
def get_classifications(request):
    """Get all property classifications for DataTable"""
    try:
        properties = Property.objects.filter(is_deleted=False).select_related(
            'zone', 'property_type'
        )
        
        data = []
        for prop in properties:
            # Calculate classification score based on various factors
            classification_score = calculate_classification_score(prop)
            classification_category = get_classification_category(classification_score)
            
            data.append({
                'id': prop.id,
                'property_id': prop.property_id,
                'address': prop.address,
                'zone': prop.zone.name if prop.zone else '',
                'property_type': prop.property_type.name if prop.property_type else '',
                'current_type': prop.property_type.name if prop.property_type else '',
                'current_zone': prop.zone.name if prop.zone else '',
                'market_value': float(prop.market_value) if prop.market_value else 0,
                'assessed_value': float(prop.assessed_value) if prop.assessed_value else 0,
                'total_area': float(prop.total_area) if prop.total_area else 0,
                'year_built': prop.year_built,
                'classification_score': classification_score,
                'classification_category': classification_category,
                'status': prop.status,
                'recommended_type': get_recommended_type(prop),
                'recommended_zone': get_recommended_zone(prop),
            })
        
        return JsonResponse({'data': data, 'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def calculate_classification_score(property_obj):
    """Calculate classification score based on property characteristics"""
    score = 0
    
    # Market value factor (0-40 points)
    if property_obj.market_value:
        if property_obj.market_value > 1000000:
            score += 40
        elif property_obj.market_value > 500000:
            score += 30
        elif property_obj.market_value > 200000:
            score += 20
        elif property_obj.market_value > 100000:
            score += 10
        else:
            score += 5
    
    # Area factor (0-20 points)
    if property_obj.total_area:
        if property_obj.total_area > 500:
            score += 20
        elif property_obj.total_area > 300:
            score += 15
        elif property_obj.total_area > 150:
            score += 10
        elif property_obj.total_area > 80:
            score += 5
        else:
            score += 2
    
    # Age factor (0-15 points)
    if property_obj.year_built:
        current_year = timezone.now().year
        age = current_year - property_obj.year_built
        if age < 5:
            score += 15
        elif age < 10:
            score += 12
        elif age < 20:
            score += 8
        elif age < 30:
            score += 5
        else:
            score += 2
    
    # Floor count factor (0-15 points)
    if property_obj.floor_count:
        if property_obj.floor_count > 5:
            score += 15
        elif property_obj.floor_count > 3:
            score += 10
        elif property_obj.floor_count > 1:
            score += 5
        else:
            score += 2
    
    # Zone factor (0-10 points)
    if property_obj.zone:
        zone_weights = {
            'commercial': 10,
            'mixed_use': 8,
            'residential': 6,
            'industrial': 5,
            'agricultural': 3
        }
        score += zone_weights.get(property_obj.zone.zone_type, 5)
    
    return min(score, 100)  # Cap at 100

def get_classification_category(score):
    """Get classification category based on score"""
    if score >= 80:
        return 'Premium'
    elif score >= 60:
        return 'High Value'
    elif score >= 40:
        return 'Medium Value'
    elif score >= 20:
        return 'Standard'
    else:
        return 'Basic'

def get_recommended_type(property_obj):
    """Get recommended property type based on characteristics"""
    if property_obj.market_value and property_obj.market_value > 500000:
        return 'Luxury'
    elif property_obj.total_area and property_obj.total_area > 300:
        return 'Large'
    elif property_obj.year_built and (timezone.now().year - property_obj.year_built) < 10:
        return 'Modern'
    else:
        return 'Standard'

def get_recommended_zone(property_obj):
    """Get recommended zone based on property characteristics"""
    if property_obj.market_value and property_obj.market_value > 300000:
        return 'Commercial'
    elif property_obj.total_area and property_obj.total_area > 200:
        return 'Mixed Use'
    else:
        return 'Residential'

@login_required
@require_http_methods(["POST"])
def update_classification(request, property_id):
    """Update property classification (type and zone)"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        data = request.POST.dict()
        
        with transaction.atomic():
            # Update property type and zone
            if data.get('property_type'):
                property_obj.property_type_id = data.get('property_type')
            if data.get('zone'):
                property_obj.zone_id = data.get('zone')
            
            property_obj.modified_by = request.user
            property_obj.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Property classification updated successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to update classification: {str(e)}'
        })

@login_required
@require_http_methods(["GET"])
def get_classification_analysis(request, property_id):
    """Get detailed classification analysis for a property"""
    try:
        property_obj = get_object_or_404(Property, id=property_id, is_deleted=False)
        
        # Calculate detailed scores
        market_value_score = calculate_market_value_score(property_obj.market_value)
        area_score = calculate_area_score(property_obj.total_area)
        age_score = calculate_age_score(property_obj.year_built)
        floor_score = calculate_floor_score(property_obj.floor_count)
        zone_score = calculate_zone_score(property_obj.zone)
        
        total_score = market_value_score + area_score + age_score + floor_score + zone_score
        category = get_classification_category(total_score)
        
        analysis_data = {
            'property_id': property_obj.property_id,
            'address': property_obj.address,
            'current_type': property_obj.property_type.name if property_obj.property_type else '',
            'current_zone': property_obj.zone.name if property_obj.zone else '',
            'market_value': float(property_obj.market_value) if property_obj.market_value else 0,
            'market_value_score': market_value_score,
            'total_area': float(property_obj.total_area) if property_obj.total_area else 0,
            'area_score': area_score,
            'year_built': property_obj.year_built,
            'age_score': age_score,
            'floor_count': property_obj.floor_count,
            'floor_score': floor_score,
            'zone_type': property_obj.zone.zone_type if property_obj.zone else '',
            'zone_score': zone_score,
            'total_score': total_score,
            'classification_category': category,
            'recommended_type': get_recommended_type(property_obj),
            'recommended_zone': get_recommended_zone(property_obj),
        }
        
        return JsonResponse({'success': True, 'data': analysis_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def calculate_market_value_score(market_value):
    """Calculate market value score"""
    if not market_value:
        return 0
    if market_value > 1000000:
        return 40
    elif market_value > 500000:
        return 30
    elif market_value > 200000:
        return 20
    elif market_value > 100000:
        return 10
    else:
        return 5

def calculate_area_score(total_area):
    """Calculate area score"""
    if not total_area:
        return 0
    if total_area > 500:
        return 20
    elif total_area > 300:
        return 15
    elif total_area > 150:
        return 10
    elif total_area > 80:
        return 5
    else:
        return 2

def calculate_age_score(year_built):
    """Calculate age score"""
    if not year_built:
        return 0
    current_year = timezone.now().year
    age = current_year - year_built
    if age < 5:
        return 15
    elif age < 10:
        return 12
    elif age < 20:
        return 8
    elif age < 30:
        return 5
    else:
        return 2

def calculate_floor_score(floor_count):
    """Calculate floor count score"""
    if not floor_count:
        return 0
    if floor_count > 5:
        return 15
    elif floor_count > 3:
        return 10
    elif floor_count > 1:
        return 5
    else:
        return 2

def calculate_zone_score(zone):
    """Calculate zone score"""
    if not zone:
        return 0
    zone_weights = {
        'commercial': 10,
        'mixed_use': 8,
        'residential': 6,
        'industrial': 5,
        'agricultural': 3
    }
    return zone_weights.get(zone.zone_type, 5)

@login_required
@require_http_methods(["GET"])
def get_classification_stats(request):
    """Get classification statistics"""
    try:
        properties = Property.objects.filter(is_deleted=False)
        total_properties = properties.count()
        
        # Count by classification category
        categories = {}
        for prop in properties:
            score = calculate_classification_score(prop)
            category = get_classification_category(score)
            categories[category] = categories.get(category, 0) + 1
        
        # Count by property type
        type_stats = {}
        for prop_type in PropertyType.objects.filter(is_deleted=False):
            count = properties.filter(property_type=prop_type).count()
            if count > 0:
                type_stats[prop_type.name] = count
        
        # Count by zone
        zone_stats = {}
        for zone in Zone.objects.filter(is_deleted=False):
            count = properties.filter(zone=zone).count()
            if count > 0:
                zone_stats[zone.name] = count
        
        stats = {
            'total_properties': total_properties,
            'categories': categories,
            'property_types': type_stats,
            'zones': zone_stats,
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})