import traceback
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Q, F
from core.models import Property, Zone, District, Region, PropertyType, Bill, Payment, Bops
import json
from django.utils import timezone
from django.core.serializers import serialize
from django.contrib.gis.geos import GEOSGeometry, Polygon, Point
from decimal import Decimal
import logging

# Setup logger
logger = logging.getLogger(__name__)

@login_required
def property_mapping(request):
    """Main GIS mapping view"""
    zones = Zone.objects.all().values('id', 'name', 'code')
    property_types = PropertyType.objects.all().values('id', 'name', 'code')
    districts = District.objects.all().values('id', 'district')
    
    context = {
        'page_title': 'GIS Property Mapping',
        'active_page': 'gis_mapping',
        'zones': zones,
        'property_types': property_types,
        'districts': districts,
    }
    return render(request, 'core/main/map/map.html', context)

@login_required
def get_properties_geojson(request):
    """API endpoint to get properties as GeoJSON"""
    try:
        # Get filter parameters
        zone_filter = request.GET.get('zone', '')
        # property_type_filter = request.GET.get('property_type', '')
        status_filter = request.GET.get('status', '')
        district_filter = request.GET.get('district', '')
        
        # Start with all properties
        properties = Property.objects.all()
        
        # # Apply filters
        # if zone_filter:
        #     properties = properties.filter(zone__code=zone_filter)
        # if property_type_filter:
        #     properties = properties.filter(property_type__code=property_type_filter)
        # if status_filter:
        #     properties = properties.filter(status=status_filter)
        if district_filter:
            properties = properties.filter(district=district_filter)
        
        # Limit results for performance
        properties = properties
        
        logger.info(f"Processing {properties.count()} properties")
        
        # Create GeoJSON FeatureCollection
        features = []
        
        for property in properties:
            geometry = None
            geometry_type = None
            
            # Try to get geometry from geom field first
            if property.geom and str(property.geom).strip():
                try:
                    # Check if geom is valid GEOSGeometry
                    if hasattr(property.geom, 'geojson'):
                        geometry = json.loads(property.geom.geojson)
                        geometry_type = geometry.get('type')
                        logger.debug(f"Property {property.id}: Successfully parsed geom as GEOSGeometry")
                    else:
                        # Try to parse as string
                        geom_str = str(property.geom)
                        # Try to parse as WKT
                        try:
                            from django.contrib.gis.geos import GEOSGeometry
                            geom = GEOSGeometry(geom_str)
                            geometry = json.loads(geom.geojson)
                            geometry_type = geometry.get('type')
                            logger.debug(f"Property {property.id}: Parsed geom string as WKT")
                        except Exception as wkt_error:
                            logger.warning(f"Property {property.id}: Failed to parse geom as WKT: {wkt_error}")
                            
                            # Try to parse as GeoJSON string
                            try:
                                geom_dict = json.loads(geom_str)
                                if 'type' in geom_dict and 'coordinates' in geom_dict:
                                    geometry = geom_dict
                                    geometry_type = geom_dict.get('type')
                                    logger.debug(f"Property {property.id}: Parsed geom as GeoJSON string")
                                elif 'geometry' in geom_dict:
                                    geometry = geom_dict['geometry']
                                    geometry_type = geometry.get('type')
                                    logger.debug(f"Property {property.id}: Found geometry in GeoJSON dict")
                            except json.JSONDecodeError:
                                logger.warning(f"Property {property.id}: geom is not valid JSON: {geom_str[:100]}")
                except Exception as geom_error:
                    logger.warning(f"Property {property.id}: Error processing geom field: {geom_error}")
            
            # Fallback: Use point coordinates if available
            if not geometry and property.latitude and property.longitude:
                try:
                    geometry = {
                        "type": "Point",
                        "coordinates": [
                            float(property.longitude),
                            float(property.latitude)
                        ]
                    }
                    geometry_type = "Point"
                    logger.debug(f"Property {property.id}: Using lat/long as Point geometry")
                except (ValueError, TypeError) as point_error:
                    logger.warning(f"Property {property.id}: Invalid lat/long coordinates: {point_error}")
            
            # Additional fallback: Create polygon from bounding coordinates
            if not geometry and all([property.nlat, property.slat, property.wlong, property.elong]):
                try:
                    geometry = {
                        "type": "Polygon",
                        "coordinates": [[
                            [float(property.wlong), float(property.slat)],
                            [float(property.elong), float(property.slat)],
                            [float(property.elong), float(property.nlat)],
                            [float(property.wlong), float(property.nlat)],
                            [float(property.wlong), float(property.slat)]
                        ]]
                    }
                    geometry_type = "Polygon"
                    logger.debug(f"Property {property.id}: Created polygon from bounding coordinates")
                except (ValueError, TypeError) as bbox_error:
                    logger.warning(f"Property {property.id}: Invalid bounding coordinates: {bbox_error}")
            
            # Skip if no geometry could be created
            if not geometry:
                logger.debug(f"Property {property.id}: Skipping - no valid geometry data")
                continue
            
            # Prepare property information
            property_info = {
                "id": property.id,
                "property_id": f"PROP-{property.id}",
                "address": property.address or property.addressv1 or "No address",
                # "property_type": property.property_type.name if property.property_type else "Unknown",
                # "zone": property.zone.name if property.zone else "Unknown",
                # "zone_code": property.zone.code if property.zone else "",
                "district": property.district or "Unknown",
                "region": property.region or "Unknown",
                # "status": property.status or "active",
                "has_geom": property.geom is not None and str(property.geom).strip() != '',
                "has_point": property.latitude is not None and property.longitude is not None,
                "geometry_type": geometry_type,
                "geometry_source": "geom" if property.geom else "coordinates" if property.latitude else "bbox"
            }
            
            # Add numeric coordinates if available
            if property.latitude and property.longitude:
                try:
                    property_info["latitude"] = float(property.latitude)
                    property_info["longitude"] = float(property.longitude)
                except (ValueError, TypeError):
                    pass
            
            # Add area information if available
            if property.area:
                try:
                    property_info["area"] = float(property.area)
                except (ValueError, TypeError):
                    pass
            
            if property.area_in_me:
                try:
                    property_info["area_in_me"] = float(property.area_in_me)
                except (ValueError, TypeError):
                    pass
            
            # Add bounding box information
            if all([property.nlat, property.slat, property.wlong, property.elong]):
                try:
                    property_info["bbox"] = {
                        "north": float(property.nlat),
                        "south": float(property.slat),
                        "west": float(property.wlong),
                        "east": float(property.elong)
                    }
                except (ValueError, TypeError):
                    pass
            
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
                    # "zone": zone_filter,
                    # "property_type": property_type_filter,
                    # "status": status_filter,
                    "district": district_filter
                }
            }
        }

        print(geojson)
        
        logger.info(f"Generated GeoJSON with {len(features)} features")
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    
    except Exception as e:
        logger.error(f"Error in get_properties_geojson: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            "error": "Failed to generate GeoJSON",
            "details": str(e),
            "traceback": traceback.format_exc()
        }, status=500)

