import traceback
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Q, F
from core.models import Polygon, BlockBoundary, PropertyRate, Business, Session, Bill
import json
from django.utils import timezone
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon as GISPolygon
from decimal import Decimal
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Helper function to convert Decimal to float
def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@login_required
def property_mapping(request):
    """Main GIS mapping view"""
    # Get unique zones from property rates
    zones = PropertyRate.objects.filter(
        area_zone__isnull=False,
        area_zone__gt=''
    ).values('area_zone').distinct()
    
    # Get unique property types from property rates
    property_types = PropertyRate.objects.filter(
        prop_type__isnull=False,
        prop_type__gt=''
    ).values('prop_type').distinct()
    
    # Get unique districts from property rates (suburb field)
    districts = PropertyRate.objects.filter(
        suburb__isnull=False,
        suburb__gt=''
    ).values('suburb').distinct()
    
    context = {
        'page_title': 'GIS Property Mapping',
        'active_page': 'gis_mapping',
        'zones': [{'id': z['area_zone'], 'name': z['area_zone'], 'code': z['area_zone'].lower().replace(' ', '_')} for z in zones],
        'property_types': [{'id': p['prop_type'], 'name': p['prop_type'], 'code': p['prop_type'].lower().replace(' ', '_')} for p in property_types],
        'districts': [{'id': d['suburb'], 'district': d['suburb']} for d in districts],
    }
    return render(request, 'core/main/map/map.html', context)

