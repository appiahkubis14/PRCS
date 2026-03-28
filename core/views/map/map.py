# views.py
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.contrib.gis.geos import GEOSGeometry
from rest_framework.decorators import api_view
from core.models import Polygon, BlockBoundary, Session, Bill, Business, PropertyRate
import json
from decimal import Decimal

# Helper function to convert Decimal to float for JSON serialization
def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@api_view(['GET'])
def properties_list(request):
    """Get filtered properties/polygons list"""
    # Get filters from query parameters
    filters = {}
    
    if district := request.GET.get('district'):
        # Since district isn't directly in Polygon, filter by location or other fields
        filters['location__icontains'] = district
    
    if zone := request.GET.get('zone'):
        # Filter by area_zone if available, otherwise ignore
        filters['area_zone__icontains'] = zone
    
    if property_type := request.GET.get('property_type'):
        # Filter by prop_type from property_rates if available
        # This would require a join or subquery
        pass
    
    if status := request.GET.get('status'):
        filters['status'] = status
    
    if min_value := request.GET.get('min_value'):
        # This would need to be handled with property_rates
        pass
    
    # Get polygons with basic info
    polygons = Polygon.objects.filter(**filters).values(
        'id', 'location', 'latitude', 'longitude', 'status',
        'division', 'block', 'property'
    )[:100]  # Limit to 100 for performance
    
    # Enhance with property rate data if available
    polygon_list = []
    for poly in polygons:
        poly_dict = dict(poly)
        
        # Get property rate data if exists
        property_rate = PropertyRate.objects.filter(
            polygon_id=poly['id']
        ).first()
        
        if property_rate:
            poly_dict['assessed_value'] = float(property_rate.rateable_value) if property_rate.rateable_value else 0
            poly_dict['market_value'] = float(property_rate.rateable_value) if property_rate.rateable_value else 0
            poly_dict['property_type'] = property_rate.prop_type or ''
            poly_dict['address'] = property_rate.prop_address or ''
            poly_dict['owner_name'] = property_rate.surname or ''
            poly_dict['street'] = property_rate.street_name or ''
            poly_dict['district'] = property_rate.suburb or ''
            poly_dict['region'] = property_rate.area_zone or ''
        else:
            poly_dict['assessed_value'] = 0
            poly_dict['market_value'] = 0
            poly_dict['property_type'] = ''
            poly_dict['address'] = poly.get('location', '')
            poly_dict['owner_name'] = ''
            poly_dict['street'] = ''
            poly_dict['district'] = ''
            poly_dict['region'] = ''
        
        # Convert Decimal fields
        for field in ['assessed_value', 'market_value']:
            if poly_dict.get(field):
                poly_dict[field] = float(poly_dict[field])
        
        polygon_list.append(poly_dict)
    
    return JsonResponse(polygon_list, safe=False, json_dumps_params={'default': decimal_to_float})

