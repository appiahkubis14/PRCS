import os
from django.http import HttpResponse, Http404, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
import logging
import mimetypes

from dotenv.main import logger

from core.models import Polygon

import os
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
import mimetypes
import logging

logger = logging.getLogger(__name__)

from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from django.views.decorators.cache import cache_control
import os
import logging

logger = logging.getLogger(__name__)
import os
import re
from django.http import HttpResponse, HttpResponseNotModified, Http404, FileResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_control
from django.utils.http import http_date
import logging
import time
from wsgiref.handlers import format_date_time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# @require_http_methods(["GET", "HEAD"])
# @cache_control(max_age=86400, public=True)
# def serve_pmtiles(request, filename):
#     """Serve PMTiles files with HTTP Byte Serving support"""
    
#     # Security check
#     if filename not in ['properties_high_quality_v1.pmtiles']:
#         logger.warning(f"Attempted to access unauthorized file: {filename}")
#         raise Http404("File not found")
    
#     # Find file
#     possible_paths = [
#         os.path.join(settings.BASE_DIR, 'static', 'tiles', filename),
#         os.path.join(settings.BASE_DIR, 'media', 'tiles', filename),
#         os.path.join(settings.STATIC_ROOT, 'tiles', filename) if hasattr(settings, 'STATIC_ROOT') else None,
#         os.path.join(settings.MEDIA_ROOT, 'tiles', filename) if hasattr(settings, 'MEDIA_ROOT') else None,
#     ]
    
#     file_path = None
#     for path in possible_paths:
#         if path and os.path.exists(path):
#             file_path = path
#             logger.info(f"Found PMTiles file at: {file_path}")
#             break
    
#     if not file_path:
#         logger.error(f"PMTiles file not found. Checked paths: {possible_paths}")
#         raise Http404("File not found")
    
#     file_size = os.path.getsize(file_path)
#     last_modified = os.path.getmtime(file_path)
    
#     # Handle If-Modified-Since header
#     if_modified_since = request.headers.get('If-Modified-Since')
#     if if_modified_since:
#         # Parse the header (simple implementation)
#         try:
#             # You might want to use email.utils.parsedate for proper parsing
#             modified_since = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S %Z')
#             if last_modified <= modified_since.timestamp():
#                 return HttpResponseNotModified()
#         except:
#             pass  # Ignore parsing errors
    
#     # Handle HEAD request
#     if request.method == 'HEAD':
#         response = HttpResponse()
#         response['Accept-Ranges'] = 'bytes'
#         response['Access-Control-Allow-Origin'] = '*'
#         response['Content-Type'] = 'application/vnd.pmtiles'
#         response['Content-Length'] = file_size
#         response['Last-Modified'] = http_date(last_modified)
#         response['Cache-Control'] = 'public, max-age=86400'
#         return response
    
#     # Handle Range header
#     range_header = request.headers.get('Range', '').strip()
    
#     # Log the request for debugging
#     logger.debug(f"PMTiles request: {request.method} {filename} Range: {range_header}")
    
#     # If no Range header, return entire file
#     if not range_header:
#         try:
#             response = FileResponse(open(file_path, 'rb'), content_type='application/vnd.pmtiles')
#             response['Accept-Ranges'] = 'bytes'
#             response['Access-Control-Allow-Origin'] = '*'
#             response['Content-Disposition'] = f'inline; filename="{filename}"'
#             response['Content-Length'] = file_size
#             response['Last-Modified'] = http_date(last_modified)
#             response['Cache-Control'] = 'public, max-age=86400'
#             return response
#         except Exception as e:
#             logger.error(f"Error serving PMTiles file: {e}")
#             raise Http404("Error serving file")
    
#     # Parse Range header
#     range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
#     if not range_match:
#         logger.warning(f"Invalid range header: {range_header}")
#         response = HttpResponse(status=416)  # Range Not Satisfiable
#         response['Content-Range'] = f'bytes */{file_size}'
#         return response
    
#     start_str, end_str = range_match.groups()
#     start = int(start_str)
    
#     # Calculate end byte
#     if end_str:
#         end = int(end_str)
#     else:
#         end = file_size - 1
    
#     # Validate range
#     if start >= file_size or end >= file_size or start > end:
#         logger.warning(f"Invalid range: {start}-{end} for file size {file_size}")
#         response = HttpResponse(status=416)
#         response['Content-Range'] = f'bytes */{file_size}'
#         return response
    
#     content_length = end - start + 1
    
#     logger.info(f"Serving range {start}-{end}/{file_size} for {filename}")
    
#     try:
#         file = open(file_path, 'rb')
#         file.seek(start)
        
#         # Read only the requested bytes
#         data = file.read(content_length)
        
#         response = HttpResponse(data, content_type='application/vnd.pmtiles', status=206)
#         response['Accept-Ranges'] = 'bytes'
#         response['Access-Control-Allow-Origin'] = '*'
#         response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
#         response['Content-Length'] = content_length
#         response['Content-Disposition'] = f'inline; filename="{filename}"'
#         response['Last-Modified'] = http_date(last_modified)
#         response['Cache-Control'] = 'public, max-age=86400'
        
