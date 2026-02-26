# views.py
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from rest_framework.decorators import api_view
from core.models import Property, Zone, District, PropertyType, Region
import json

@api_view(['GET'])
def properties_list(request):
    """Get filtered properties list"""
    # Get filters from query parameters
    filters = {}
    
    if district := request.GET.get('district'):
        filters['district__icontains'] = district
    
    if zone := request.GET.get('zone'):
        filters['zone__code'] = zone
    
    if property_type := request.GET.get('property_type'):
        filters['property_type__code'] = property_type
    
    if status := request.GET.get('status'):
        filters['status'] = status
    
    if min_value := request.GET.get('min_value'):
        filters['assessed_value__gte'] = float(min_value)
    
    # Get properties with proper field names
    properties = Property.objects.filter(**filters).select_related('zone', 'property_type').values(
        'id', '', 'address', 'latitude', 'longitude',
        'zone__name', 'property_type__name', 'assessed_value',
        'total_area', 'status', 'district', 'street', 'postcode',
        'region', 'gpsname', 'market_value', 'built_up_area',
        'floor_count', 'year_built'
    )
    
    # Convert Decimal to float for JSON serialization
    property_list = []
    for prop in properties:
        prop_dict = dict(prop)
        # Convert Decimal fields
        for field in ['assessed_value', 'market_value', 'total_area', 'built_up_area']:
            if prop_dict.get(field):
                prop_dict[field] = float(prop_dict[field])
        property_list.append(prop_dict)
    
    return JsonResponse(property_list, safe=False)




# @api_view(['GET'])
# def property_detail(request, identifier):
#     """Get detailed property information"""
#     try:
#         if identifier.isdigit():
#             property_obj = Property.objects.select_related('zone', 'property_type').get(id=int(identifier))
#         else:
#             property_obj = Property.objects.select_related('zone', 'property_type').get(property_id=identifier)
        
#         # Get owners
#         owners = property_obj.owners.values(
#             'owner_name', 'owner_type', 'phone_number', 
#             'email', 'ownership_percentage', 'is_primary_owner'
#         )
        
#         data = {
#             'id': property_obj.id,
#             # 'property_id': property_obj.property_id,
#             # 'address': property_obj.address,
#             # 'latitude': float(property_obj.latitude) if property_obj.latitude else None,
#             # 'longitude': float(property_obj.longitude) if property_obj.longitude else None,
#             # 'zone': property_obj.zone.name if property_obj.zone else None,
#             # 'zone_code': property_obj.zone.code if property_obj.zone else None,
#             'property_type': property_obj.property_type.name if property_obj.property_type else None,
#             'property_type_code': property_obj.property_type.code if property_obj.property_type else None,
#             'market_value': float(property_obj.market_value) if property_obj.market_value else None,
#             'assessed_value': float(property_obj.assessed_value) if property_obj.assessed_value else None,
#             'total_area': float(property_obj.total_area) if property_obj.total_area else None,
#             'built_up_area': float(property_obj.built_up_area) if property_obj.built_up_area else None,
#             'floor_count': property_obj.floor_count,
#             'year_built': property_obj.year_built,
#             'status': property_obj.status,
#             'district': property_obj.district,
#             'street': property_obj.street,
#             'postcode': property_obj.postcode,
#             'region': property_obj.region,
#             'gpsname': property_obj.gpsname,
#             'coordinates': property_obj.coordinates if property_obj.coordinates else None,
#             'nlat': float(property_obj.nlat) if property_obj.nlat else None,
#             'slat': float(property_obj.slat) if property_obj.slat else None,
#             'wlong': float(property_obj.wlong) if property_obj.wlong else None,
#             'elong': float(property_obj.elong) if property_obj.elong else None,
#             'owners': list(owners),
#             'payment_rate': 85.5,  # This should be calculated from your payment data
#             'total_revenue': 0,  # Calculate from bills/payments
#             'paid_bills': 0,  # Calculate from bills
#             'overdue_bills': 0,  # Calculate from bills
#             'bills_count': 0,  # Calculate from bills
#         }
        
#         return JsonResponse(data)
#     except Property.DoesNotExist:
#         return JsonResponse({'error': 'Property not found'}, status=404)

@api_view(['GET'])
def zones_list(request):
    """Get zones data"""
    zones = Zone.objects.annotate(
        property_count=Count('properties')
    ).values(
        'id', 'code', 'name', 'zone_type', 'property_count'
    )
    
    return JsonResponse(list(zones), safe=False)