@login_required
def get_properties_geojson(request):
    """API endpoint to get properties as GeoJSON"""
    try:
        # Get filter parameters
        zone_filter = request.GET.get('zone', '')
        property_type_filter = request.GET.get('property_type', '')
        status_filter = request.GET.get('status', '')
        district_filter = request.GET.get('district', '')
        
        # Start with all polygons
        polygons = Polygon.objects.filter(deleted_at__isnull=True)
        
        # Apply filters by joining with property_rates
        if zone_filter or property_type_filter or district_filter:
            # Get property rates with filters
            property_rates = PropertyRate.objects.all()
            
            if zone_filter:
                property_rates = property_rates.filter(area_zone__icontains=zone_filter)
            if property_type_filter:
                property_rates = property_rates.filter(prop_type__icontains=property_type_filter)
            if district_filter:
                property_rates = property_rates.filter(suburb__icontains=district_filter)
            
            # Get polygon IDs from filtered property rates
            polygon_ids = property_rates.values_list('polygon_id', flat=True).distinct()
            polygons = polygons.filter(id__in=polygon_ids)
        
        # Apply status filter directly on polygons
        if status_filter:
            polygons = polygons.filter(status=status_filter)
        
        # Limit for performance
        polygons = polygons[:500]
        
        logger.info(f"Processing {polygons.count()} properties")
        
        # Create GeoJSON FeatureCollection
        features = []
        
        for polygon in polygons:
            geometry = None
            geometry_type = None
            
            # Get property rate data
            property_rate = PropertyRate.objects.filter(polygon_id=polygon.id).first()
            
            # Try to get geometry from geom field
            if polygon.geom:
                try:
                    if hasattr(polygon.geom, 'geojson'):
                        geometry = json.loads(polygon.geom.geojson)
                        geometry_type = geometry.get('type')
                        logger.debug(f"Polygon {polygon.id}: Successfully parsed geom")
                    else:
                        # Try to parse as string
                        geom_str = str(polygon.geom)
                        try:
                            geom = GEOSGeometry(geom_str)
                            geometry = json.loads(geom.geojson)
                            geometry_type = geometry.get('type')
                        except Exception:
                            pass
                except Exception as geom_error:
                    logger.warning(f"Polygon {polygon.id}: Error processing geom: {geom_error}")
            
            # Fallback: Use point coordinates if available
            if not geometry and polygon.latitude and polygon.longitude:
                try:
                    geometry = {
                        "type": "Point",
                        "coordinates": [
                            float(polygon.longitude),
                            float(polygon.latitude)
                        ]
                    }
                    geometry_type = "Point"
                except (ValueError, TypeError):
                    pass
            
            # Skip if no geometry
            if not geometry:
                logger.debug(f"Polygon {polygon.id}: Skipping - no valid geometry")
                continue
            
            # Prepare property information
            property_info = {
                "id": polygon.id,
                "property_id": f"{polygon.division}-{polygon.block}-{polygon.property}",
                "address": property_rate.prop_address if property_rate else polygon.location or "No address",
                "property_type": property_rate.prop_type if property_rate else "Unknown",
                "zone": property_rate.area_zone if property_rate else "Unknown",
                "zone_code": (property_rate.area_zone.lower().replace(' ', '_') if property_rate and property_rate.area_zone else ""),
                "district": property_rate.suburb if property_rate else "Unknown",
                "region": property_rate.area_zone if property_rate else "Unknown",
                "status": polygon.status,
                "has_geom": polygon.geom is not None,
                "has_point": polygon.latitude is not None and polygon.longitude is not None,
                "geometry_type": geometry_type,
                "geometry_source": "geom" if polygon.geom else "coordinates"
            }
            
            # Add numeric coordinates if available
            if polygon.latitude and polygon.longitude:
                try:
                    property_info["latitude"] = float(polygon.latitude)
                    property_info["longitude"] = float(polygon.longitude)
                except (ValueError, TypeError):
                    pass
            
            # Add valuation data if available
            if property_rate:
                if property_rate.rateable_value:
                    property_info["assessed_value"] = float(property_rate.rateable_value)
                if property_rate.rate_input:
                    property_info["total_area"] = float(property_rate.rate_input)
                if property_rate.prop_name:
                    property_info["property_name"] = property_rate.prop_name
                if property_rate.surname:
                    property_info["owner_name"] = f"{property_rate.title or ''} {property_rate.surname} {property_rate.first_name or ''}".strip()
            
            # Add division, block, property info
            property_info["division"] = polygon.division
            property_info["block"] = polygon.block
            property_info["property_no"] = polygon.property
            
            # Create feature
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": property_info
            }
            features.append(feature)
        
        # Create GeoJSON response
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_properties": len(features),
                "with_geom_field": len([f for f in features if f['properties']['has_geom']]),
                "with_point_coordinates": len([f for f in features if f['properties']['has_point']]),
                "timestamp": timezone.now().isoformat(),
                "filters_applied": {
                    "zone": zone_filter,
                    "property_type": property_type_filter,
                    "status": status_filter,
                    "district": district_filter
                }
            }
        }
        
        logger.info(f"Generated GeoJSON with {len(features)} features")
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False, 'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in get_properties_geojson: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            "error": "Failed to generate GeoJSON",
            "details": str(e),
            "traceback": traceback.format_exc()
        }, status=500)