#         file.close()
#         return response
        
#     except Exception as e:
#         logger.error(f"Error serving partial content: {e}")
#         raise Http404("Error serving file")



import os
import re
import logging
from datetime import datetime
from django.http import FileResponse, HttpResponse, HttpResponseNotModified, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_control
from django.utils.http import http_date
from django.conf import settings

logger = logging.getLogger(__name__)

# List of allowed PMTiles files
ALLOWED_PMTILES_FILES = [
    'properties_high_quality_v1.pmtiles',
    'aerial_imagery_v1.pmtiles',  # Add your aerial file
    'custom_properties_v1.pmtiles',
    # Add more files as needed
]

@require_http_methods(["GET", "HEAD"])
@cache_control(max_age=86400, public=True)
def serve_pmtiles(request, filename):
    """Serve PMTiles files with HTTP Byte Serving support"""
    
    # Security check - allow only specified files
    if filename not in ALLOWED_PMTILES_FILES:
        logger.warning(f"Attempted to access unauthorized file: {filename}")
        raise Http404("File not found")
    
    # Find file in multiple possible locations
    file_path = find_pmtiles_file(filename)
    
    if not file_path:
        logger.error(f"PMTiles file not found: {filename}")
        raise Http404("File not found")
    
    try:
        file_size = os.path.getsize(file_path)
        last_modified = os.path.getmtime(file_path)
        etag = f'"{filename}-{file_size}-{last_modified}"'
        
        # Handle If-None-Match header (ETag)
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match and if_none_match == etag:
            return HttpResponseNotModified()
        
        # Handle If-Modified-Since header
        if_modified_since = request.headers.get('If-Modified-Since')
        if if_modified_since:
            try:
                # Parse HTTP date
                modified_since = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S %Z').timestamp()
                if last_modified <= modified_since:
                    return HttpResponseNotModified()
            except (ValueError, TypeError):
                pass  # Ignore parsing errors
        
        # Handle HEAD request
        if request.method == 'HEAD':
            response = HttpResponse()
            set_common_headers(response, file_size, last_modified, etag, filename)
            return response
        
        # Handle Range header
        range_header = request.headers.get('Range', '').strip()
        
        # Log request for debugging
        logger.debug(f"PMTiles request: {request.method} {filename} Range: {range_header}")
        
        # If no Range header, return entire file
        if not range_header:
            return serve_entire_file(file_path, file_size, last_modified, etag, filename)
        
        # Parse and serve range
        return serve_file_range(file_path, file_size, last_modified, etag, filename, range_header)
        
    except Exception as e:
        logger.error(f"Error serving PMTiles file {filename}: {e}", exc_info=True)
        raise Http404("Error serving file")

def find_pmtiles_file(filename):
    """Find PMTiles file in possible locations"""
    
    # Get all possible base directories
    base_dirs = [
        settings.BASE_DIR,
    ]
    
    # Add static and media directories if they exist
    if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
        base_dirs.append(settings.STATIC_ROOT)
    if hasattr(settings, 'MEDIA_ROOT') and settings.MEDIA_ROOT:
        base_dirs.append(settings.MEDIA_ROOT)
    
    # Possible subdirectories
    subdirs = ['static', 'media', 'tiles', 'static/tiles', 'media/tiles']
    
    # Check all combinations
    for base_dir in base_dirs:
        for subdir in subdirs:
            possible_path = os.path.join(base_dir, subdir, filename)
            if os.path.exists(possible_path):
                logger.info(f"Found PMTiles file at: {possible_path}")
                return possible_path
        
        # Also check directly in base directory
        possible_path = os.path.join(base_dir, filename)
        if os.path.exists(possible_path):
            logger.info(f"Found PMTiles file at: {possible_path}")
            return possible_path
    
    return None

def set_common_headers(response, file_size, last_modified, etag, filename):
    """Set common headers for all responses"""
    response['Accept-Ranges'] = 'bytes'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Range, If-None-Match, If-Modified-Since'
    response['Content-Type'] = 'application/vnd.pmtiles'
    response['Content-Length'] = file_size
    response['Last-Modified'] = http_date(last_modified)
    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=86400'
    response['Content-Disposition'] = f'inline; filename="{filename}"'

def serve_entire_file(file_path, file_size, last_modified, etag, filename):
    """Serve the entire file"""
    try:
        file_handle = open(file_path, 'rb')
        response = FileResponse(file_handle, content_type='application/vnd.pmtiles')
        set_common_headers(response, file_size, last_modified, etag, filename)
        return response
    except Exception as e:
        logger.error(f"Error serving entire file: {e}")
        raise

