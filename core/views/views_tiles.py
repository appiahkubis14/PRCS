import os
from django.http import HttpResponse, Http404, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
import logging
import mimetypes

from dotenv.main import logger

from core.models import Property

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

@require_http_methods(["GET", "HEAD"])
@cache_control(max_age=86400, public=True)  # Cache for 24 hours
def serve_pmtiles(request, filename):
    """Serve PMTiles files efficiently"""
    # Security check - only allow specific files
    if filename not in ['properties.pmtiles']:
        logger.warning(f"Attempted to access unauthorized file: {filename}")
        raise Http404("File not found")
    
    # Try multiple possible locations
    possible_paths = [
        os.path.join(settings.BASE_DIR, 'static', 'tiles', filename),
        os.path.join(settings.BASE_DIR, 'media', 'tiles', filename),
        os.path.join(settings.STATIC_ROOT, 'tiles', filename) if hasattr(settings, 'STATIC_ROOT') else None,
        os.path.join(settings.MEDIA_ROOT, 'tiles', filename) if hasattr(settings, 'MEDIA_ROOT') else None,
    ]
    
    file_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            file_path = path
            logger.info(f"Found PMTiles file at: {file_path}")
            break
    
    if not file_path:
        logger.error(f"PMTiles file not found. Checked paths: {possible_paths}")
        raise Http404("File not found")
    
    # For HEAD requests, just return a success response without the file
    if request.method == 'HEAD':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Content-Type'] = 'application/vnd.pmtiles'
        response['Content-Length'] = os.path.getsize(file_path)
        return response
    
    # For GET requests, return the file
    try:
        response = FileResponse(open(file_path, 'rb'), content_type='application/vnd.pmtiles')
        response['Access-Control-Allow-Origin'] = '*'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f"Error serving PMTiles file: {e}")
        raise Http404("Error serving file")



@login_required
def get_properties_points(request):
    """API endpoint to get only point properties (for clustering)"""
    try:
        # Get filter parameters
        district_filter = request.GET.get('district', '')
        
        # Get only properties with point coordinates
        properties = Property.objects.exclude(
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