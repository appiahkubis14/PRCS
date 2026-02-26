# core/management/commands/convert_drone_rio.py

import os
import subprocess
import json
import time
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Convert drone orthomosaic to PMTiles using rio-pmtiles'

    def add_arguments(self, parser):
        parser.add_argument('input_file', type=str, help='Path to input GeoTIFF file')
        parser.add_argument('--output', type=str, default='drone.pmtiles', help='Output PMTiles filename')
        parser.add_argument('--min-zoom', type=int, default=10, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=20, help='Maximum zoom level')
        parser.add_argument('--name', type=str, default='Drone Orthomosaic', help='Name in metadata')
        parser.add_argument('--description', type=str, default='Converted from GeoTIFF using rio-pmtiles', help='Description in metadata')
        parser.add_argument('--format', type=str, default='PNG', choices=['PNG', 'JPEG', 'WEBP'], help='Tile image format')
        parser.add_argument('--tile-size', type=int, default=256, help='Tile size in pixels')
        parser.add_argument('--resampling', type=str, default='cubic', 
                          choices=['nearest', 'bilinear', 'cubic', 'cubic_spline', 'lanczos', 'average'],
                          help='Resampling method')
        parser.add_argument('--quality', type=int, default=75, help='JPEG/WEBP quality (10-100)')
        parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
        parser.add_argument('--overlay', action='store_true', default=True, help='Export as overlay (not baselayer)')
        parser.add_argument('--exclude-empty', action='store_true', default=True, help='Exclude empty tiles')

    def check_dependencies(self):
        """Check if required tools are installed"""
        deps_ok = True
        
        # Check rio-pmtiles
        try:
            result = subprocess.run(['rio', 'pmtiles', '--help'], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                self.stdout.write("✅ rio-pmtiles found")
            else:
                self.stdout.write(self.style.ERROR("❌ rio-pmtiles not working properly"))
                deps_ok = False
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("❌ rio-pmtiles not found"))
            deps_ok = False
        
        # Check pmtiles CLI (optional, for verification)
        try:
            subprocess.run(['pmtiles', 'version'], capture_output=True, check=True)
            self.stdout.write("✅ pmtiles CLI found (optional)")
        except:
            self.stdout.write("⚠️ pmtiles CLI not found (optional, for verification)")
        
        if not deps_ok:
            self.stdout.write(self.style.WARNING("\n📦 Installation instructions:"))
            self.stdout.write("  pip install rio-pmtiles")
            self.stdout.write("  # Optional: install pmtiles CLI for verification")
            self.stdout.write("  wget https://github.com/protomaps/go-pmtiles/releases/download/v1.23.0/go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  tar -xzf go-pmtiles_1.23.0_Linux_x86_64.tar.gz")
            self.stdout.write("  sudo mv pmtiles /usr/local/bin/")
        
        return deps_ok

    def get_raster_info(self, input_file):
        """Get basic info about the raster file"""
        try:
            cmd = ['gdalinfo', '-json', input_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            raster_info = {
                'size': info.get('size', [0, 0]),
                'bands': len(info.get('bands', [])),
                'driver': info.get('driver', {}).get('longName', 'Unknown')
            }
            
            # Try to get bounds
            if 'wgs84Extent' in info:
                coords = info['wgs84Extent']['coordinates'][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                raster_info['bounds'] = [min(lons), min(lats), max(lons), max(lats)]
            elif 'cornerCoordinates' in info:
                corners = info['cornerCoordinates']
                raster_info['bounds'] = [
                    corners['lowerLeft'][0],
                    corners['lowerLeft'][1],
                    corners['upperRight'][0],
                    corners['upperRight'][1]
                ]
            
            return raster_info
        except:
            return None

    def handle(self, *args, **options):
        input_file = options['input_file']
        output_file = options['output']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        name = options['name']
        description = options['description']
        img_format = options['format']
        tile_size = options['tile_size']
        resampling = options['resampling']
        quality = options['quality']
        workers = options['workers']
        
        start_time = time.time()
        
        self.stdout.write("=" * 70)
        self.stdout.write("🚁 DRONE TO PMTILES CONVERTER (rio-pmtiles)")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Input file: {input_file}")
        self.stdout.write(f"Output file: {output_file}")
        self.stdout.write(f"Zoom levels: {min_zoom} to {max_zoom}")
        self.stdout.write(f"Format: {img_format}")
        self.stdout.write(f"Tile size: {tile_size}px")
        self.stdout.write(f"Resampling: {resampling}")
        self.stdout.write("=" * 70)
        
        # Check if input file exists
        if not os.path.exists(input_file):
            self.stdout.write(self.style.ERROR(f"❌ Input file not found: {input_file}"))
            return
        
        # Check file size
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        self.stdout.write(f"📁 Input file size: {file_size_mb:.2f} MB")
        
        # Get raster info
        raster_info = self.get_raster_info(input_file)
        if raster_info:
            self.stdout.write(f"📊 Raster info:")
            self.stdout.write(f"   - Dimensions: {raster_info.get('size', ['?','?'])}")
            self.stdout.write(f"   - Bands: {raster_info.get('bands', '?')}")
            self.stdout.write(f"   - Driver: {raster_info.get('driver', '?')}")
            if 'bounds' in raster_info:
                self.stdout.write(f"   - Bounds: {raster_info['bounds']}")
        
        # Check dependencies
        self.stdout.write("\n🔍 Checking dependencies...")
        if not self.check_dependencies():
            return
        
        # Create output directory
        output_path = os.path.join(settings.BASE_DIR, 'static', 'tiles', output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Build the rio-pmtiles command (the working syntax)
        cmd = [
            'rio', 'pmtiles',
            '--zoom-levels', f'{min_zoom}..{max_zoom}',
            '--format', img_format,
            '--tile-size', str(tile_size),
            '--resampling', resampling,
            '--name', name,
            '--description', description,
        ]
        
        # Add optional flags
        if options['overlay']:
            cmd.append('--overlay')
        
        if options['exclude_empty']:
            cmd.append('--exclude-empty-tiles')
        
        # Add quality for JPEG/WEBP
        if img_format in ['JPEG', 'WEBP'] and quality:
            cmd.extend(['--co', f'QUALITY={quality}'])
        
        # Add number of workers
        if workers:
            cmd.extend(['-j', str(workers)])
        
        # Add input and output
        cmd.extend([input_file, output_path])
        
        self.stdout.write(f"\n🔄 Running rio-pmtiles...")
        self.stdout.write(f"📝 Command: {' '.join(cmd)}")
        
        try:
            # Run with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Show progress
            tile_count = 0
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Show progress updates
                    if '%' in line:
                        self.stdout.write(f"  {line}")
                    elif 'tile' in line.lower() and 'writing' in line.lower():
                        tile_count += 1
                        if tile_count % 100 == 0:
                            self.stdout.write(f"  Processed {tile_count} tiles...")
                    elif 'error' in line.lower():
                        self.stdout.write(self.style.ERROR(f"  ⚠️ {line}"))
                    else:
                        # Only show important messages
                        if any(keyword in line.lower() for keyword in ['zoom', 'complete', 'done', 'finish']):
                            self.stdout.write(f"  {line}")
            
            process.wait()
            
            if process.returncode != 0:
                self.stdout.write(self.style.ERROR("❌ rio-pmtiles failed"))
                return
            
            self.stdout.write(self.style.SUCCESS("\n✅ PMTiles created successfully"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            return
        
        # Final output
        if os.path.exists(output_path):
            final_size = os.path.getsize(output_path) / (1024 * 1024)
            compression_ratio = (1 - final_size / file_size_mb) * 100 if file_size_mb > 0 else 0
            
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS("✅ CONVERSION COMPLETE"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"📁 Output file: {output_path}")
            self.stdout.write(f"📊 File size: {final_size:.2f} MB")
            self.stdout.write(f"📈 Compression: {compression_ratio:.1f}% reduction")
            self.stdout.write(f"🔍 Zoom levels: {min_zoom}-{max_zoom}")
            
            # Show PMTiles info using pmtiles CLI if available
            try:
                info = subprocess.run(['pmtiles', 'show', output_path], 
                                    capture_output=True, text=True)
                if info.returncode == 0 and info.stdout:
                    self.stdout.write("\n📋 PMTiles archive info:")
                    for line in info.stdout.split('\n')[:15]:
                        if line.strip():
                            self.stdout.write(f"  {line}")
            except:
                pass
            
            self.stdout.write("\n👉 To view:")
            self.stdout.write(f"   1. Drag and drop to https://pmtiles.io")
            self.stdout.write(f"   2. Or run: pmtiles serve {output_path}")
            self.stdout.write(f"   3. Or use in MapLibre with: pmtiles://{output_path}")
        
        total_time = time.time() - start_time
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✨ Total time: {total_time:.1f} seconds"))
        self.stdout.write("=" * 70)