# In your views.py
@api_view(['GET'])
def zones_geojson(request):
    """Get zones as GeoJSON with proper validation"""
    try:
        zones = Zone.objects.all()
        
        features = []
        for zone in zones:
            if zone.geom:
                # Ensure the geometry is valid GeoJSON
                feature = {
                    "type": "Feature",
                    "id": zone.id,
                    "geometry": json.loads(zone.geom.geojson) if hasattr(zone.geom, 'geojson') else None,
                    "properties": {
                        "id": zone.id,
                        "name": zone.name,
                        "code": zone.code,
                        "zone_type": zone.zone_type or "",
                        "color": "#0dae48",
                        "description": zone.description or "",
                        "property_count": zone.properties.count(),
                        "total_revenue": 0  # Update with actual revenue calculation
                    }
                }
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return JsonResponse(geojson, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e), "message": "Invalid GeoJSON data"}, status=500)

@api_view(['GET'])
def districts_geojson(request):
    """Get districts as GeoJSON with proper validation"""
    try:
        districts = District.objects.all()
        
        features = []
        for district in districts:
            if district.geom:
                feature = {
                    "type": "Feature",
                    "id": district.id,
                    "geometry": json.loads(district.geom.geojson) if hasattr(district.geom, 'geojson') else None,
                    "properties": {
                        "id": district.id,
                        "name": district.name,
                        "region": district.region or "",
                        "property_count": district.properties.count(),
                        "total_revenue": 0  # Update with actual revenue calculation
                    }
                }
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return JsonResponse(geojson, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e), "message": "Invalid GeoJSON data"}, status=500)

@api_view(['GET'])
def zones_performance(request):
    """Get zone performance data"""
    from django.db.models import Count, Sum
    
    zones = Zone.objects.annotate(
        property_count=Count('properties'),
        total_value=Sum('properties__assessed_value'),
        avg_value=Avg('properties__assessed_value'),
        collection_rate=Avg('properties__assessed_value')  # Placeholder - replace with actual calculation
    ).values(
        'id', 'name', 'property_count', 'total_value', 'avg_value', 'collection_rate'
    )
    
    # Convert Decimal to float
    zones_list = []
    for zone in zones:
        zone_dict = dict(zone)
        for field in ['total_value', 'avg_value', 'collection_rate']:
            if zone_dict.get(field):
                zone_dict[field] = float(zone_dict[field])
        zones_list.append(zone_dict)
    
    return JsonResponse(zones_list, safe=False)

@api_view(['GET'])
def districts_list(request):
    """Get districts data"""
    districts = District.objects.annotate(
        # property_count=Count('properties')
    ).values(
        'id', 'district', 'district_code',
    )
    
    return JsonResponse(list(districts), safe=False)

@api_view(['GET'])
def property_types_list(request):
    """Get property types"""
    types = PropertyType.objects.values('id', 'name', 'code', 'base_rate')
    
    # Convert Decimal to float
    types_list = []
    for type_obj in types:
        type_dict = dict(type_obj)
        type_dict['base_rate'] = float(type_dict['base_rate']) if type_dict['base_rate'] else None
        types_list.append(type_dict)
    
    return JsonResponse(types_list, safe=False)

# @api_view(['GET'])
# def search_properties(request):
#     """Search properties by various criteria"""
#     query = request.GET.get('q', '')
    
#     if len(query) < 2:
#         return JsonResponse([], safe=False)
    
#     properties = Property.objects.filter(
        
#         Q(address__icontains=query) |
#         Q(street__icontains=query) |
#         Q(gpsname__icontains=query) |
#         Q(district__icontains=query) |
#         Q(region__icontains=query)
#     ).select_related('zone', 'property_type').values(
#         'id', 'address', 'latitude', 'longitude',
#         'zone__name', 'district'
#     )[:20]
    
#     # Convert Decimal to float
#     properties_list = []
#     for prop in properties:
#         prop_dict = dict(prop)
#         if prop_dict.get('assessed_value'):
#             prop_dict['assessed_value'] = float(prop_dict['assessed_value'])
#         properties_list.append(prop_dict)
    
#     return JsonResponse(properties_list, safe=False)

@api_view(['GET'])
def heatmap_data(request):
    """Get data for heatmap visualization"""
    properties = Property.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        assessed_value__gt=0
    ).values('latitude', 'longitude', 'assessed_value')
    
    # Convert to list of points with intensity
    points = []
    for prop in properties:
        if prop['latitude'] and prop['longitude']:
            try:
                points.append({
                    'latitude': float(prop['latitude']),
                    'longitude': float(prop['longitude']),
                    'revenue_intensity': float(prop['assessed_value']) / 1000000
                })
            except (TypeError, ValueError):
                continue
    
    return JsonResponse(points, safe=False)

