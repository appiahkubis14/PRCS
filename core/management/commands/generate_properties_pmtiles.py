import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from core.models import Property
import mercantile
from shapely.geometry import shape
import struct
import logging
from pyproj import Transformer
import traceback
from django.utils import timezone
import gzip # Add this import at the top of your file

# Set up logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate PMTiles file from property polygons'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='properties.pmtiles')
        parser.add_argument('--max-zoom', type=int, default=14)
        parser.add_argument('--min-zoom', type=int, default=8)
        parser.add_argument('--batch-size', type=int, default=100, help='Process in batches to save memory')

    def safe_get_geojson(self, property_obj):
        """Safely extract GeoJSON from property geometry with multiple fallback methods"""
        
        # Method 1: Try geojson field if it exists
        if hasattr(property_obj, 'geojson') and property_obj.geojson:
            try:
                if isinstance(property_obj.geojson, dict):
                    return property_obj.geojson
                elif isinstance(property_obj.geojson, str):
                    return json.loads(property_obj.geojson)
            except:
                pass
        
        # Method 2: Try geom field with geojson property
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
            
            # Method 3: Try converting geom to string and parse
            try:
                geom_str = str(property_obj.geom)
                if geom_str and geom_str != 'None' and geom_str.strip():
                    # Try as WKT
                    try:
                        geom = GEOSGeometry(geom_str)
                        if geom and geom.valid:
                            return json.loads(geom.geojson)
                    except:
                        pass
                    
                    # Try as GeoJSON string
                    try:
                        if geom_str.startswith('{'):
                            geom_dict = json.loads(geom_str)
                            if 'type' in geom_dict and 'coordinates' in geom_dict:
                                return geom_dict
                    except:
                        pass
            except:
                pass
        
        # Method 4: Create from bounding coordinates if available
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
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to create polygon from bounds: {e}")
        
        # Method 5: Create point from lat/long if available
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
        max_zoom = options['max_zoom']
        min_zoom = options['min_zoom']
        batch_size = options['batch_size']
        
        self.stdout.write(f"Generating PMTiles from property polygons...")
        
        # Get all properties that might have geometry
        properties = Property.objects.all()
        total = properties.count()
        
        self.stdout.write(f"Found {total} total properties")
        
        # Create a dictionary to store tile data
        tiles_dict = {}
        
        processed = 0
        skipped = 0
        error_count = 0
        
        # Process in batches to manage memory
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = properties[start:end]
            
            self.stdout.write(f"Processing batch {start//batch_size + 1}/{(total-1)//batch_size + 1}")
            
            for property in batch:
                try:
                    # Get geometry as GeoJSON
                    geom_geojson = self.safe_get_geojson(property)
                    
                    if not geom_geojson:
                        skipped += 1
                        if skipped % 100 == 0:
                            self.stdout.write(f"Skipped {skipped} properties (no valid geometry)")
                        continue
                    
                    # Validate geometry type
                    geom_type = geom_geojson.get('type')
                    if geom_type not in ['Polygon', 'MultiPolygon', 'Point']:
                        skipped += 1
                        continue
                    
                    # Convert to shapely geometry for bounds calculation
                    try:
                        geom_shapely = shape(geom_geojson)
                    except Exception as e:
                        logger.warning(f"Failed to convert to shapely: {e}")
                        skipped += 1
                        continue
                    
                    # Prepare properties (keep it minimal for performance)
                    props = {
                        "id": property.id,
                    }
                    
                    # Add essential fields only (limit size)
                    if property.address:
                        props["address"] = property.address[:100]  # Truncate long addresses
                    elif property.addressv1:
                        props["address"] = property.addressv1[:100]
                    
                    if property.district:
                        props["district"] = property.district
                    if property.region:
                        props["region"] = property.region
                    
                    # Add area if available (as integer to save space)
                    if property.area:
                        try:
                            props["area"] = round(float(property.area), 2)
                        except:
                            pass
                    
                    # Calculate bounding box
                    try:
                        bounds = geom_shapely.bounds  # (minx, miny, maxx, maxy)
                        
                        # Validate bounds
                        if not all([-180 <= bounds[0] <= 180, -90 <= bounds[1] <= 90, 
                                   -180 <= bounds[2] <= 180, -90 <= bounds[3] <= 90]):
                            logger.warning(f"Invalid bounds for property {property.id}: {bounds}")
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to calculate bounds: {e}")
                        continue
                    
                    # Find all tiles this geometry covers at different zoom levels
                    for zoom in range(min_zoom, max_zoom + 1):
                        try:
                            # Get tiles covering the bounding box
                            tiles = list(mercantile.tiles(bounds[0], bounds[1], bounds[2], bounds[3], [zoom]))
                            
                            # Limit number of tiles per geometry to prevent explosion
                            if len(tiles) > 100:  # Skip if geometry covers too many tiles
                                continue
                            
                            for tile in tiles:
                                tile_key = (zoom, tile.x, tile.y)
                                
                                if tile_key not in tiles_dict:
                                    tiles_dict[tile_key] = {
                                        "type": "FeatureCollection",
                                        "features": []
                                    }
                                
                                # Create feature with simplified geometry
                                feature = {
                                    "type": "Feature",
                                    "geometry": geom_geojson,
                                    "properties": props
                                }
                                
                                tiles_dict[tile_key]["features"].append(feature)
                        except Exception as tile_error:
                            logger.warning(f"Tile processing error for property {property.id}: {tile_error}")
                            continue
                    
                    processed += 1
                    if processed % 100 == 0:
                        self.stdout.write(f"Processed {processed} properties, Skipped: {skipped}, Errors: {error_count}")
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 10:  # Log first 10 errors
                        self.stdout.write(self.style.ERROR(f"Error processing property {property.id}: {str(e)}"))
                        self.stdout.write(traceback.format_exc())
                    elif error_count == 11:
                        self.stdout.write(self.style.ERROR("Too many errors, suppressing further error logs"))
        
        self.stdout.write(self.style.SUCCESS(f"Processing complete: {processed} processed, {skipped} skipped, {error_count} errors"))
        self.stdout.write(f"Creating PMTiles file with {len(tiles_dict)} tiles...")
        
        # Create PMTiles file
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            self.create_pmtiles_file(tiles_dict, output_path, min_zoom, max_zoom)
            self.stdout.write(self.style.SUCCESS(f"Successfully generated {output_path}"))
            self.stdout.write(f"Total tiles created: {len(tiles_dict)}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create PMTiles file: {e}"))
            self.stdout.write(traceback.format_exc())
    
    

    def create_pmtiles_file(self, tiles_dict, output_path, min_zoom, max_zoom):
        """Create PMTiles file from tiles dictionary with proper gzip compression"""
        
        with open(output_path, 'wb') as f:
            # --- Write PMTiles header (version 2) ---
            f.write(b'PMTiles')
            f.write(struct.pack('<I', 2))  # Version 2
            
            # Reserve space for header fields (64-bit integers)
            header_fields = [
                'root_dir_offset', 'root_dir_length',
                'metadata_offset', 'metadata_length',
                'leaf_dir_offset', 'leaf_dir_length',
                'tile_data_offset', 'tile_data_length',
                'tile_data_count', 'tile_data_entries'
            ]
            
            header_positions = {}
            for field in header_fields:
                header_positions[field] = f.tell()
                f.write(struct.pack('<Q', 0))  # Placeholder
            
            # --- Store tile data offsets and write compressed tile data ---
            tile_offsets = {}
            current_offset = f.tell()
            tile_data_start = current_offset
            
            self.stdout.write("Writing compressed tile data...")
            for i, ((z, x, y), geojson_data) in enumerate(tiles_dict.items()):
                # 1. Convert GeoJSON feature collection to a minified JSON string
                json_str = json.dumps(geojson_data, separators=(',', ':'))
                
                # 2. Compress the string using gzip
                compressed_content = gzip.compress(json_str.encode('utf-8'))
                
                # 3. Store offset and write to file: [4-byte length][compressed data]
                tile_offsets[(z, x, y)] = current_offset
                f.write(struct.pack('<I', len(compressed_content)))  # Size of compressed data
                f.write(compressed_content)                          # The compressed data itself
                
                current_offset = f.tell()
                
                if (i + 1) % 1000 == 0:
                    self.stdout.write(f"Written {i + 1}/{len(tiles_dict)} tiles")
            
            tile_data_end = current_offset
            
            # --- Write Root Directory (entries for min_zoom level) ---
            root_dir_start = current_offset
            root_entries = []
            # Group tiles by zoom to find min_zoom entries (same logic as before)
            tiles_by_zoom = {}
            for (z, x, y), offset in tile_offsets.items():
                tiles_by_zoom.setdefault(z, []).append((z, x, y, offset))
            
            for z, x, y, offset in tiles_by_zoom.get(min_zoom, []):
                # Entry format: zoom (1B), x (4B), y (4B), offset (8B)
                entry = struct.pack('<B', z) + struct.pack('<I', x) + struct.pack('<I', y) + struct.pack('<Q', offset)
                root_entries.append(entry)
            
            f.write(struct.pack('<I', len(root_entries)))  # Number of entries
            for entry in root_entries:
                f.write(entry)
            root_dir_end = f.tell()
            
            # --- Write Metadata (uncompressed) ---
            metadata_start = root_dir_end
            metadata = {
                "name": "Properties", "description": "Property boundaries",
                "minzoom": min_zoom, "maxzoom": max_zoom,
                "center": [-1.0, 5.0, 8], "bounds": [-3.5, 4.5, 1.5, 11.5],
                "format": "json",  # Important: format is "json" (viewer will decompress)
                "type": "overlay",
                "compression": "gzip",  # Optional hint, but helpful
                "generated": str(timezone.now()),
                "tile_count": len(tiles_dict)
            }
            metadata_json = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
            f.write(struct.pack('<I', len(metadata_json)))
            f.write(metadata_json)
            metadata_end = f.tell()
            
            # --- Update Header with correct offsets ---
            f.seek(header_positions['root_dir_offset'])
            f.write(struct.pack('<Q', root_dir_start))
            f.seek(header_positions['root_dir_length'])
            f.write(struct.pack('<Q', root_dir_end - root_dir_start))
            f.seek(header_positions['metadata_offset'])
            f.write(struct.pack('<Q', metadata_start))
            f.seek(header_positions['metadata_length'])
            f.write(struct.pack('<Q', metadata_end - metadata_start))
            f.seek(header_positions['tile_data_offset'])
            f.write(struct.pack('<Q', tile_data_start))
            f.seek(header_positions['tile_data_length'])
            f.write(struct.pack('<Q', tile_data_end - tile_data_start))
            f.seek(header_positions['tile_data_count'])
            f.write(struct.pack('<Q', len(tiles_dict)))
            f.seek(header_positions['tile_data_entries'])
            f.write(struct.pack('<Q', len(tiles_dict)))
            
            self.stdout.write(self.style.SUCCESS(f"PMTiles file created successfully with {len(tiles_dict)} compressed tiles."))