@login_required
def get_zones_geojson(request):
    """API endpoint to get zones as GeoJSON"""
    try:
        zones = Zone.objects.all().exclude(boundary__isnull=True).exclude(boundary='')
        
        features = []
        for zone in zones:
            geometry = None
            
            try:
                if zone.boundary:
                    if isinstance(zone.boundary, str):
                        try:
                            # Try to parse as JSON
                            geom_dict = json.loads(zone.boundary)
                            if 'coordinates' in geom_dict:
                                geometry = geom_dict
                            else:
                                # Try to parse as WKT
                                geom = GEOSGeometry(zone.boundary)
                                geometry = json.loads(geom.geojson)
                        except json.JSONDecodeError:
                            # Try to parse as WKT
                            geom = GEOSGeometry(zone.boundary)
                            geometry = json.loads(geom.geojson)
                    else:
                        geometry = zone.boundary
            except Exception as e:
                logger.warning(f"Failed to parse boundary for zone {zone.id}: {e}")
                continue
            
            if not geometry:
                continue
            
            # Count properties in this zone
            property_count = Property.objects.filter(zone=zone).count()
            
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": zone.id,
                    "name": zone.name,
                    "code": zone.code,
                    "zone_type": zone.zone_type,
                    "property_count": property_count,
                    "color": get_zone_color(zone.zone_type)
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
        'mixed': '#ff5722',            # Deep Orange (alternative)
    }
    return colors.get(zone_type.lower(), '#0dae48')

