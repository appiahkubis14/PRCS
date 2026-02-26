# core/management/commands/convert_drone_pmtiles.py

import os
import subprocess
import json
import time
import shutil
import sqlite3
import sys
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
        parser.add_argument('--debug', action='store_true', help='Show debug output')

    def check_dependencies(self):
        """Check if required tools are installed"""
        deps = {
            'gdal2tiles.py': ['gdal2tiles.py', '--version'],
            'gdal_translate': ['gdal_translate', '--version'],
            'pmtiles': ['pmtiles', 'version']
        }
        
        all_installed = True
        for name, cmd in deps.items():
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                self.stdout.write(f"✅ {name} found: {result.stdout.strip()[:50]}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                self.stdout.write(self.style.ERROR(f"❌ {name} not found: {e}"))
                all_installed = False
        
        if not all_installed:
            self.stdout.write(self.style.WARNING("\n📦 Installation instructions:"))
            self.stdout.write("  For GDAL tools: sudo apt-get install gdal-bin python3-gdal")
            self.stdout.write("  For pmtiles CLI: wget https://github.com/protomaps/go-pmtiles/releases/download/v1.23.0/go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  tar -xzf go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  sudo mv pmtiles /usr/local/bin/")
        
        return all_installed

    def generate_tiles_with_debug(self, input_file, tile_dir, min_zoom, max_zoom, debug=False):
        """Generate tiles with detailed error logging"""
        self.stdout.write(f"   Generating tiles (zoom {min_zoom}-{max_zoom})...")
        
        # Ensure tile directory is empty
        if os.path.exists(tile_dir):
            shutil.rmtree(tile_dir)
        os.makedirs(tile_dir, exist_ok=True)
        
        # Use a log file to capture output
        log_file = os.path.join(os.path.dirname(tile_dir), 'gdal2tiles.log')
        
        # Build command
        cmd = [
            "gdal2tiles.py",
            "-z", f"{min_zoom}-{max_zoom}",
            "-w", "none",
            input_file,
            tile_dir
        ]
        
        self.stdout.write(f"   Command: {' '.join(cmd)}")
        
        try:
            # Run with output captured
            with open(log_file, 'w') as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Show progress
                for line in process.stdout:
                    f.write(line)
                    if debug:
                        self.stdout.write(f"     {line.strip()}")
                    elif any(x in line for x in ['Generating', '0...10', '100', 'done']):
                        self.stdout.write(f"     {line.strip()}")
                
                process.wait()
            
            # Check return code
            if process.returncode != 0:
                self.stdout.write(self.style.ERROR(f"❌ gdal2tiles failed with code {process.returncode}"))
                
                # Show last few lines of log
                self.stdout.write("\n   📋 Last 10 lines of log:")
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        self.stdout.write(f"     {line.strip()}")
                
                return False
            
            # Count tiles
            tile_count = 0
            for root, dirs, files in os.walk(tile_dir):
                tile_count += len([f for f in files if f.endswith('.png')])
            
            self.stdout.write(self.style.SUCCESS(f"✅ Generated {tile_count} tiles"))
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error generating tiles: {e}"))
            return False

    def create_mbtiles_sqlite(self, tile_dir, mbtiles_path, min_zoom, max_zoom):
        """Create MBTiles file using direct SQLite insertion"""
        self.stdout.write("   Creating MBTiles with SQLite...")
        
        if os.path.exists(mbtiles_path):
            os.remove(mbtiles_path)
        
        try:
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
            
            # Insert metadata
            metadata = [
                ('name', 'Drone Orthomosaic'),
                ('type', 'baselayer'),
                ('version', '1.3'),
                ('description', 'Converted from GeoTIFF'),
                ('format', 'png'),
                ('minzoom', str(min_zoom)),
                ('maxzoom', str(max_zoom)),
                ('bounds', '-180,-85,180,85')
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
                                
                                # Convert TMS y to XYZ y
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
            
            self.stdout.write(f"   ✅ SQLite MBTiles created with {final_count} tiles")
            return final_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ SQLite error: {e}"))
            return 0

    def handle(self, *args, **options):
        input_file = options['input_file']
        output_file = options['output']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        base_temp_dir = options['temp_dir']
        debug = options.get('debug', False)
        
        start_time = time.time()
        
        self.stdout.write("=" * 60)
        self.stdout.write("🚁 DRONE ORTHOMOSAIC TO PMTILES CONVERTER")
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
        
        # Check dependencies
        self.stdout.write("\n🔍 Checking dependencies...")
        if not self.check_dependencies():
            return
        
        # Create output directory
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create temp directories
        os.makedirs(base_temp_dir, exist_ok=True)
        tile_dir = os.path.join(base_temp_dir, 'gdal_tiles')
        mbtiles_path = os.path.join(base_temp_dir, 'final.mbtiles')
        
        success = False
        
        try:
            # METHOD 1: Try direct GeoTIFF to MBTiles (fastest)
            self.stdout.write(f"\n🔄 METHOD 1: Direct GeoTIFF → MBTiles...")
            direct_mbtiles = os.path.join(base_temp_dir, 'direct.mbtiles')
            
            # Simpler command with fewer options
            cmd_direct = [
                'gdal_translate',
                '-of', 'MBTiles',
                '-co', 'TILE_FORMAT=PNG',
                '-co', f'MIN_ZOOM={min_zoom}',
                '-co', f'MAX_ZOOM={max_zoom}',
                '--config', 'GDAL_CACHEMAX', '1024',
                input_file,
                direct_mbtiles
            ]
            
            self.stdout.write(f"📝 Command: {' '.join(cmd_direct)}")
            
            try:
                result = subprocess.run(cmd_direct, capture_output=True, text=True, timeout=600)
                if result.returncode == 0 and os.path.exists(direct_mbtiles) and os.path.getsize(direct_mbtiles) > 1000:
                    self.stdout.write(self.style.SUCCESS("✅ Direct MBTiles created"))
                    shutil.move(direct_mbtiles, mbtiles_path)
                    success = True
                else:
                    self.stdout.write("⚠️ Direct method failed:")
                    if result.stderr:
                        self.stdout.write(f"   Error: {result.stderr[:200]}")
            except Exception as e:
                self.stdout.write(f"⚠️ Direct method error: {e}")
            
            # METHOD 2: Generate tiles then convert to MBTiles
            if not success:
                self.stdout.write(f"\n🔄 METHOD 2: Tiles → MBTiles...")
                
                # Generate tiles with debugging
                tiles_ok = self.generate_tiles_with_debug(
                    input_file, tile_dir, min_zoom, max_zoom, debug
                )
                
                if not tiles_ok:
                    self.stdout.write(self.style.ERROR("❌ Tile generation failed"))
                    
                    # Try with even simpler command
                    self.stdout.write("\n   Attempting with simpler command...")
                    simple_tile_dir = os.path.join(base_temp_dir, 'simple_tiles')
                    
                    cmd_simple = [
                        "gdal2tiles.py",
                        "-z", f"{min_zoom}-{max_zoom}",
                        input_file,
                        simple_tile_dir
                    ]
                    
                    self.stdout.write(f"   Command: {' '.join(cmd_simple)}")
                    
                    try:
                        result = subprocess.run(cmd_simple, capture_output=True, text=True)
                        if result.returncode == 0:
                            self.stdout.write("✅ Simple command succeeded")
                            tile_dir = simple_tile_dir
                            tiles_ok = True
                        else:
                            self.stdout.write(f"❌ Simple command failed: {result.stderr[:200]}")
                            return
                    except Exception as e:
                        self.stdout.write(f"❌ Error: {e}")
                        return
                
                # Create MBTiles from tiles
                self.stdout.write(f"\n   Creating MBTiles from tiles...")
                
                # Try SQLite method directly (more reliable)
                sqlite_count = self.create_mbtiles_sqlite(tile_dir, mbtiles_path, min_zoom, max_zoom)
                
                if sqlite_count > 0:
                    self.stdout.write(self.style.SUCCESS("✅ SQLite method succeeded"))
                    success = True
                else:
                    self.stdout.write(self.style.ERROR("❌ All MBTiles creation methods failed"))
                    return
            
            # Convert MBTiles to PMTiles
            if success and os.path.exists(mbtiles_path):
                self.stdout.write(f"\n📦 Converting MBTiles to PMTiles...")
                
                cmd_pmtiles = ['pmtiles', 'convert', mbtiles_path, output_path]
                result = subprocess.run(cmd_pmtiles, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS("✅ PMTiles created successfully"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ PMTiles conversion failed: {result.stderr}"))
                    return
            else:
                self.stdout.write(self.style.ERROR("❌ No MBTiles file created"))
                return
            
            # Final output
            if os.path.exists(output_path):
                final_size = os.path.getsize(output_path) / (1024 * 1024)
                compression_ratio = (1 - final_size / file_size_mb) * 100 if file_size_mb > 0 else 0
                
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("✅ CONVERSION COMPLETE"))
                self.stdout.write("=" * 60)
                self.stdout.write(f"📁 Output file: {output_path}")
                self.stdout.write(f"📊 File size: {final_size:.2f} MB")
                self.stdout.write(f"📈 Compression: {compression_ratio:.1f}% reduction")
                self.stdout.write(f"🔍 Zoom levels: {min_zoom}-{max_zoom}")
                
                # Show PMTiles info
                try:
                    info = subprocess.run(['pmtiles', 'show', output_path], 
                                        capture_output=True, text=True)
                    if info.stdout:
                        self.stdout.write("\n📋 Archive info:")
                        for line in info.stdout.split('\n')[:10]:
                            if line.strip():
                                self.stdout.write(f"  {line}")
                except:
                    pass
        
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