#!/usr/bin/env python3
"""
Download all tiles from a PMTiles server and stitch them into a GeoTIFF
"""

import os
import sys
import requests
import math
import numpy as np
from PIL import Image
import io
import mercantile
import rasterio
from rasterio.transform import from_bounds
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def download_tile(url, z, x, y):
    """Download a single tile"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return (z, x, y, response.content)
    except:
        pass
    return (z, x, y, None)

def pmtiles_to_geotiff(pmtiles_path, output_tif_path, target_zoom=None):
    """
    Convert PMTiles to GeoTIFF by serving locally and downloading tiles
    """
    print(f"\n{'='*60}")
    print(f"🔄 Converting {pmtiles_path} to GeoTIFF")
    print(f"{'='*60}")
    
    # First, let's get the info we already know
    min_lon = -3.176438
    min_lat = 6.788074
    max_lon = -3.155096
    max_lat = 6.800697
    min_zoom = 15
    max_zoom = 20
    
    if target_zoom is None:
        target_zoom = max_zoom
    
    print(f"\n📊 PMTiles Info:")
    print(f"  Bounds: {min_lon:.6f}, {min_lat:.6f}, {max_lon:.6f}, {max_lat:.6f}")
    print(f"  Zoom range: {min_zoom}-{max_zoom}")
    print(f"  Target zoom: {target_zoom}")
    
    # Start the PMTiles server in the background
    import subprocess
    import time
    import signal
    
    print("\n🚀 Starting PMTiles server...")
    server_process = subprocess.Popen(
        ['pmtiles', 'serve', pmtiles_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Calculate all tiles at target zoom
        tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, [target_zoom]))
        print(f"Found {len(tiles)} tiles at zoom {target_zoom}")
        
        if len(tiles) == 0:
            print("❌ No tiles found")
            return False
        
        # Calculate image dimensions
        first_tile = tiles[0]
        tile_bounds = mercantile.bounds(first_tile)
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south
        
        total_width_deg = max_lon - min_lon
        total_height_deg = max_lat - min_lat
        
        width_tiles = int(math.ceil(total_width_deg / tile_width_deg))
        height_tiles = int(math.ceil(total_height_deg / tile_height_deg))
        
        tile_size = 256
        img_width = width_tiles * tile_size
        img_height = height_tiles * tile_size
        
        print(f"\n📐 Creating image: {img_width} x {img_height} pixels")
        print(f"   Grid: {width_tiles} x {height_tiles} tiles")
        
        # Create image array
        img_array = np.zeros((img_height, img_width, 3), dtype=np.uint8)
        
        # Download tiles
        print("\n📥 Downloading tiles...")
        base_url = "http://localhost:8080"
        successful = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for tile in tiles:
                url = f"{base_url}/{tile.z}/{tile.x}/{tile.y}.png"
                futures.append(executor.submit(download_tile, url, tile.z, tile.x, tile.y))
            
            for i, future in enumerate(as_completed(futures)):
                z, x, y, tile_data = future.result()
                
                if tile_data:
                    try:
                        # Convert to image
                        tile_img = Image.open(io.BytesIO(tile_data))
                        tile_array = np.array(tile_img)
                        
                        # Calculate position
                        tile_bounds = mercantile.bounds(x, y, z)
                        tile_x_deg = tile_bounds.west - min_lon
                        tile_y_deg = max_lat - tile_bounds.north
                        
                        x_pos = int((tile_x_deg / tile_width_deg) * tile_size)
                        y_pos = int((tile_y_deg / tile_height_deg) * tile_size)
                        
                        # Handle different formats
                        if len(tile_array.shape) == 2:
                            tile_array = np.stack([tile_array] * 3, axis=2)
                        elif tile_array.shape[2] == 4:
                            tile_array = tile_array[:, :, :3]
                        
                        h, w = tile_array.shape[:2]
                        img_array[y_pos:y_pos+h, x_pos:x_pos+w] = tile_array[:h, :w]
                        successful += 1
                        
                    except Exception as e:
                        print(f"  ⚠️ Error processing tile {z}/{x}/{y}: {e}")
                
                if (i + 1) % 100 == 0:
                    print(f"  Processed {i+1}/{len(tiles)} tiles ({successful} successful)")
        
        print(f"\n✅ Successfully downloaded {successful}/{len(tiles)} tiles")
        
        if successful == 0:
            print("❌ No tiles were downloaded")
            return False
        
        # Save as GeoTIFF
        print("\n💾 Saving GeoTIFF...")
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, img_width, img_height)
        
        with rasterio.open(
            output_tif_path,
            'w',
            driver='GTiff',
            height=img_height,
            width=img_width,
            count=3,
            dtype=img_array.dtype,
            crs='EPSG:4326',
            transform=transform,
            compress='lzw',
            tiled=True,
            blockxsize=256,
            blockysize=256
        ) as dst:
            dst.write(img_array[:, :, 0], 1)
            dst.write(img_array[:, :, 1], 2)
            dst.write(img_array[:, :, 2], 3)
        
        print(f"✅ GeoTIFF saved to: {output_tif_path}")
        
        # Show file size
        size_mb = os.path.getsize(output_tif_path) / (1024 * 1024)
        print(f"📁 File size: {size_mb:.2f} MB")
        
        return True
        
    finally:
        # Stop the server
        print("\n🛑 Stopping PMTiles server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python download_pmtiles.py drone_v2.pmtiles [output.tif]")
        sys.exit(1)
    
    pmtiles_path = sys.argv[1]
    
    if len(sys.argv) == 3:
        output_path = sys.argv[2]
    else:
        output_path = pmtiles_path.replace('.pmtiles', '_converted.tif')
    
    # Install required packages if needed
    try:
        import mercantile
        import rasterio
        import numpy
        from PIL import Image
        import requests
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install mercantile rasterio numpy pillow requests")
        sys.exit(1)
    
    # Kill any process using port 8080
    os.system("fuser -k 8080/tcp 2>/dev/null")
    
    # Run conversion
    success = pmtiles_to_geotiff(pmtiles_path, output_path)
    
    if success:
        print("\n✅ Conversion complete!")
    else:
        print("\n❌ Conversion failed")
        sys.exit(1)