@api_view(['GET'])
def map_analytics(request):
    """Get analytics data for the map"""
    from django.db.models import Count, Sum, Avg
    
    # Total properties
    total_properties = Property.objects.count()
    
    # Active properties
    active_properties = Property.objects.filter(status='active').count()
    
    # Total revenue (calculated from assessed values as placeholder)
    total_revenue = Property.objects.aggregate(
        total=Sum('assessed_value')
    )['total'] or 0
    
    # Collection rate (placeholder - should be calculated from actual payments)
    collection_rate = 75.5
    
    # Zone stats
    zone_stats = Zone.objects.annotate(
        property_count=Count('properties'),
        total_value=Sum('properties__assessed_value')
    ).values('name', 'property_count', 'total_value')
    
    # Convert to float
    zone_stats_list = []
    for zone in zone_stats:
        zone_dict = dict(zone)
        zone_dict['total_value'] = float(zone_dict['total_value']) if zone_dict['total_value'] else 0
        zone_stats_list.append(zone_dict)
    
    data = {
        'total_properties': total_properties,
        'active_properties': active_properties,
        'total_revenue': float(total_revenue),
        'collection_rate': collection_rate,
        'zone_stats': zone_stats_list
    }
    
    return JsonResponse(data)




# In your views.py
@api_view(['GET'])
def property_detail(request, identifier):
    """Get detailed property information"""
    try:
        if identifier.isdigit():
            property_obj = Property.objects.select_related('zone', 'property_type').get(id=int(identifier))
        else:
            property_obj = Property.objects.select_related('zone', 'property_type').get(id=identifier)
        
        data = {
            'id': property_obj.id,
            'property_id': str(property_obj.id),  # Using id as property_id
            'address': property_obj.address or '',
            'street': property_obj.street or '',
            'district': property_obj.district or '',
            'zone': property_obj.zone.name if property_obj.zone else '',
            'zone_code': property_obj.zone.code if property_obj.zone else '',
            'property_type': property_obj.property_type.name if property_obj.property_type else '',
            'property_type_code': property_obj.property_type.code if property_obj.property_type else '',
            'area_in_me': float(property_obj.area_in_me) if property_obj.area_in_me else None,
            'gpsname': property_obj.gpsname or '',
            'region': property_obj.region or '',
            'postcode': property_obj.postcode or '',
            'status': 'active',  # Default status since your model doesn't have status field
            'latitude': float(property_obj.latitude) if property_obj.latitude else None,
            'longitude': float(property_obj.longitude) if property_obj.longitude else None,
            'nlat': float(property_obj.nlat) if property_obj.nlat else None,
            'slat': float(property_obj.slat) if property_obj.slat else None,
            'wlong': float(property_obj.wlong) if property_obj.wlong else None,
            'elong': float(property_obj.elong) if property_obj.elong else None,
            'area': float(property_obj.area) if property_obj.area else None,
            'addressv1': property_obj.addressv1 or '',
            'geometry': {
                'type': 'Point' if property_obj.latitude and property_obj.longitude else 'Unknown',
                'coordinates': {
                    'latitude': float(property_obj.latitude) if property_obj.latitude else None,
                    'longitude': float(property_obj.longitude) if property_obj.longitude else None
                }
            },
            'payment_rate': 0,  # You'll need to calculate this from your payment data
            'marker_color': '#0dae48',  # Default color
            'assessed_value': 0,  # Your model doesn't have this field
        }
        
        return JsonResponse(data)
    except Property.DoesNotExist:
        return JsonResponse({'error': 'Property not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@api_view(['GET'])
def search_properties(request):
    """Search properties by various fields"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Search in multiple fields
    properties = Property.objects.filter(
        Q(address__icontains=query) |
        Q(street__icontains=query) |
        Q(district__icontains=query) |
        Q(region__icontains=query) |
        Q(gpsname__icontains=query) |
        Q(postcode__icontains=query) |
        Q(zone__name__icontains=query) |
        Q(property_type__name__icontains=query)
    ).select_related('zone', 'property_type')[:50]  # Limit results
    
    results = []
    for prop in properties:
        if prop.latitude and prop.longitude:
            results.append({
                'id': prop.id,
                'property_id': str(prop.id),
                'address': prop.address or '',
                'street': prop.street or '',
                'district': prop.district or '',
                'zone': prop.zone.name if prop.zone else '',
                'latitude': float(prop.latitude),
                'longitude': float(prop.longitude)
            })
    
    return JsonResponse(results, safe=False)