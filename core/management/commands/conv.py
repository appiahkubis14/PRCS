# core/management/commands/convert_drone_pmtiles.py

import os
import subprocess
import json
import time
import shutil
import sqlite3
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Convert drone orthomosaic to PMTiles'

    def add_arguments(self, parser):
        parser.add_argument('input_file', type=str, help='Path to input GeoTIFF file')
        parser.add_argument('--output', type=str, default='drone_map.pmtiles')
        parser.add_argument('--min-zoom', type=int, default=15)
        parser.add_argument('--max-zoom', type=int, default=20)
        parser.add_argument('--temp-dir', type=str, default='temp_pmtiles_conversion')

    def check_dependencies(self):
        """Check if required tools are installed"""
        deps = {
            'gdal_translate': ['gdal_translate', '--version'],
            'gdalinfo': ['gdalinfo', '--version'],
            'pmtiles': ['pmtiles', 'version']
        }
        
        all_installed = True
        for name, cmd in deps.items():
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                self.stdout.write(f"✅ {name} found")
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.stdout.write(self.style.ERROR(f"❌ {name} not found"))
                all_installed = False
        
        if not all_installed:
            self.stdout.write(self.style.WARNING("\n📦 Installation instructions:"))
            self.stdout.write("  For GDAL: sudo apt-get install gdal-bin")
            self.stdout.write("  For pmtiles: wget https://github.com/protomaps/go-pmtiles/releases/download/v1.23.0/go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  tar -xzf go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  sudo mv pmtiles /usr/local/bin/")
        
        return all_installed

    def get_raster_bounds(self, input_file):
        """Extract actual bounds from GeoTIFF using gdalinfo"""
        self.stdout.write("   Extracting bounds from GeoTIFF...")
        
        try:
            # Get bounds in WGS84
            cmd = ['gdalinfo', '-json', input_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # Try to get WGS84 bounds first
            if 'wgs84Extent' in info:
                coords = info['wgs84Extent']['coordinates'][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                bounds = [min(lons), min(lats), max(lons), max(lats)]
                self.stdout.write(f"   ✅ Bounds: {bounds}")
                return bounds
            
            # Fallback to corner coordinates
            elif 'cornerCoordinates' in info:
                corners = info['cornerCoordinates']
                bounds = [
                    corners['lowerLeft'][0],
                    corners['lowerLeft'][1],
                    corners['upperRight'][0],
                    corners['upperRight'][1]
                ]
                self.stdout.write(f"   ✅ Bounds: {bounds}")
                return bounds
            
        except Exception as e:
            self.stdout.write(f"   ⚠️ Could not extract bounds: {e}")
        
        # Default fallback (you can change this to your area)
        self.stdout.write("   ⚠️ Using default bounds")
        return [-180, -85, 180, 85]

    def create_mbtiles_from_tiles(self, tile_dir, mbtiles_path, min_zoom, max_zoom, bounds):
        """Create MBTiles from a directory of tiles using SQLite with correct bounds"""
        self.stdout.write("   Creating MBTiles database...")
        
        if os.path.exists(mbtiles_path):
            os.remove(mbtiles_path)
        
        conn = sqlite3.connect(mbtiles_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE metadata (
                name TEXT,
                value TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE tiles (
                zoom_level INTEGER,
                tile_column INTEGER,
                tile_row INTEGER,
                tile_data BLOB
            )
        ''')
        
        cursor.execute('CREATE INDEX tiles_index ON tiles (zoom_level, tile_column, tile_row)')
        
        # Format bounds for MBTiles metadata
        bounds_str = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Insert metadata with CORRECT bounds
        metadata = [
            ('name', 'Drone Orthomosaic'),
            ('type', 'baselayer'),
            ('version', '1.3'),
            ('description', 'Converted from GeoTIFF'),
            ('format', 'png'),
            ('minzoom', str(min_zoom)),
            ('maxzoom', str(max_zoom)),
            ('bounds', bounds_str),
            ('center', f"{center_lon},{center_lat},{min_zoom}")
        ]
        
        for name, value in metadata:
            cursor.execute('INSERT INTO metadata (name, value) VALUES (?, ?)', (name, value))
        
        # Insert tiles
        tile_count = 0
        for root, dirs, files in os.walk(tile_dir):
            for file in files:
                if file.endswith('.png'):
                    try:
                        # Parse path: .../z/x/y.png
                        rel_path = os.path.relpath(os.path.join(root, file), tile_dir)
                        parts = rel_path.split(os.sep)
                        
                        if len(parts) == 3:
                            z = int(parts[0])
                            x = int(parts[1])
                            y = int(parts[2].replace('.png', ''))
                            
                            # Convert TMS y to XYZ y (flip Y coordinate)
                            y_tms = (1 << z) - 1 - y
                            
                            with open(os.path.join(root, file), 'rb') as f:
                                tile_data = f.read()
                            
                            cursor.execute(
                                'INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)',
                                (z, x, y_tms, tile_data)
                            )
                            
                            tile_count += 1
                            if tile_count % 500 == 0:
                                conn.commit()
                                self.stdout.write(f"      Inserted {tile_count} tiles...")
                    except Exception as e:
                        self.stdout.write(f"      Warning: Could not insert {file}: {e}")
        
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM tiles')
        final_count = cursor.fetchone()[0]
        conn.close()
        
        self.stdout.write(f"   ✅ MBTiles created with {final_count} tiles")
        self.stdout.write(f"   📍 Bounds: {bounds_str}")
        return final_count

    def generate_tiles_with_gdal(self, input_file, tile_dir, min_zoom, max_zoom):
        """Generate tiles using gdal2tiles"""
        self.stdout.write("   Generating tiles with gdal2tiles...")
        
        cmd = [
            "gdal2tiles.py",
            "-z", f"{min_zoom}-{max_zoom}",
            "-w", "none",
            input_file,
            tile_dir
        ]
        
        self.stdout.write(f"   Command: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if line and ('Generating' in line or '...' in line):
                    if '0...10' in line or '100' in line or 'done' in line:
                        self.stdout.write(f"     {line}")
            
            process.wait()
            
            if process.returncode != 0:
                return False
            
            # Count tiles
            tile_count = 0
            for root, dirs, files in os.walk(tile_dir):
                tile_count += len([f for f in files if f.endswith('.png')])
            
            self.stdout.write(f"   ✅ Generated {tile_count} tiles")
            return True
            
        except Exception as e:
            self.stdout.write(f"   ❌ Error generating tiles: {e}")
            return False

    def update_pmtiles_metadata(self, pmtiles_path, bounds, min_zoom, max_zoom):
        """Update PMTiles metadata with correct bounds"""
        self.stdout.write("   Updating PMTiles metadata...")
        
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        metadata = {
            "bounds": [bounds[0], bounds[1], bounds[2], bounds[3]],
            "center": [center_lon, center_lat, min_zoom],
            "minzoom": min_zoom,
            "maxzoom": max_zoom
        }
        
        # Create temp metadata file
        metadata_path = os.path.join(os.path.dirname(pmtiles_path), 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        try:
            subprocess.run(['pmtiles', 'metadata', pmtiles_path, '--set', f'@{metadata_path}'], 
                         capture_output=True, check=True)
            self.stdout.write("   ✅ Metadata updated")
        except Exception as e:
            self.stdout.write(f"   ⚠️ Could not update metadata: {e}")
        finally:
            if os.path.exists(metadata_path):
                os.remove(metadata_path)

    def handle(self, *args, **options):
        input_file = options['input_file']
        output_file = options['output']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        base_temp_dir = options['temp_dir']
        
        start_time = time.time()
        
        self.stdout.write("=" * 60)
        self.stdout.write("🚁 DRONE TO PMTILES CONVERTER")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Input file: {input_file}")
        self.stdout.write(f"Output file: {output_file}")
        self.stdout.write(f"Zoom levels: {min_zoom} to {max_zoom}")
        self.stdout.write("=" * 60)
        
        # Check input file
        if not os.path.exists(input_file):
            self.stdout.write(self.style.ERROR(f"❌ Input file not found: {input_file}"))
            return
        
        # Check file size
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        self.stdout.write(f"📁 Input file size: {file_size_mb:.2f} MB")
        
        # Get actual bounds from the GeoTIFF
        bounds = self.get_raster_bounds(input_file)
        
        # Check dependencies
        self.stdout.write("\n🔍 Checking dependencies...")
        if not self.check_dependencies():
            return
        
        # Create output directory
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create temp directories
        os.makedirs(base_temp_dir, exist_ok=True)
        tile_dir = os.path.join(base_temp_dir, 'tiles')
        mbtiles_path = os.path.join(base_temp_dir, 'output.mbtiles')
        
        success = False
        
        try:
            # METHOD 1: Try direct MBTiles creation
            self.stdout.write(f"\n🔄 Attempting direct MBTiles creation...")
            direct_mbtiles = os.path.join(base_temp_dir, 'direct.mbtiles')
            
            cmd_direct = [
                'gdal_translate',
                '-of', 'MBTiles',
                input_file,
                direct_mbtiles
            ]
            
            self.stdout.write(f"   Command: {' '.join(cmd_direct)}")
            
            try:
                result = subprocess.run(cmd_direct, capture_output=True, text=True, timeout=600)
                if result.returncode == 0 and os.path.exists(direct_mbtiles) and os.path.getsize(direct_mbtiles) > 1000:
                    self.stdout.write(self.style.SUCCESS("✅ Direct MBTiles created"))
                    
                    # Convert to PMTiles
                    self.stdout.write(f"\n📦 Converting to PMTiles...")
                    subprocess.run(['pmtiles', 'convert', direct_mbtiles, output_path], check=True)
                    
                    # Update metadata with correct bounds
                    self.update_pmtiles_metadata(output_path, bounds, min_zoom, max_zoom)
                    
                    self.stdout.write(self.style.SUCCESS("✅ PMTiles created"))
                    success = True
                else:
                    self.stdout.write("   ⚠️ Direct method failed, using tile method...")
            except Exception as e:
                self.stdout.write(f"   ⚠️ Direct method error: {e}")
            
            # METHOD 2: Generate tiles and convert
            if not success:
                self.stdout.write(f"\n🔄 Using tile-based method...")
                
                # Clean and create tile directory
                if os.path.exists(tile_dir):
                    shutil.rmtree(tile_dir)
                os.makedirs(tile_dir, exist_ok=True)
                
                # Generate tiles
                tiles_ok = self.generate_tiles_with_gdal(input_file, tile_dir, min_zoom, max_zoom)
                
                if not tiles_ok:
                    self.stdout.write(self.style.ERROR("❌ Failed to generate tiles"))
                    return
                
                # Create MBTiles from tiles with correct bounds
                self.stdout.write(f"\n🔄 Creating MBTiles from tiles...")
                tile_count = self.create_mbtiles_from_tiles(tile_dir, mbtiles_path, min_zoom, max_zoom, bounds)
                
                if tile_count == 0:
                    self.stdout.write(self.style.ERROR("❌ Failed to create MBTiles"))
                    return
                
                # Convert to PMTiles
                self.stdout.write(f"\n📦 Converting to PMTiles...")
                result = subprocess.run(['pmtiles', 'convert', mbtiles_path, output_path], 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS("✅ PMTiles created"))
                    
                    # Update metadata with correct bounds (though MBTiles should have them)
                    self.update_pmtiles_metadata(output_path, bounds, min_zoom, max_zoom)
                    
                    success = True
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Conversion failed: {result.stderr}"))
                    return
            
            # Final output
            if success and os.path.exists(output_path):
                final_size = os.path.getsize(output_path) / (1024 * 1024)
                compression_ratio = (1 - final_size / file_size_mb) * 100 if file_size_mb > 0 else 0
                
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("✅ CONVERSION COMPLETE"))
                self.stdout.write("=" * 60)
                self.stdout.write(f"📁 Output file: {output_path}")
                self.stdout.write(f"📊 File size: {final_size:.2f} MB")
                self.stdout.write(f"📈 Compression: {compression_ratio:.1f}% reduction")
                self.stdout.write(f"🔍 Zoom levels: {min_zoom}-{max_zoom}")
                self.stdout.write(f"📍 Bounds: {bounds}")
                
                # Show PMTiles info
                try:
                    info = subprocess.run(['pmtiles', 'show', output_path], 
                                        capture_output=True, text=True)
                    if info.stdout:
                        self.stdout.write("\n📋 Archive info:")
                        for line in info.stdout.split('\n')[:15]:
                            if line.strip():
                                self.stdout.write(f"  {line}")
                except:
                    pass
                
                self.stdout.write("\n👉 To view: Drag and drop the file to https://pmtiles.io")
                self.stdout.write(f"   Or use: pmtiles serve {output_path}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
        
        finally:
            # Clean up
            self.stdout.write("\n🧹 Cleaning up...")
            if os.path.exists(base_temp_dir):
                try:
                    shutil.rmtree(base_temp_dir)
                    self.stdout.write("✅ Cleanup complete")
                except:
                    self.stdout.write("⚠️ Could not remove temp directory")
        
        total_time = time.time() - start_time
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✨ Total time: {total_time:.1f} seconds"))
        self.stdout.write("=" * 60)