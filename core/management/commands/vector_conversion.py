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
    help = 'Generate PMTiles using tippecanoe with full property attributes for popups'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='custom_properties_v1.pmtiles')
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
                # Try to convert to float, but if it fails, skip
                lat = float(property_obj.latitude)
                lng = float(property_obj.longitude)
                return {
                    "type": "Point",
                    "coordinates": [lng, lat]
                }
            except (ValueError, TypeError):
                pass
        
        return None

    def safe_float_conversion(self, value):
        """Safely convert a value to float, return None if conversion fails"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Create temporary GeoJSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp_file:
            features = []
            
            # Use select_related to fetch related objects efficiently
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
                    
                    # Safely convert latitude and longitude
                    lat = self.safe_float_conversion(property.latitude)
                    lng = self.safe_float_conversion(property.longitude)
                    
                    # Create feature with comprehensive properties for popups
                    feature = {
                        "type": "Feature",
                        "geometry": geom,
                        "properties": {
                            # Core identifiers
                            "id": property.id,
                            
                            # Location information - ensure all values are strings
                            "address": str(property.address or property.addressv1 or "N/A").strip(),
                            "district": str(property.district or "N/A").strip(),
                            "region": str(property.region or "N/A").strip(),
                            "postcode": str(property.postcode or "N/A").strip(),
                            "street": str(property.street or "N/A").strip(),
                            "gpsname": str(property.gpsname or "N/A").strip(),
                            
                            # Zone information - comment out for now to isolate issue
                            # "zone": str(property.zone.name) if property.zone else "N/A",
                            # "zone_code": str(property.zone.code) if property.zone else "N/A",
                            
                            # Property type information - comment out for now
                            # "property_type": str(property.property_type.name) if property.property_type else "N/A",
                            # "property_type_code": str(property.property_type.code) if property.property_type else "N/A",
                            
                            # Status - comment out for now
                            # "status": str(property.status or "active"),
                            
                            # Geographic codes
                            "g_code": str(property.g_code or "N/A").strip(),
                        }
                    }
                    
                    # Add coordinates only if they converted successfully
                    if lat is not None and lng is not None:
                        feature["properties"]["latitude"] = lat
                        feature["properties"]["longitude"] = lng
                    
                    # Safely add numeric fields
                    area = self.safe_float_conversion(property.area)
                    if area is not None:
                        feature["properties"]["area"] = area
                    
                    area_in_me = self.safe_float_conversion(property.area_in_me)
                    if area_in_me is not None:
                        feature["properties"]["area_in_me"] = area_in_me
                    
                    # Add marker color
                    # if property.property_type and property.property_type.color:
                    #     feature["properties"]["marker_color"] = str(property.property_type.color)
                    # else:
                    #     # Default color
                    #     feature["properties"]["marker_color"] = "#0dae48"
                    
                    features.append(feature)
                    processed += 1
                    
                    if i % 100 == 0:
                        self.stdout.write(f"Processed {processed} properties, Skipped: {skipped}")
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on property {property.id}: {e}"))
                    skipped += 1
            
            self.stdout.write(f"Final: Processed {processed} properties, Skipped {skipped}")
            
            if processed == 0:
                self.stdout.write(self.style.ERROR("No valid geometries found! Exiting."))
                return
            
            # Write GeoJSON
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            json.dump(geojson, tmp_file)
            tmp_file_path = tmp_file.name
            
            # Check file size
            file_size = os.path.getsize(tmp_file_path)
            self.stdout.write(f"Temporary GeoJSON file size: {file_size} bytes")
        
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
        
        # Use the same tippecanoe command as the working version
        cmd = [
            'tippecanoe',
            '-o', output_path,
            '-l', 'properties',
            '--maximum-zoom=20',
            '--minimum-zoom=5',
            '--drop-densest-as-needed',
            '--detect-shared-borders',
            '-f',  # Force overwrite
            tmp_file_path
        ]
        
        self.stdout.write("Running tippecanoe...")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.stdout.write(self.style.SUCCESS(f"Successfully generated {output_path}"))
            if result.stdout:
                self.stdout.write(f"tippecanoe output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Tippecanoe failed: {e.stderr}"))
        finally:
            # Clean up temp file
            os.unlink(tmp_file_path)