from django.apps import AppConfig
import threading
import json
from django.core.cache import cache
import time
import os

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    # Class variable to track if thread has been started
    _loading_thread_started = False
    _loading_lock = threading.Lock()
    
    def ready(self):
        # Avoid running in management commands or migrations
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('DJANGO_AUTORELOAD') == 'true':
            return
        
        # Avoid starting multiple threads
        with CoreConfig._loading_lock:
            if CoreConfig._loading_thread_started:
                return
            CoreConfig._loading_thread_started = True
        
        # Check if data already exists in cache
        if cache.get('properties_geojson_final') is not None and cache.get('properties_list_final') is not None:
            print("Data already cached, skipping background loading")
            return
        
        # Start background thread to load data
        def load_data_in_background():
            # Wait for database to be ready
            time.sleep(5)
            
            try:
                from core.models import Polygon
                
                # Check again in case data was loaded during the sleep
                if cache.get('properties_geojson_final') is not None and cache.get('properties_list_final') is not None:
                    print("Data already cached during wait, skipping")
                    return
                
                fields = ['id', 'address', 'district', 'region', 'zone', 'property_type', 
                         'area', 'area_in_me', 'status', 'latitude', 'longitude', 
                         'g_code', 'postcode', 'street', 'gpsname']
                
                total = Polygon.objects.count()
                print(f"Starting to load {total} properties...")
                
                # Set initial loading flag
                cache.set('properties_loading', True, timeout=None)
                
                # Process in chunks
                chunk_size = 5000
                features = []
                all_properties = []
                
                for offset in range(0, total, chunk_size):
                    print(f"Loading chunk {offset} to {offset+chunk_size}")
                    properties = list(Polygon.objects.all()[offset:offset + chunk_size])
                    
                    for prop in properties:
                        # Process GeoJSON feature
                        feature = {
                            "type": "Feature",
                            "geometry": json.loads(prop.geom.geojson) if prop.geom else None,
                            "properties": {}
                        }
                        
                        for field in fields:
                            if hasattr(prop, field):
                                value = getattr(prop, field)
                                if value is not None:
                                    feature['properties'][field] = str(value)
                        
                        if feature['geometry']:
                            features.append(feature)
                        
                        # Process property list data
                        prop_data = {
                            'id': prop.id,
                            'address': prop.address,
                            'g_code': prop.g_code,
                            'gpsname': prop.gpsname,
                            'area_in_me': float(prop.area_in_me) if prop.area_in_me else None,
                            'region': prop.region,
                            'district': prop.district,
                            'postcode': prop.postcode,
                            'street': prop.street,
                            'area': str(prop.area) if prop.area else None,
                            'latitude': float(prop.latitude) if prop.latitude else None,
                            'longitude': float(prop.longitude) if prop.longitude else None,
                            'nlat': float(prop.nlat) if prop.nlat else None,
                            'slat': float(prop.slat) if prop.slat else None,
                            'wlong': float(prop.wlong) if prop.wlong else None,
                            'elong': float(prop.elong) if prop.elong else None,
                            'addressv1': prop.addressv1,
                            'coordinates': prop.coordinates,
                            'geom': prop.geom.geojson if prop.geom else None,
                            'created_at': prop.created_at.strftime('%Y-%m-%d %H:%M:%S') if prop.created_at else None,
                            'updated_at': prop.updated_at.strftime('%Y-%m-%d %H:%M:%S') if prop.updated_at else None,
                        }
                        all_properties.append(prop_data)
                    
                    # Store partial data for progress display
                    partial_data = {
                        "type": "FeatureCollection",
                        "features": features,
                        "loading_progress": f"{min(offset+chunk_size, total)}/{total}"
                    }
                    cache.set('properties_geojson_partial', partial_data, timeout=None)
                    cache.set('properties_list_partial', all_properties, timeout=None)
                    
                    print(f"Progress: {min(offset+chunk_size, total)}/{total} properties loaded")
                
                # Final cache updates
                final_geojson = {
                    "type": "FeatureCollection",
                    "features": features
                }
                cache.set('properties_geojson_final', final_geojson, timeout=None)
                cache.set('properties_list_final', all_properties, timeout=None)
                
                # Remove loading flag and partial data
                cache.delete('properties_loading')
                cache.delete('properties_geojson_partial')
                cache.delete('properties_list_partial')
                
                print(f"Successfully loaded {len(features)} GeoJSON features and {len(all_properties)} properties")
                
            except Exception as e:
                print(f"Error loading properties in background: {e}")
                cache.delete('properties_loading')
        
        # Start background thread
        thread = threading.Thread(target=load_data_in_background, daemon=True)
        thread.start()