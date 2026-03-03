# core/management/commands/generate_pmtiles.py
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
        parser.add_argument('--include-points', action='store_true', default=False)
        parser.add_argument('--quality', type=str, default='medium',
                          choices=['draft', 'low', 'medium', 'high', 'maximum'],
                          help='Quality level (affects simplification and detail)')

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
                    geom = GEOSGeometry(geom_str)
                    if geom and geom.valid:
                        return json.loads(geom.geojson)
            except:
                pass
        
        # Method 3: Create from bounding coordinates if available
        if all([property_obj.nlat, property_obj.slat, property_obj.wlong, property_obj.elong]):
            try:
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
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        include_points = options['include_points']
        quality = options['quality']
        
        self.stdout.write("=" * 70)
        self.stdout.write("PMTILES GENERATION")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Output file: {output_file}")
        self.stdout.write(f"Zoom levels: {min_zoom} to {max_zoom}")
        self.stdout.write(f"Include points: {include_points}")
        self.stdout.write(f"Quality: {quality}")
        self.stdout.write("=" * 70)
        
        # Create temporary GeoJSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp_file:
            features = []
            
            # Get properties
            properties = Property.objects.all()
            total = properties.count()
            
            self.stdout.write(f"\nProcessing {total} properties...")
            
            processed = 0
            skipped = 0
            points_skipped = 0
            
            for i, property in enumerate(properties, 1):
                try:
                    # Get geometry safely
                    geom = self.safe_get_geojson(property)
                    
                    if not geom:
                        skipped += 1
                        continue
                    
                    # Skip Point geometries if not requested
                    if geom.get('type') == 'Point' and not include_points:
                        points_skipped += 1
                        continue
                    
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
                        feature["properties"]["addr"] = property.address[:50]
                    elif property.addressv1:
                        feature["properties"]["addr"] = property.addressv1[:50]
                    
                    if property.district:
                        feature["properties"]["dist"] = property.district[:30]
                    
                    features.append(feature)
                    processed += 1
                    
                    if i % 1000 == 0:
                        self.stdout.write(f"  Processed {i}/{total}... (valid: {processed})")
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on property {property.id}: {e}"))
                    skipped += 1
            
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("PROCESSING SUMMARY")
            self.stdout.write("=" * 70)
            self.stdout.write(f"Total properties: {total}")
            self.stdout.write(f"Processed: {processed}")
            self.stdout.write(f"Skipped (no geometry): {skipped}")
            if not include_points:
                self.stdout.write(f"Points skipped: {points_skipped}")
            self.stdout.write(f"Valid features: {len(features)}")
            
            if len(features) == 0:
                self.stdout.write(self.style.ERROR("No valid features found! Exiting."))
                return
            
            # Write GeoJSON
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            json.dump(geojson, tmp_file)
            tmp_file_path = tmp_file.name
            
            # Show GeoJSON size
            geojson_size = os.path.getsize(tmp_file_path) / (1024 * 1024)
            self.stdout.write(f"\nGeoJSON size: {geojson_size:.2f} MB")
        
        # Use tippecanoe to generate PMTiles
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Check if tippecanoe is installed
        try:
            result = subprocess.run(['tippecanoe', '-v'], check=True, capture_output=True, text=True)
            self.stdout.write(f"\n✅ Using {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.stdout.write(self.style.ERROR("❌ tippecanoe is not installed"))
            self.stdout.write("  Ubuntu/Debian: sudo apt-get install tippecanoe")
            self.stdout.write("  macOS: brew install tippecanoe")
            return
        
        # Base command
        cmd = [
            'tippecanoe',
            '-o', output_path,
            '-l', 'properties',
            f'--minimum-zoom={min_zoom}',
            f'--maximum-zoom={max_zoom}',
            '--detect-shared-borders',
            '-f',  # Force overwrite
            tmp_file_path
        ]
        
        # Add quality-specific flags
        if quality == 'draft':
            cmd.extend([
                '--simplification=20',
                '--drop-densest-as-needed',
                '--maximum-tile-bytes=100000',
                '--coalesce-densest-as-needed'
            ])
        elif quality == 'low':
            cmd.extend([
                '--simplification=10',
                '--drop-densest-as-needed',
                '--maximum-tile-bytes=80000',
                '--coalesce'
            ])
        elif quality == 'medium':
            cmd.extend([
                '--simplification=5',
                '--drop-densest-as-needed',
                '--maximum-tile-bytes=50000',
                '--coalesce'
            ])
        elif quality == 'high':
            cmd.extend([
                '--simplification=2',  # Less simplification
                '--no-tile-size-limit',  # Allow larger tiles
                '--no-feature-limit',    # Don't limit features
                '--detect-shared-borders',
                '--preserve-input-order'  # Preserve original geometry
            ])
        elif quality == 'maximum':
            cmd.extend([
                '--simplification=0',  # No simplification
                '--no-tile-size-limit',
                '--no-feature-limit',
                '--no-tile-compression',
                '--preserve-input-order',
                '--detect-shared-borders'
            ])
        
        self.stdout.write("\n🔄 Running tippecanoe...")
        self.stdout.write(f"Command: {' '.join(cmd)}")
        
        try:
            # Run with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Show output
            for line in process.stdout:
                line = line.strip()
                if line:
                    if 'error' in line.lower():
                        self.stdout.write(self.style.ERROR(f"  {line}"))
                    elif any(k in line.lower() for k in ['tile', 'zoom', 'layer', '%']):
                        self.stdout.write(f"  {line}")
            
            process.wait()
            
            if process.returncode == 0:
                self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully generated {output_path}"))
                
                # Show file info
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path) / (1024 * 1024)
                    compression = (1 - file_size / geojson_size) * 100 if geojson_size > 0 else 0
                    
                    self.stdout.write("\n" + "=" * 70)
                    self.stdout.write("FILE INFORMATION")
                    self.stdout.write("=" * 70)
                    self.stdout.write(f"📁 Output: {output_path}")
                    self.stdout.write(f"📊 Size: {file_size:.2f} MB")
                    self.stdout.write(f"📈 Compression: {compression:.1f}% reduction")
                    self.stdout.write(f"🔍 Zoom levels: {min_zoom}-{max_zoom}")
                    self.stdout.write(f"📍 Features: {len(features)}")
                    self.stdout.write(f"⚙️ Quality: {quality}")
            else:
                self.stdout.write(self.style.ERROR("\n❌ Tippecanoe failed"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_file_path)
            except:
                pass