@api_view(['GET'])
def property_detail(request, identifier):
    """Get detailed property/polygon information"""
    try:
        # Try to get by id
        if identifier.isdigit():
            polygon_obj = Polygon.objects.get(id=int(identifier))
        else:
            # Try to get by property_id (division-block-property)
            parts = identifier.split('-')
            if len(parts) == 3:
                polygon_obj = Polygon.objects.get(
                    division=int(parts[0]),
                    block=int(parts[1]),
                    property=int(parts[2])
                )
            else:
                polygon_obj = Polygon.objects.get(id=identifier)
        
        # Get property rate data
        property_rate = PropertyRate.objects.filter(
            polygon_id=polygon_obj.id
        ).first()
        
        # Get session data if exists
        session = Session.objects.filter(
            polygon_id=polygon_obj.id,
            deleted_at__isnull=True
        ).order_by('-created_at').first()
        
        # Get bills for this polygon
        bills = Bill.objects.filter(
            polygon_id=polygon_obj.id,
            deleted_at__isnull=True
        )
        
        # Calculate payment statistics
        total_bills = bills.count()
        paid_bills = bills.filter(status='paid').count()
        total_amount = bills.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = bills.aggregate(total=Sum('amount_paid'))['total'] or 0
        overdue_bills = bills.filter(status='overdue').count()
        
        # Calculate payment rate
        payment_rate = (total_paid / total_amount * 100) if total_amount > 0 else 0
        
        data = {
            'id': polygon_obj.id,
            'property_id': f"{polygon_obj.division}-{polygon_obj.block}-{polygon_obj.property}",
            'address': property_rate.prop_address if property_rate else polygon_obj.location or '',
            'street': property_rate.street_name if property_rate else '',
            'district': property_rate.suburb if property_rate else '',
            'zone': property_rate.area_zone if property_rate else '',
            'property_type': property_rate.prop_type if property_rate else '',
            'owner_name': f"{property_rate.title or ''} {property_rate.surname or ''} {property_rate.first_name or ''}".strip() if property_rate else '',
            'owner_contact': property_rate.mobile_number if property_rate else '',
            'owner_email': property_rate.email if property_rate else '',
            'latitude': float(polygon_obj.latitude) if polygon_obj.latitude else None,
            'longitude': float(polygon_obj.longitude) if polygon_obj.longitude else None,
            'status': polygon_obj.status,
            'division': polygon_obj.division,
            'block': polygon_obj.block,
            'property_no': polygon_obj.property,
            'location': polygon_obj.location or '',
            'has_geometry': polygon_obj.geom is not None,
            'assessed_value': float(property_rate.rateable_value) if property_rate and property_rate.rateable_value else 0,
            'total_area': float(property_rate.rate_input) if property_rate and property_rate.rate_input else 0,
            'rate_code': float(property_rate.rate_code) if property_rate and property_rate.rate_code else 0,
            'tin_number': property_rate.tin_number if property_rate else '',
            'session_status': session.status if session else None,
            'session_submitted': session.submitted_at if session else None,
            'payment_rate': round(payment_rate, 2),
            'total_revenue': float(total_paid),
            'total_bills': total_bills,
            'paid_bills': paid_bills,
            'overdue_bills': overdue_bills,
            'bills': [
                {
                    'id': bill.id,
                    'bill_number': bill.bill_number,
                    'bill_type': bill.bill_type,
                    'amount': float(bill.amount),
                    'total_due': float(bill.total_due),
                    'amount_paid': float(bill.amount_paid),
                    'due_date': bill.due_date,
                    'status': bill.status,
                    'issued_at': bill.issued_at
                }
                for bill in bills
            ]
        }
        
        return JsonResponse(data, json_dumps_params={'default': decimal_to_float})
        
    except Polygon.DoesNotExist:
        return JsonResponse({'error': 'Property not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def zones_list(request):
    """Get zones/districts data from polygons"""
    # Since we don't have a Zone model, we'll group by area_zone from property_rates
    zones = PropertyRate.objects.filter(
        area_zone__isnull=False,
        area_zone__gt=''
    ).values('area_zone').annotate(
        property_count=Count('id', distinct=True),
        total_value=Sum('rateable_value')
    ).order_by('area_zone')
    
    zones_list = []
    for zone in zones:
        zones_list.append({
            'id': zone['area_zone'],
            'code': zone['area_zone'].lower().replace(' ', '_'),
            'name': zone['area_zone'],
            'zone_type': 'residential',  # Default
            'property_count': zone['property_count'],
            'total_value': float(zone['total_value']) if zone['total_value'] else 0
        })
    
    return JsonResponse(zones_list, safe=False, json_dumps_params={'default': decimal_to_float})

@api_view(['GET'])
def zones_geojson(request):
    """Get zones as GeoJSON using block boundaries"""
    try:
        # Use block boundaries for zones
        boundaries = BlockBoundary.objects.all()
        
        features = []
        for boundary in boundaries:
            if boundary.geom:
                feature = {
                    "type": "Feature",
                    "id": boundary.id,
                    "geometry": json.loads(boundary.geom.geojson) if hasattr(boundary.geom, 'geojson') else None,
                    "properties": {
                        "id": boundary.id,
                        "name": f"Block {boundary.block}",
                        "code": f"BLK_{boundary.block}",
                        "zone_type": "block",
                        "color": "#0dae48",
                        "description": f"Division: {boundary.division}, Block: {boundary.block}",
                        "property_count": boundary.property_count,
                        "complete_count": boundary.complete_count,
                        "assessed_count": boundary.assessed_count,
                        "total_revenue": 0  # Calculate from bills if needed
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
    """Get districts/divisions as GeoJSON"""
    try:
        # Group block boundaries by division
        divisions = BlockBoundary.objects.values('division').distinct()
        
        features = []
        for div in divisions:
            boundaries = BlockBoundary.objects.filter(division=div['division'])
            
            # Create a combined geometry for the division
            # For simplicity, return individual blocks with division grouping
            for boundary in boundaries:
                if boundary.geom:
                    feature = {
                        "type": "Feature",
                        "id": f"div_{boundary.division}",
                        "geometry": json.loads(boundary.geom.geojson) if hasattr(boundary.geom, 'geojson') else None,
                        "properties": {
                            "id": boundary.division,
                            "name": f"Division {boundary.division}",
                            "region": "",
                            "property_count": boundary.property_count,
                            "total_revenue": 0
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
    from django.db.models import Count, Sum, Avg
    
    # Get performance by area_zone from property_rates
    zones = PropertyRate.objects.filter(
        area_zone__isnull=False,
        area_zone__gt=''
    ).values('area_zone').annotate(
        property_count=Count('id', distinct=True),
        total_value=Sum('rateable_value'),
        avg_value=Avg('rateable_value')
    )
    
    zones_list = []
    for zone in zones:
        zones_list.append({
            'id': zone['area_zone'],
            'name': zone['area_zone'],
            'property_count': zone['property_count'],
            'total_value': float(zone['total_value']) if zone['total_value'] else 0,
            'avg_value': float(zone['avg_value']) if zone['avg_value'] else 0,
            'collection_rate': 0  # Placeholder
        })
    
    return JsonResponse(zones_list, safe=False, json_dumps_params={'default': decimal_to_float})

@api_view(['GET'])
def districts_list(request):
    """Get districts/divisions data"""
    districts = BlockBoundary.objects.values('division').distinct().annotate(
        property_count=Count('property_count')
    )
    
    districts_list = []
    for district in districts:
        districts_list.append({
            'id': district['division'],
            'district': f"Division {district['division']}",
            'district_code': f"DIV_{district['division']}",
            'property_count': district['property_count']
        })
    
    return JsonResponse(districts_list, safe=False)

@api_view(['GET'])
def property_types_list(request):
    """Get property types from property_rates"""
    types = PropertyRate.objects.filter(
        prop_type__isnull=False,
        prop_type__gt=''
    ).values('prop_type').annotate(
        count=Count('id')
    ).order_by('prop_type')
    
    types_list = []
    for type_obj in types:
        types_list.append({
            'id': type_obj['prop_type'],
            'name': type_obj['prop_type'],
            'code': type_obj['prop_type'].lower().replace(' ', '_'),
            'base_rate': 0,
            'count': type_obj['count']
        })
    
    return JsonResponse(types_list, safe=False)

@api_view(['GET'])
def search_properties(request):
    """Search properties by various criteria"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Search in polygons and property_rates
    polygons = Polygon.objects.filter(
        Q(location__icontains=query) |
        Q(division__icontains=query) |
        Q(block__icontains=query)
    ).values('id', 'location', 'latitude', 'longitude', 'division', 'block', 'property')[:50]
    
    # Enhance with property rate data
    results = []
    for poly in polygons:
        property_rate = PropertyRate.objects.filter(polygon_id=poly['id']).first()
        
        if poly['latitude'] and poly['longitude']:
            results.append({
                'id': poly['id'],
                'property_id': f"{poly['division']}-{poly['block']}-{poly['property']}",
                'address': property_rate.prop_address if property_rate else poly['location'] or '',
                'street': property_rate.street_name if property_rate else '',
                'district': property_rate.suburb if property_rate else '',
                'zone': property_rate.area_zone if property_rate else '',
                'owner_name': property_rate.surname if property_rate else '',
                'latitude': float(poly['latitude']),
                'longitude': float(poly['longitude'])
            })
    
    return JsonResponse(results, safe=False, json_dumps_params={'default': decimal_to_float})

@api_view(['GET'])
def heatmap_data(request):
    """Get data for heatmap visualization"""
    # Get polygons with coordinates and value data
    polygons = Polygon.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False
    ).select_related().values('id', 'latitude', 'longitude')
    
    points = []
    for poly in polygons:
        if poly['latitude'] and poly['longitude']:
            # Get property rate value if exists
            property_rate = PropertyRate.objects.filter(polygon_id=poly['id']).first()
            intensity = 0
            
            if property_rate and property_rate.rateable_value:
                intensity = float(property_rate.rateable_value) / 1000000
            else:
                # Default intensity based on polygon status
                polygon_obj = Polygon.objects.get(id=poly['id'])
                intensity = 1 if polygon_obj.status == 'complete' else 0.5
            
            points.append({
                'latitude': float(poly['latitude']),
                'longitude': float(poly['longitude']),
                'revenue_intensity': intensity,
                'property_id': poly['id']
            })
    
    return JsonResponse(points, safe=False, json_dumps_params={'default': decimal_to_float})

@api_view(['GET'])
def map_analytics(request):
    """Get analytics data for the map"""
    from django.db.models import Count, Sum, Avg
    
    # Total polygons/properties
    total_properties = Polygon.objects.filter(deleted_at__isnull=True).count()
    
    # Properties with completed assessment
    completed_properties = Polygon.objects.filter(
        status='complete',
        deleted_at__isnull=True
    ).count()
    
    # Properties with assessment
    assessed_properties = Polygon.objects.filter(
        accessed=True,
        deleted_at__isnull=True
    ).count()
    
    # Total revenue from bills
    total_revenue = Bill.objects.filter(
        deleted_at__isnull=True
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # Collection rate
    total_due = Bill.objects.filter(deleted_at__isnull=True).aggregate(total=Sum('total_due'))['total'] or 0
    collection_rate = (float(total_revenue) / float(total_due) * 100) if total_due > 0 else 0
    
    # Zone stats by area_zone
    zone_stats = PropertyRate.objects.filter(
        area_zone__isnull=False,
        area_zone__gt=''
    ).values('area_zone').annotate(
        property_count=Count('id', distinct=True),
        total_value=Sum('rateable_value')
    )[:10]
    
    zone_stats_list = []
    for zone in zone_stats:
        zone_stats_list.append({
            'name': zone['area_zone'],
            'property_count': zone['property_count'],
            'total_value': float(zone['total_value']) if zone['total_value'] else 0
        })
    
    # Block stats
    block_stats = BlockBoundary.objects.all()[:10]
    block_stats_list = []
    for block in block_stats:
        block_stats_list.append({
            'name': f"Block {block.block}",
            'property_count': block.property_count,
            'complete_count': block.complete_count,
            'assessed_count': block.assessed_count
        })
    
    data = {
        'total_properties': total_properties,
        'completed_properties': completed_properties,
        'assessed_properties': assessed_properties,
        'total_revenue': float(total_revenue),
        'collection_rate': round(collection_rate, 2),
        'zone_stats': zone_stats_list,
        'block_stats': block_stats_list
    }
    
    return JsonResponse(data, json_dumps_params={'default': decimal_to_float})