@login_required
def get_zones_geojson(request):
    """API endpoint to get zones as GeoJSON using block boundaries"""
    try:
        # Use block boundaries as zones
        boundaries = BlockBoundary.objects.all().exclude(geom__isnull=True)
        
        features = []
        for boundary in boundaries:
            if not boundary.geom:
                continue
            
            try:
                geometry = json.loads(boundary.geom.geojson)
            except Exception as e:
                logger.warning(f"Failed to parse geometry for boundary {boundary.id}: {e}")
                continue
            
            # Count properties in this block boundary
            property_count = boundary.property_count or 0
            
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": boundary.id,
                    "name": f"Block {boundary.block}",
                    "code": f"BLK_{boundary.block}",
                    "zone_type": "block",
                    "property_count": property_count,
                    "division": boundary.division,
                    "block": boundary.block,
                    "complete_count": boundary.complete_count or 0,
                    "assessed_count": boundary.assessed_count or 0,
                    "color": get_zone_color("block")
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_zones": len(features),
                "timestamp": timezone.now().isoformat()
            }
        }
        
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False})
    
    except Exception as e:
        logger.error(f"Error in get_zones_geojson: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

def get_zone_color(zone_type):
    """Get color for zone based on type"""
    colors = {
        'residential': '#0dae48',      # Green
        'commercial': '#9c27b0',       # Purple
        'industrial': '#ff9800',       # Orange
        'agricultural': '#228B22',     # Forest Green
        'mixed_use': '#ff5722',        # Deep Orange
        'block': '#6c757d',            # Gray for blocks
        'mixed': '#ff5722',
    }
    return colors.get(zone_type.lower(), '#0dae48')

@login_required
def get_districts_geojson(request):
    """API endpoint to get districts as GeoJSON (grouped by division)"""
    try:
        # Group block boundaries by division
        divisions = BlockBoundary.objects.values('division').distinct().exclude(division__isnull=True)
        
        features = []
        for div in divisions:
            boundaries = BlockBoundary.objects.filter(division=div['division']).exclude(geom__isnull=True)
            
            # For each division, we could create a union of geometries
            # For simplicity, we'll create separate features for each block
            for boundary in boundaries:
                if not boundary.geom:
                    continue
                
                try:
                    geometry = json.loads(boundary.geom.geojson)
                except Exception as e:
                    logger.warning(f"Failed to parse geometry for boundary {boundary.id}: {e}")
                    continue
                
                # Get property rates in this division
                property_rates = PropertyRate.objects.filter(
                    division=div['division']
                ).count()
                
                feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": div['division'],
                        "name": f"Division {div['division']}",
                        "region": "",
                        "property_count": property_rates,
                        "block": boundary.block,
                        "division": div['division'],
                        "color": '#6c757d'
                    }
                }
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_districts": len(features),
                "timestamp": timezone.now().isoformat()
            }
        }
        
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False})
    
    except Exception as e:
        logger.error(f"Error in get_districts_geojson: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_bops_geojson(request):
    """API endpoint to get Businesses as GeoJSON"""
    try:
        # Get all businesses
        businesses = Business.objects.filter(is_deleted=False)
        
        # Apply filters if needed
        business_type = request.GET.get('business_type', '')
        if business_type:
            businesses = businesses.filter(business_type__slug=business_type)
        
        # Limit for performance
        businesses = businesses[:500]
        
        features = []
        for business in businesses:
            geometry = None
            
            # Try to get geometry from lat/lng
            if business.lat and business.lng:
                try:
                    lat = float(business.lat)
                    lng = float(business.lng)
                    geometry = {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    }
                except (ValueError, TypeError):
                    pass
            
            # Try centroid field if available
            if not geometry and hasattr(business, 'centroid') and business.centroid:
                centroid_value = business.centroid
                if isinstance(centroid_value, str) and ',' in centroid_value:
                    try:
                        parts = centroid_value.split(',')
                        if len(parts) == 2:
                            first, second = float(parts[0].strip()), float(parts[1].strip())
                            # Assume lat,lon format
                            geometry = {"type": "Point", "coordinates": [second, first]}
                    except (ValueError, TypeError):
                        pass
            
            # Try geometry field
            if not geometry and hasattr(business, 'geometry') and business.geometry:
                try:
                    if hasattr(business.geometry, 'geojson'):
                        geometry = json.loads(business.geometry.geojson)
                except Exception:
                    pass
            
            # Skip if no valid geometry
            if not geometry:
                continue
            
            # Create properties
            properties = {
                "id": business.id,
                "account_number": business.account_number or '',
                "business_name": business.business_name or '',
                "business_category": business.business_category or '',
                "business_class": business.business_class or '',
                "location": business.location or '',
                "address": business.address or '',
                "division": business.division or '',
                "block": business.block or '',
                "owner_name": business.owner_name or '',
                "phone_number": business.phone_number or '',
                "email": business.email or '',
                "business_type": business.business_type.name if business.business_type else '',
                "business_sub_type": business.business_sub_type.name if business.business_sub_type else '',
                "flat_rate": float(business.flat_rate) if business.flat_rate else 0,
            }
            
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total": len(features),
                "total_records": businesses.count(),
                "timestamp": timezone.now().isoformat()
            }
        }
        
        logger.info(f"Generated {len(features)} business features")
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False, 'default': decimal_to_float})
        
    except Exception as e:
        logger.error(f"Error in get_bops_geojson: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_property_details(request, property_id):
    """API endpoint to get detailed property information"""
    try:
        # Try to get polygon by id
        try:
            polygon = Polygon.objects.get(id=int(property_id))
        except (Polygon.DoesNotExist, ValueError):
            # Try to get by division-block-property format
            parts = property_id.split('-')
            if len(parts) == 3:
                try:
                    polygon = Polygon.objects.get(
                        division=int(parts[0]),
                        block=int(parts[1]),
                        property=int(parts[2])
                    )
                except Polygon.DoesNotExist:
                    return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
            else:
                return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
        
        # Get property rate data
        property_rate = PropertyRate.objects.filter(polygon_id=polygon.id).first()
        
        # Get session data
        session = Session.objects.filter(
            polygon_id=polygon.id,
            deleted_at__isnull=True
        ).order_by('-created_at').first()
        
        # Get bills
        bills = Bill.objects.filter(
            polygon_id=polygon.id,
            deleted_at__isnull=True
        )
        
        # Calculate statistics
        total_bills = bills.count()
        paid_bills = bills.filter(status='paid').count()
        total_amount = bills.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = bills.aggregate(total=Sum('amount_paid'))['total'] or 0
        overdue_bills = bills.filter(status='overdue').count()
        payment_rate = (total_paid / total_amount * 100) if total_amount > 0 else 0
        
        # Parse geometry
        geometry_info = None
        if polygon.geom:
            try:
                geometry_info = json.loads(polygon.geom.geojson)
            except Exception:
                pass
        
        # Build property data
        property_data = {
            "id": polygon.id,
            "property_id": f"{polygon.division}-{polygon.block}-{polygon.property}",
            "address": property_rate.prop_address if property_rate else polygon.location or "",
            "street": property_rate.street_name if property_rate else "",
            "district": property_rate.suburb if property_rate else "",
            "region": property_rate.area_zone if property_rate else "",
            "postcode": "",
            "property_type": property_rate.prop_type if property_rate else "Unknown",
            "zone": property_rate.area_zone if property_rate else "Unknown",
            "status": polygon.status,
            "total_area": float(property_rate.rate_input) if property_rate and property_rate.rate_input else None,
            "built_up_area": None,
            "floor_count": None,
            "year_built": None,
            "latitude": float(polygon.latitude) if polygon.latitude else None,
            "longitude": float(polygon.longitude) if polygon.longitude else None,
            "geometry": geometry_info,
            "has_geom": polygon.geom is not None,
            "has_point": polygon.latitude is not None and polygon.longitude is not None,
            "owner_name": f"{property_rate.title or ''} {property_rate.surname or ''} {property_rate.first_name or ''}".strip() if property_rate else "",
            "owner_contact": property_rate.mobile_number if property_rate else "",
            "owner_email": property_rate.email if property_rate else "",
            "assessed_value": float(property_rate.rateable_value) if property_rate and property_rate.rateable_value else 0,
            "division": polygon.division,
            "block": polygon.block,
            "property_no": polygon.property,
            "session_status": session.status if session else None,
            "session_submitted": session.submitted_at if session else None,
            "total_bills": total_bills,
            "paid_bills": paid_bills,
            "overdue_bills": overdue_bills,
            "total_amount": float(total_amount),
            "total_paid": float(total_paid),
            "payment_rate": round(payment_rate, 2)
        }
        
        return JsonResponse({"data": property_data, "status": "success"}, json_dumps_params={'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in get_property_details: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def search_properties(request):
    """API endpoint for property search"""
    try:
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return JsonResponse({"results": [], "status": "success"})
        
        # Search in polygons
        polygon_filter = Q()
        
        # Search by location
        polygon_filter |= Q(location__icontains=query)
        
        # Search by division, block, property
        if query.isdigit():
            polygon_filter |= Q(division=int(query))
            polygon_filter |= Q(block=int(query))
            polygon_filter |= Q(property=int(query))
        
        polygons = Polygon.objects.filter(polygon_filter, deleted_at__isnull=True)[:50]
        
        # Search in property rates
        property_rate_filter = Q()
        property_rate_filter |= Q(prop_address__icontains=query)
        property_rate_filter |= Q(street_name__icontains=query)
        property_rate_filter |= Q(suburb__icontains=query)
        property_rate_filter |= Q(area_zone__icontains=query)
        property_rate_filter |= Q(surname__icontains=query)
        property_rate_filter |= Q(first_name__icontains=query)
        property_rate_filter |= Q(prop_name__icontains=query)
        
        property_rates = PropertyRate.objects.filter(property_rate_filter)[:50]
        
        # Combine results
        results = []
        processed_ids = set()
        
        # Add polygon results
        for polygon in polygons:
            if polygon.id in processed_ids:
                continue
            processed_ids.add(polygon.id)
            
            property_rate = PropertyRate.objects.filter(polygon_id=polygon.id).first()
            
            result = {
                "id": polygon.id,
                "display_id": f"{polygon.division}-{polygon.block}-{polygon.property}",
                "address": property_rate.prop_address if property_rate else polygon.location or "",
                "district": property_rate.suburb if property_rate else "",
                "zone": property_rate.area_zone if property_rate else "",
                "zone_code": property_rate.area_zone.lower().replace(' ', '_') if property_rate and property_rate.area_zone else "",
                "property_type": property_rate.prop_type if property_rate else "",
                "property_type_code": property_rate.prop_type.lower().replace(' ', '_') if property_rate and property_rate.prop_type else "",
                "latitude": float(polygon.latitude) if polygon.latitude else None,
                "longitude": float(polygon.longitude) if polygon.longitude else None,
                "has_geom": polygon.geom is not None,
                "has_point": polygon.latitude is not None and polygon.longitude is not None,
                "area": float(property_rate.rate_input) if property_rate and property_rate.rate_input else None,
                "area_in_me": None,
                "status": polygon.status,
                "division": polygon.division,
                "block": polygon.block,
                "property_no": polygon.property,
                "is_id_match": query.isdigit() and (polygon.id == int(query) or 
                                                    polygon.division == int(query) or
                                                    polygon.block == int(query) or
                                                    polygon.property == int(query))
            }
            
            # Determine match type
            if result["is_id_match"]:
                result["match_type"] = "id"
            elif property_rate and property_rate.prop_address and query.lower() in property_rate.prop_address.lower():
                result["match_type"] = "address"
            elif property_rate and property_rate.suburb and query.lower() in property_rate.suburb.lower():
                result["match_type"] = "district"
            elif property_rate and property_rate.area_zone and query.lower() in property_rate.area_zone.lower():
                result["match_type"] = "zone"
            elif polygon.location and query.lower() in polygon.location.lower():
                result["match_type"] = "location"
            
            results.append(result)
        
        # Add property rate results that aren't already in polygons
        for property_rate in property_rates:
            if property_rate.polygon_id and property_rate.polygon_id in processed_ids:
                continue
            
            # Try to get the polygon
            polygon = None
            if property_rate.polygon_id:
                try:
                    polygon = Polygon.objects.get(id=property_rate.polygon_id)
                except Polygon.DoesNotExist:
                    pass
            
            result = {
                "id": property_rate.id,
                "display_id": f"PR-{property_rate.id}",
                "address": property_rate.prop_address or "",
                "district": property_rate.suburb or "",
                "zone": property_rate.area_zone or "",
                "zone_code": property_rate.area_zone.lower().replace(' ', '_') if property_rate.area_zone else "",
                "property_type": property_rate.prop_type or "",
                "property_type_code": property_rate.prop_type.lower().replace(' ', '_') if property_rate.prop_type else "",
                "latitude": float(polygon.latitude) if polygon and polygon.latitude else None,
                "longitude": float(polygon.longitude) if polygon and polygon.longitude else None,
                "has_geom": polygon and polygon.geom is not None,
                "has_point": polygon and polygon.latitude is not None and polygon.longitude is not None,
                "area": float(property_rate.rate_input) if property_rate.rate_input else None,
                "area_in_me": None,
                "status": polygon.status if polygon else "unknown",
                "division": property_rate.division,
                "block": property_rate.block,
                "property_no": None,
                "is_id_match": query.isdigit() and property_rate.id == int(query),
                "match_type": "valuation"
            }
            
            results.append(result)
        
        logger.info(f"Search for '{query}' found {len(results)} results")
        return JsonResponse({
            "results": results,
            "status": "success",
            "query": query,
            "count": len(results)
        }, json_dumps_params={'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in search_properties: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            "error": "Search failed",
            "details": str(e),
            "status": "error"
        }, status=500)

@login_required
def get_map_stats(request):
    """API endpoint for map statistics"""
    try:
        # Property statistics
        total_properties = Polygon.objects.filter(deleted_at__isnull=True).count()
        
        properties_with_geom = Polygon.objects.filter(
            geom__isnull=False,
            deleted_at__isnull=True
        ).count()
        
        properties_with_point = Polygon.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            deleted_at__isnull=True
        ).count()
        
        # Block boundaries statistics
        blocks_with_boundaries = BlockBoundary.objects.filter(
            geom__isnull=False
        ).count()
        
        # Property rates statistics
        property_rates_count = PropertyRate.objects.count()
        
        # Business statistics
        businesses_count = Business.objects.filter(is_deleted=False).count()
        businesses_with_coords = Business.objects.filter(
            lat__isnull=False,
            lng__isnull=False
        ).count()
        
        stats = {
            "total_properties": total_properties,
            "properties_with_geom": properties_with_geom,
            "properties_with_point": properties_with_point,
            "blocks_with_boundaries": blocks_with_boundaries,
            "property_rates_count": property_rates_count,
            "businesses_count": businesses_count,
            "businesses_with_coords": businesses_with_coords,
            "timestamp": timezone.now().isoformat()
        }
        
        return JsonResponse({"data": stats, "status": "success"}, json_dumps_params={'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in get_map_stats: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_property_geometry(request, property_id):
    """API endpoint to get only property geometry"""
    try:
        # Try to get polygon by id
        try:
            polygon = Polygon.objects.get(id=int(property_id))
        except (Polygon.DoesNotExist, ValueError):
            # Try to get by division-block-property format
            parts = property_id.split('-')
            if len(parts) == 3:
                try:
                    polygon = Polygon.objects.get(
                        division=int(parts[0]),
                        block=int(parts[1]),
                        property=int(parts[2])
                    )
                except Polygon.DoesNotExist:
                    return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
            else:
                return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
        
        geometry = None
        if polygon.geom:
            try:
                geometry = json.loads(polygon.geom.geojson)
            except Exception as e:
                logger.warning(f"Failed to parse geometry for property {property_id}: {e}")
        
        return JsonResponse({
            "property_id": f"{polygon.division}-{polygon.block}-{polygon.property}",
            "geometry": geometry,
            "has_geometry": bool(geometry),
            "status": "success"
        }, json_dumps_params={'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in get_property_geometry: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_properties_without_geometry(request):
    """API endpoint to get properties without geometry (for debugging)"""
    try:
        limit = int(request.GET.get('limit', 10))
        
        # Properties without geometry
        properties_without_geom = Polygon.objects.filter(
            geom__isnull=True,
            deleted_at__isnull=True
        )[:limit].values('id', 'location', 'division', 'block', 'property', 'status')
        
        # Properties with bad geometry
        properties_with_bad_geom = Polygon.objects.filter(
            geom__isnull=False,
            deleted_at__isnull=True
        ).exclude(geom='')[:limit].values('id', 'location', 'division', 'block', 'property', 'status')
        
        # Property rates without polygon association
        property_rates_without_polygon = PropertyRate.objects.filter(
            polygon_id__isnull=True
        )[:limit].values('id', 'prop_address', 'suburb', 'division', 'block')
        
        return JsonResponse({
            "without_geometry": list(properties_without_geom),
            "with_bad_geometry": list(properties_with_bad_geom),
            "property_rates_without_polygon": list(property_rates_without_polygon),
            "status": "success"
        }, json_dumps_params={'default': decimal_to_float})
    
    except Exception as e:
        logger.error(f"Error in get_properties_without_geometry: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)