import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Property
import mapbox_vector_tile
import mercantile

class Command(BaseCommand):
    help = 'Generate PMTiles file from property polygons'

    def handle(self, *args, **options):
        output_file = 'properties.pmtiles'
        
        # Collect features
        features = []
        properties = Property.objects.exclude(geom__isnull=True)
        
        for prop in properties:
            try:
                # Get geometry as GeoJSON
                if hasattr(prop.geom, 'geojson'):
                    geom = json.loads(prop.geom.geojson)
                else:
                    geom = json.loads(GEOSGeometry(str(prop.geom)).geojson)
                
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "id": prop.id,
                        "address": (prop.address or prop.addressv1 or "")[:50]
                    }
                })
            except:
                continue
        
        # Group by tile and encode as MVT
        tiles_data = {}
        
        for zoom in range(8, 15):
            for feature in features:
                # Calculate which tiles this feature belongs to
                # This is simplified - you need proper tile coverage calculation
                # For production, use mercantile to get actual tile coverage
                pass
        
        # Write PMTiles file
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        
        # This requires a proper PMTiles writer library
        # Consider using: https://github.com/protomaps/pmtiles/tree/master/python