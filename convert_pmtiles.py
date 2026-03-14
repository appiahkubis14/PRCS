#!/usr/bin/env python3
"""
Convert PMTiles to GeoTIFF using pmtiles CLI.
"""

import os
import sys
import math
import subprocess
import tempfile
import numpy as np
from PIL import Image
import io
import mercantile
import rasterio
from rasterio.transform import from_bounds

def pmtiles_to_geotiff_cli(pmtiles_path, output_tif_path, target_zoom=20):
    print(f"\n{'='*60}")
    print(f"🔄 Converting {pmtiles_path} to GeoTIFF using CLI")
    print(f"{'='*60}")

    # Hardcoded bounds from your pmtiles show output
    min_lon = -3.176438
    min_lat = 6.788074
    max_lon = -3.155096
    max_lat = 6.800697

    print(f"\n📊 Using zoom {target_zoom}, bounds: {min_lon:.6f}, {min_lat:.6f}, {max_lon:.6f}, {max_lat:.6f}")

    # Generate all tile coordinates at target zoom
    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, [target_zoom]))
    print(f"Found {len(tiles)} tiles")

    if len(tiles) == 0:
        print("❌ No tiles found")
        return False

    # Calculate image dimensions
    first_tile = tiles[0]
    tile_bounds = mercantile.bounds(first_tile)
    tile_width_deg = tile_bounds.east - tile_bounds.west
    tile_height_deg = tile_bounds.north - tile_bounds.south

    width_tiles = int(math.ceil((max_lon - min_lon) / tile_width_deg))
    height_tiles = int(math.ceil((max_lat - min_lat) / tile_height_deg))

    tile_size = 256
    img_width = width_tiles * tile_size
    img_height = height_tiles * tile_size

    print(f"Creating image: {img_width} x {img_height} pixels")

    # Create image array
    img_array = np.zeros((img_height, img_width, 3), dtype=np.uint8)

    # Extract tiles using pmtiles CLI
    print("\n📥 Extracting tiles...")
    successful = 0

    for i, tile in enumerate(tiles):
        z, x, y = tile.z, tile.x, tile.y
        try:
            # Run pmtiles tile command
            cmd = ['pmtiles', 'tile', pmtiles_path, str(z), str(x), str(y)]
            result = subprocess.run(cmd, capture_output=True, check=True)

            if result.stdout:
                tile_data = result.stdout
                tile_img = Image.open(io.BytesIO(tile_data))
                tile_array = np.array(tile_img)

                # Calculate position
                tile_bounds = mercantile.bounds(x, y, z)
                tile_x_deg = tile_bounds.west - min_lon
                tile_y_deg = max_lat - tile_bounds.north

                x_pos = int((tile_x_deg / tile_width_deg) * tile_size)
                y_pos = int((tile_y_deg / tile_height_deg) * tile_size)

                # Handle formats
                if len(tile_array.shape) == 2:
                    tile_array = np.stack([tile_array] * 3, axis=2)
                elif tile_array.shape[2] == 4:
                    tile_array = tile_array[:, :, :3]

                h, w = tile_array.shape[:2]
                img_array[y_pos:y_pos+h, x_pos:x_pos+w] = tile_array[:h, :w]
                successful += 1

        except subprocess.CalledProcessError as e:
            # Tile not found or error – skip
            if e.stderr:
                pass
        except Exception as e:
            pass

        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(tiles)} tiles ({successful} successful)")

    print(f"\n✅ Extracted {successful}/{len(tiles)} tiles")

    if successful == 0:
        print("❌ No tiles extracted. Ensure pmtiles CLI works and tile paths are correct.")
        return False

    # Save GeoTIFF
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
        compress='lzw'
    ) as dst:
        dst.write(img_array[:, :, 0], 1)
        dst.write(img_array[:, :, 1], 2)
        dst.write(img_array[:, :, 2], 3)

    print(f"✅ GeoTIFF saved: {output_tif_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pmtiles_to_geotiff_cli.py drone_v2.pmtiles [output.tif]")
        sys.exit(1)

    pmtiles_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >= 3 else pmtiles_path.replace('.pmtiles', '_converted.tif')

    # Optionally specify zoom as third argument
    target_zoom = 20
    if len(sys.argv) >= 4:
        target_zoom = int(sys.argv[3])

    success = pmtiles_to_geotiff_cli(pmtiles_path, output_path, target_zoom)

    if success:
        print("\n✅ Conversion complete!")
    else:
        print("\n❌ Conversion failed")
        sys.exit(1)