@login_required
def get_districts_geojson(request):
    """API endpoint to get districts as GeoJSON"""
    try:
        districts = District.objects.all().exclude(geom__isnull=True)
        
        features = []
        for district in districts:
            geometry = None
            
            try:
                if district.geom:
                    # Assuming geom is already a GEOSGeometry field
                    geometry = json.loads(district.geom.geojson)
            except Exception as e:
                logger.warning(f"Failed to parse geometry for district {district.id}: {e}")
                continue
            
            if not geometry:
                continue
            
            # Count properties in this district
            property_count = Property.objects.filter(district=district.district).count()
            
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": district.id,
                    "name": district.district,
                    "region": district.region,
                    "property_count": property_count,
                    "color": '#6c757d'  # Gray for districts
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
    """API endpoint to get Bops (businesses) as GeoJSON for the map.
    Uses only centroid (never loads geom) to avoid WKT parse errors from invalid geom data in DB.
    """
    try:
        from django.db.models import Q
        # Use all_objects to avoid is_deleted filter (column may not exist on lanma_businesses).
        # Do NOT select geom - DB may contain invalid/empty strings that raise WKT errors when deserialized.
        bops_qs = Bops.all_objects.filter(
            Q(centroid__isnull=False) & ~Q(centroid='')
        ).only(
            'id', 'centroid', 'account_number', 'business_name', 'business_category',
            'business_class', 'location', 'address', 'division', 'block', 'owner_name'
        )
        features = []
        for bop in bops_qs:
            geometry = None
            if bop.centroid and ',' in bop.centroid:
                try:
                    parts = bop.centroid.split(',')
                    if len(parts) == 2:
                        lat, lon = float(parts[0].strip()), float(parts[1].strip())
                        geometry = {"type": "Point", "coordinates": [lon, lat]}
                except (ValueError, TypeError):
                    pass
            if not geometry:
                continue
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": bop.id,
                    "account_number": bop.account_number or "",
                    "business_name": bop.business_name or "",
                    "business_category": bop.business_category or "",
                    "business_class": bop.business_class or "",
                    "location": bop.location or "",
                    "address": bop.address or "",
                    "division": bop.division or "",
                    "block": bop.block or "",
                    "owner_name": bop.owner_name or "",
                }
            }
            features.append(feature)
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {"total": len(features), "timestamp": timezone.now().isoformat()}
        }
        return JsonResponse(geojson, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error in get_bops_geojson: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)


