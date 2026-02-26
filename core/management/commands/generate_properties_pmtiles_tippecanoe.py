import json
import os
import subprocess
import tempfile
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Property
from django.contrib.gis.geos import GEOSGeometry
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate PMTiles using tippecanoe'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='properties.pmtiles')
        parser.add_argument('--max-zoom', type=int, default=14)
        parser.add_argument('--min-zoom', type=int, default=8)

    def safe_get_geojson(self, property_obj):
        """Safely extract GeoJSON from property geometry"""
        
        # Method 1: Try geom field with geojson property
        if property_obj.geom:
            try:
                if hasattr(property_obj.geom, 'geojson'):
                    geom_json = property_obj.geom.geojson
                    if geom_json:
                        if isinstance(geom_json, str):
                            return json.loads(geom_json)
                        elif isinstance(geom_json, dict):
                            return geom_json
            except:
                pass
            
            # Method 2: Try converting geom to string and parse as WKT
            try:
                geom_str = str(property_obj.geom)
                if geom_str and geom_str != 'None' and geom_str.strip():
                    # Try as WKT
                    geom = GEOSGeometry(geom_str)
                    if geom and geom.valid:
                        return json.loads(geom.geojson)
            except:
                pass
        
        # Method 3: Create from bounding coordinates if available
        if all([property_obj.nlat, property_obj.slat, property_obj.wlong, property_obj.elong]):
            try:
                # Create polygon from bounds
                coords = [
                    [float(property_obj.wlong), float(property_obj.slat)],
                    [float(property_obj.elong), float(property_obj.slat)],
                    [float(property_obj.elong), float(property_obj.nlat)],
                    [float(property_obj.wlong), float(property_obj.nlat)],
                    [float(property_obj.wlong), float(property_obj.slat)]
                ]
                return {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            except (ValueError, TypeError):
                pass
        
        # Method 4: Create point from lat/long if available
        if property_obj.latitude and property_obj.longitude:
            try:
                return {
                    "type": "Point",
                    "coordinates": [
                        float(property_obj.longitude),
                        float(property_obj.latitude)
                    ]
                }
            except (ValueError, TypeError):
                pass
        
        return None

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Create temporary GeoJSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp_file:
            features = []
            
            properties = Property.objects.all()
            total = properties.count()
            
            self.stdout.write(f"Processing {total} properties...")
            
            processed = 0
            skipped = 0
            
            for i, property in enumerate(properties, 1):
                try:
                    # Get geometry safely
                    geom = self.safe_get_geojson(property)
                    
                    if not geom:
                        skipped += 1
                        continue
                    
                    # Skip Point geometries if you only want polygons
                    # if geom.get('type') == 'Point':
                    #     skipped += 1
                    #     continue
                    
                    # Create feature with minimal properties
                    feature = {
                        "type": "Feature",
                        "geometry": geom,
                        "properties": {
                            "id": property.id,
                        }
                    }
                    
                    # Add essential fields only
                    if property.address:
                        feature["properties"]["address"] = property.address[:50]
                    elif property.addressv1:
                        feature["properties"]["address"] = property.addressv1[:50]
                    
                    if property.district:
                        feature["properties"]["district"] = property.district
                    
                    features.append(feature)
                    processed += 1
                    
                    if i % 100 == 0:
                        self.stdout.write(f"Processed {processed} properties, Skipped: {skipped}")
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on property {property.id}: {e}"))
                    skipped += 1
            
            self.stdout.write(f"Final: Processed {processed} properties, Skipped {skipped}")
            
            # Write GeoJSON
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            json.dump(geojson, tmp_file)
            tmp_file_path = tmp_file.name
        
        # Use tippecanoe to generate PMTiles
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Check if tippecanoe is installed
        try:
            subprocess.run(['tippecanoe', '-v'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.stdout.write(self.style.ERROR("tippecanoe is not installed. Please install it first:"))
            self.stdout.write("  Ubuntu/Debian: sudo apt-get install tippecanoe")
            self.stdout.write("  macOS: brew install tippecanoe")
            return
        
        cmd = [
            'tippecanoe',
            '-o', output_path,
            '-l', 'properties',
            '--maximum-zoom=14',
            '--minimum-zoom=8',
            '--drop-densest-as-needed',
            '--simplification=10',
            '--detect-shared-borders',
            '-f',  # Force overwrite
            tmp_file_path
        ]
        
        self.stdout.write("Running tippecanoe...")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.stdout.write(self.style.SUCCESS(f"Successfully generated {output_path}"))
            self.stdout.write(f"tippecanoe output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Tippecanoe failed: {e.stderr}"))
        finally:
            # Clean up temp file
            os.unlink(tmp_file_path)