def serve_file_range(file_path, file_size, last_modified, etag, filename, range_header):
    """Serve a range of the file"""
    
    # Parse Range header
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not range_match:
        logger.warning(f"Invalid range header: {range_header}")
        return create_range_not_satisfiable_response(file_size)
    
    start_str, end_str = range_match.groups()
    
    try:
        start = int(start_str)
        
        # Calculate end byte
        if end_str:
            end = int(end_str)
        else:
            end = file_size - 1
        
        # Validate range
        if start >= file_size or end >= file_size or start > end:
            logger.warning(f"Invalid range: {start}-{end} for file size {file_size}")
            return create_range_not_satisfiable_response(file_size)
        
        content_length = end - start + 1
        
        logger.info(f"Serving range {start}-{end}/{file_size} for {filename}")
        
        # Read the requested bytes
        with open(file_path, 'rb') as file:
            file.seek(start)
            data = file.read(content_length)
        
        # Create response with partial content
        response = HttpResponse(data, content_type='application/vnd.pmtiles', status=206)
        set_common_headers(response, file_size, last_modified, etag, filename)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = content_length
        
        return response
        
    except (ValueError, OSError) as e:
        logger.error(f"Error serving range: {e}")
        return create_range_not_satisfiable_response(file_size)

def create_range_not_satisfiable_response(file_size):
    """Create a 416 Range Not Satisfiable response"""
    response = HttpResponse(status=416)
    response['Content-Range'] = f'bytes */{file_size}'
    response['Access-Control-Allow-Origin'] = '*'
    return response

# Add OPTIONS handler for CORS preflight
@require_http_methods(["OPTIONS"])
def pmtiles_options(request, filename):
    """Handle OPTIONS requests for CORS preflight"""
    response = HttpResponse()
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Range, If-None-Match, If-Modified-Since'
    response['Access-Control-Max-Age'] = '86400'
    return response


@login_required
def get_properties_points(request):
    """API endpoint to get only point properties (for clustering)"""
    try:
        # Get filter parameters
        district_filter = request.GET.get('district', '')
        
        # Get only properties with point coordinates
        properties = Polygon.objects.exclude(
            latitude__isnull=True
        ).exclude(
            longitude__isnull=True
        )
        
        if district_filter:
            properties = properties.filter(district=district_filter)
        
        # Limit results for performance
        properties = properties[:]  # Limit points for clustering
        
        features = []
        for property in properties:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(property.longitude),
                        float(property.latitude)
                    ]
                },
                "properties": {
                    "id": property.id,
                    "property_id": f"PROP-{property.id}",
                    "address": property.address or property.addressv1 or "No address",
                    "district": property.district or "Unknown",
                    "region": property.region or "Unknown",
                }
            }
            features.append(feature)
        
        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        })
        
    except Exception as e:
        logger.error(f"Error in get_properties_points: {e}")
        return JsonResponse({"error": str(e)}, status=500)
    




from django.http import JsonResponse
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.serializers import geojson
from core.models import Polygon
import json

def properties_simple_geojson(request):
    """
    Return simplified GeoJSON for interactive overlay
    """
    fields = request.GET.get('fields', 'id,address,district,region,zone,property_type,area,area_in_me,status,latitude,longitude,g_code,postcode,street,gpsname').split(',')
    
    properties = Polygon.objects.all()[:50000]
    
    
    features = []
    for prop in properties:
        feature = {
            "type": "Feature",
            "geometry": json.loads(prop.geom.geojson) if prop.geom else None,
            "properties": {}
        }
        
        for field in fields:
            # if field == 'zone' and prop.zone:
            #     feature['properties']['zone'] = prop.zone.name
            # if field == 'property_type' and prop.property_type:
            #     feature['properties']['property_type'] = prop.property_type.name
            if hasattr(prop, field):
                value = getattr(prop, field)
                if value is not None:
                    feature['properties'][field] = str(value)
        
        if feature['geometry']:
            features.append(feature)
    
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })




from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from core.models import Polygon
import json

@require_GET
def property_geojson_for_highlight(request, property_id):
    """
    Return GeoJSON for a single property (for highlighting)
    """
    try:
        property = Polygon.objects.get(id=property_id)
        
        if property.geom:
            try:
                # Get geometry as GeoJSON
                geom_geojson = json.loads(property.geom.geojson)
                
                return JsonResponse({
                    'type': 'Feature',
                    'geometry': geom_geojson,
                    'properties': {
                        'id': property.id,
                        'district': property.district,
                        'region': property.region
                    }
                })
            except Exception as e:
                return JsonResponse({
                    'error': f'Error parsing geometry: {str(e)}'
                }, status=500)
        else:
            # Try to create geometry from bounds
            if all([property.nlat, property.slat, property.wlong, property.elong]):
                try:
                    coords = [
                        [float(property.wlong), float(property.slat)],
                        [float(property.elong), float(property.slat)],
                        [float(property.elong), float(property.nlat)],
                        [float(property.wlong), float(property.nlat)],
                        [float(property.wlong), float(property.slat)]
                    ]
                    return JsonResponse({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [coords]
                        },
                        'properties': {
                            'id': property.id
                        }
                    })
                except:
                    pass
            
            return HttpResponseNotFound('Polygon has no geometry')
            
    except Polygon.DoesNotExist:
        return HttpResponseNotFound('Polygon not found')
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)