@login_required
def get_property_details(request, property_id):
    """API endpoint to get detailed property information"""
    try:
        # Try to get by property_id or id
        try:
            property = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            try:
                property = Property.objects.get(id=property_id)
            except (Property.DoesNotExist, ValueError):
                return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
        
        # Parse geometry if available
        # geometry_info = None
        # if property.geom:
        #     try:
        #         # Try to parse as JSON
        #         geom_dict = json.loads(property.geom)
        #         geometry_info = geom_dict
        #     except json.JSONDecodeError:
        #         try:
        #             # Try to parse as WKT
        #             geom = GEOSGeometry(property.geom)
        #             geometry_info = json.loads(geom.geojson)
        #         except Exception:
        #             geometry_info = None
        
        # Get basic property data
        property_data = {
            "id": property.id,
            # "property_id": getattr(property, 'property_id', f"PROP-{property.id}"),
            "address": property.address or property.addressv1,
            "street": property.street,
            "district": property.district,
            "region": property.region,
            "postcode": property.postcode,
            # "property_type": property.property_type.name if property.property_type else "Unknown",
            # "zone": property.zone.name if property.zone else "Unknown",
            # "status": property.status,
            # "total_area": float(property.total_area) if property.total_area else None,
            # "built_up_area": float(property.built_up_area) if property.built_up_area else None,
            # "floor_count": property.floor_count,
            # "year_built": property.year_built,
            "latitude": float(property.latitude) if property.latitude else None,
            "longitude": float(property.longitude) if property.longitude else None,
            # "geometry": geometry_info,
            "has_geom": bool(property.geom),
            "has_point": bool(property.latitude and property.longitude)
        }
        
        return JsonResponse({"data": property_data, "status": "success"})
    
    except Exception as e:
        logger.error(f"Error in get_property_details: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def search_properties(request):
    """API endpoint for property search"""
    try:
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return JsonResponse({"results": [], "status": "success"})
        
        # Search in multiple fields
        properties = Property.objects.filter(
            Q(address__icontains=query) |
            Q(addressv1__icontains=query) |
            Q(street__icontains=query) |
            Q(gpsname__icontains=query) |
            Q(district__icontains=query) |
            Q(region__icontains=query)
        )[:20]
        
        results = []
        for property in properties:
            # Generate property_id from ID since the field doesn't exist
            property_id = f"PROP-{property.id}"
            
            results.append({
                "id": property.id,
                "property_id": property_id,  # Use generated ID
                "address": property.address or property.addressv1 or "",
                "district": property.district or "",
                "zone": property.zone.name if property.zone else "",
                "property_type": property.property_type.name if property.property_type else "",
                "latitude": float(property.latitude) if property.latitude else None,
                "longitude": float(property.longitude) if property.longitude else None,
                "has_geom": bool(property.geom),
                "has_point": bool(property.latitude and property.longitude),
                "area": float(property.area) if property.area else None,
                "area_in_me": float(property.area_in_me) if property.area_in_me else None
            })
        
        return JsonResponse({"results": results, "status": "success"})
    
    except Exception as e:
        logger.error(f"Error in search_properties: {str(e)}")
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
        total_properties = Property.objects.all().count()
        properties_with_geom = Property.objects.filter(
            
        ).exclude(
            Q(geom__isnull=True) | Q(geom='')
        ).count()
        
        properties_with_point = Property.objects.filter(
            
            latitude__isnull=False,
            longitude__isnull=False
        ).count()
        
        # Zone statistics
        zones_with_boundaries = Zone.objects.filter(
            
        ).exclude(
            Q(boundary__isnull=True) | Q(boundary='')
        ).count()
        
        # District statistics
        districts_with_geom = District.objects.filter(
            
        ).exclude(
            geom__isnull=True
        ).count()
        
        stats = {
            "total_properties": total_properties,
            "properties_with_geom": properties_with_geom,
            "properties_with_point": properties_with_point,
            "zones_with_boundaries": zones_with_boundaries,
            "districts_with_geom": districts_with_geom,
            "timestamp": timezone.now().isoformat()
        }
        
        return JsonResponse({"data": stats, "status": "success"})
    
    except Exception as e:
        logger.error(f"Error in get_map_stats: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_property_geometry(request, property_id):
    """API endpoint to get only property geometry"""
    try:
        # Try to get by property_id or id
        try:
            property = Property.objects.get(property_id=property_id)
        except Property.DoesNotExist:
            try:
                property = Property.objects.get(id=property_id)
            except (Property.DoesNotExist, ValueError):
                return JsonResponse({"error": "Property not found", "status": "error"}, status=404)
        
        geometry = None
        if property.geom:
            try:
                # Try to parse as JSON
                geom_dict = json.loads(property.geom)
                geometry = geom_dict
            except json.JSONDecodeError:
                try:
                    # Try to parse as WKT
                    geom = GEOSGeometry(property.geom)
                    geometry = json.loads(geom.geojson)
                except Exception as e:
                    logger.warning(f"Failed to parse geometry for property {property_id}: {e}")
        
        return JsonResponse({
            # "property_id": getattr(property, 'property_id', f"PROP-{property.id}"),
            "geometry": geometry,
            "has_geometry": bool(geometry),
            "status": "success"
        })
    
    except Exception as e:
        logger.error(f"Error in get_property_geometry: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)

@login_required
def get_properties_without_geometry(request):
    """API endpoint to get properties without geometry (for debugging)"""
    try:
        limit = int(request.GET.get('limit', 10))
        
        properties_without_geom = Property.objects.filter(
            
            geom__isnull=True
        )[:limit].values('id', 'address', 'district', 'zone__name')
        
        properties_with_bad_geom = Property.objects.filter(
            
            geom__isnull=False
        ).exclude(geom='')[:limit].values('id', 'address', 'district', 'zone__name', 'geom')
        
        return JsonResponse({
            "without_geometry": list(properties_without_geom),
            "with_bad_geometry": list(properties_with_bad_geom),
            "status": "success"
        })
    
    except Exception as e:
        logger.error(f"Error in get_properties_without_geometry: {str(e)}")
        return JsonResponse({"error": str(e), "status": "error"}, status=500)