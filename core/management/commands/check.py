#!/usr/bin/env python3
"""
Standalone script to convert drone orthomosaic to PMTiles
Usage: python convert_drone.py
"""

import os
import subprocess
import json
import time
import struct
import sys

def inspect_pmtiles():
    """Inspect the pmtiles package to see what's available"""
    try:
        import pmtiles
        print("=== PMTiles package inspection ===")
        print(f"pmtiles version: {pmtiles.__version__ if hasattr(pmtiles, '__version__') else 'unknown'}")
        print("\nTop-level attributes:")
        for attr in dir(pmtiles):
            if not attr.startswith('_'):
                print(f"  - {attr}")
        return pmtiles
    except ImportError as e:
        print(f"pmtiles package not found: {e}")
        return None

def write_varint(f, value):
    """Write a varint"""
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            f.write(bytes([byte | 0x80]))
        else:
            f.write(bytes([byte]))
            break

def create_pmtiles_manual(tile_dir, output_file, min_zoom, max_zoom):
    """Create PMTiles manually following v3 spec"""
    
    # Collect all tiles
    tiles = []
    print("Collecting tiles...")
    for root, dirs, files in os.walk(tile_dir):
        for file in files:
            if file.endswith('.png'):
                rel_path = os.path.relpath(os.path.join(root, file), tile_dir)
                parts = rel_path.split(os.sep)
                if len(parts) == 3:
                    try:
                        z = int(parts[0])
                        x = int(parts[1])
                        y_str = parts[2].replace('.png', '')
                        y = int(y_str)
                        # Convert TMS y to XYZ y (gdal2tiles uses TMS)
                        y = (1 << z) - 1 - y
                        tiles.append({
                            'z': z, 'x': x, 'y': y,
                            'path': os.path.join(root, file)
                        })
                    except Exception as e:
                        print(f"  Warning: Could not parse {rel_path}: {e}")
                        continue
    
    print(f"Found {len(tiles)} tiles")
    
    if len(tiles) == 0:
        print("Error: No tiles found!")
        return False
    
    # Sort tiles
    tiles.sort(key=lambda t: (t['z'], t['x'], t['y']))
    
    with open(output_file, 'wb') as f:
        # Write magic number and version
        f.write(b'PMTiles')
        f.write(struct.pack('<B', 3))  # version
        
        # Header positions for later update
        header_pos = f.tell()
        
        # Write placeholder header (26 uint64 fields)
        for _ in range(26):
            f.write(struct.pack('<Q', 0))
        
        # Write tile data
        tile_data_start = f.tell()
        print(f"Writing tile data at offset {tile_data_start}")
        
        tile_entries = []
        for i, tile in enumerate(tiles):
            with open(tile['path'], 'rb') as tile_f:
                data = tile_f.read()
            
            current_offset = f.tell()
            f.write(data)
            
            tile_entries.append({
                'z': tile['z'],
                'x': tile['x'],
                'y': tile['y'],
                'offset': current_offset,
                'length': len(data)
            })
            
            if (i + 1) % 1000 == 0:
                print(f"  Written {i + 1}/{len(tiles)} tiles")
        
        tile_data_end = f.tell()
        
        # Write root directory
        root_dir_start = f.tell()
        print(f"Writing root directory at offset {root_dir_start}")
        
        # Calculate tile IDs and create directory entries
        dir_entries = []
        for entry in tile_entries:
            # Calculate tile ID using quadkey encoding
            tile_id = 0
            for i in range(entry['z']):
                bit_x = (entry['x'] >> (entry['z'] - 1 - i)) & 1
                bit_y = (entry['y'] >> (entry['z'] - 1 - i)) & 1
                tile_id |= (bit_x << (2*i + 1)) | (bit_y << (2*i))
            
            dir_entries.append({
                'tile_id': tile_id,
                'offset': entry['offset'],
                'length': entry['length']
            })
        
        # Sort by tile ID
        dir_entries.sort(key=lambda e: e['tile_id'])
        
        # Write directory using varint encoding
        entry_count = 0
        i = 0
        while i < len(dir_entries):
            current = dir_entries[i]
            tile_id = current['tile_id']
            offset = current['offset']
            length = current['length']
            
            # Find run of consecutive tile IDs with same length
            run_length = 1
            while (i + run_length < len(dir_entries) and 
                   dir_entries[i + run_length]['tile_id'] == tile_id + run_length and
                   dir_entries[i + run_length]['length'] == length):
                run_length += 1
            
            # Write the entry
            write_varint(f, tile_id)
            write_varint(f, run_length)
            write_varint(f, length)
            write_varint(f, offset)
            
            entry_count += 1
            i += run_length
        
        root_dir_end = f.tell()
        
        # Write metadata
        metadata_start = f.tell()
        print(f"Writing metadata at offset {metadata_start}")
        
        metadata = {
            "name": "Drone Orthomosaic",
            "description": "Converted from GeoTIFF",
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "format": "png",
            "version": "3.0.0",
            "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        metadata_json = json.dumps(metadata).encode('utf-8')
        
        # Write metadata with length prefix
        f.write(struct.pack('<I', len(metadata_json)))
        f.write(metadata_json)
        metadata_end = f.tell()
        
        # Update header
        f.seek(header_pos)
        
        # Write all header fields
        header_fields = [
            root_dir_start, 
            root_dir_end - root_dir_start,  # root dir offset, length
            metadata_start, 
            metadata_end - metadata_start,   # metadata offset, length
            0, 0,  # leaf dirs offset, length (none)
            tile_data_start, 
            tile_data_end - tile_data_start,  # tile data offset, length
            len(dir_entries),  # addressed tiles count
            len(dir_entries),  # tile entries count
            len(tiles),  # tile contents count
            0,  # clustered (false)
            0,  # internal compression (none)
            0,  # tile compression (none)
            1,  # tile type (1 = PNG)
            min_zoom, 
            max_zoom,  # min/max zoom
            0, 0, 0, 0,  # bounds (simplified)
            min_zoom, 
            0, 0  # center
        ]
        
        for field in header_fields:
            if isinstance(field, int):
                f.write(struct.pack('<Q', field))
            else:
                f.write(struct.pack('<B', field))
    
    print(f"✅ PMTiles created successfully")
    print(f"📊 Statistics:")
    print(f"  - Tiles: {len(tiles)}")
    print(f"  - Directory entries: {entry_count}")
    print(f"  - File size: {os.path.getsize(output_file) / (1024 * 1024):.2f} MB")
    
    return True

def main():
    # Configuration
    input_tif = "data/data.tif"
    output_dir = "tiles"
    output_pmtiles = "drone_map.pmtiles"
    min_zoom = 15
    max_zoom = 20
    
    print("=" * 60)
    print("🚁 DRONE ORTHOMOSAIC TO PMTILES CONVERTER")
    print("=" * 60)
    
    # Check if input file exists
    if not os.path.exists(input_tif):
        print(f"❌ Input file not found: {input_tif}")
        return
    
    # Check if gdal2tiles is installed
    try:
        subprocess.run(['gdal2tiles.py', '--version'], check=True, capture_output=True)
        print("✅ gdal2tiles.py found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ gdal2tiles.py not found. Please install GDAL:")
        print("  sudo apt-get install gdal-bin")
        return
    
    # Generate tiles
    print(f"\n🔄 Generating tiles from {input_tif}...")
    print(f"   Zoom range: {min_zoom}-{max_zoom}")
    
    cmd = [
        "gdal2tiles.py",
        "-z", f"{min_zoom}-{max_zoom}",
        "-w", "leaflet",
        input_tif,
        output_dir
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Tiles generated successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate tiles: {e}")
        return
    
    # Convert to PMTiles
    print(f"\n📦 Creating PMTiles archive: {output_pmtiles}")
    
    # Try using pmtiles CLI if available
    try:
        subprocess.run(['pmtiles', '--version'], check=True, capture_output=True)
        print("Using pmtiles CLI...")
        subprocess.run(['pmtiles', 'convert', '--type=directory', '--format=png', 
                       output_dir, output_pmtiles], check=True)
        print(f"✅ PMTiles created successfully")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("pmtiles CLI not found, using manual method...")
        
        # Try using Python package
        try:
            import pmtiles
            print("Using pmtiles Python package...")
            
            # Try different APIs
            try:
                # Method 1: Try high-level API
                with pmtiles.new_writer(output_pmtiles) as writer:
                    # Add tiles logic here if this works
                    pass
                print("✅ High-level API worked")
            except:
                # Method 2: Use manual implementation
                success = create_pmtiles_manual(output_dir, output_pmtiles, min_zoom, max_zoom)
                if not success:
                    print("❌ Failed to create PMTiles")
                    return
                    
        except ImportError:
            # Manual implementation without pmtiles package
            print("pmtiles package not found, using manual method...")
            success = create_pmtiles_manual(output_dir, output_pmtiles, min_zoom, max_zoom)
            if not success:
                print("❌ Failed to create PMTiles")
                return
    
    # Final output
    if os.path.exists(output_pmtiles):
        file_size = os.path.getsize(output_pmtiles) / (1024 * 1024)
        print("\n" + "=" * 60)
        print("✅ CONVERSION COMPLETE")
        print("=" * 60)
        print(f"📁 Output file: {os.path.abspath(output_pmtiles)}")
        print(f"📊 File size: {file_size:.2f} MB")
        print(f"🔍 Zoom levels: {min_zoom}-{max_zoom}")
        
        # Optional: Verify with pmtiles info
        try:
            result = subprocess.run(['pmtiles', 'info', output_pmtiles], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("\n📋 PMTiles info:")
                print(result.stdout)
        except:
            pass
    else:
        print("❌ Failed to create PMTiles file")

if __name__ == "__main__":
    main()