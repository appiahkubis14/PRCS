from django.apps import AppConfig


# class CoreConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'core'


from django.apps import AppConfig
import threading
import json
from django.core.cache import cache
import time

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        # Start background thread to load data
        def load_data_in_background():
            # Wait for database to be ready
            time.sleep(5)
            
            try:
                from core.models import Polygon
                
                fields = ['id', 'address', 'district', 'region', 'zone', 'property_type', 
                         'area', 'area_in_me', 'status', 'latitude', 'longitude', 
                         'g_code', 'postcode', 'street', 'gpsname']
                
                features = []
                total = Polygon.objects.count()
                
                print(f"Starting to load {total} properties in background...")
                
                # Process in chunks
                chunk_size = 5000
                for offset in range(0, total, chunk_size):
                    print(f"Loading properties {offset} to {offset+chunk_size}")
                    properties = Polygon.objects.all()[offset:offset + chunk_size]
                    
                    for prop in properties:
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
                    
                    # Update cache incrementally
                    partial_data = {
                        "type": "FeatureCollection",
                        "features": features,
                        "loading_progress": f"{min(offset+chunk_size, total)}/{total}"
                    }
                    cache.set('properties_geojson', partial_data, timeout=None)
                
                # Final cache update
                final_data = {
                    "type": "FeatureCollection",
                    "features": features
                }
                cache.set('properties_geojson', final_data, timeout=None)
                print(f"Successfully loaded all {len(features)} properties")
                
            except Exception as e:
                print(f"Error loading properties in background: {e}")
        
        # Start background thread
        thread = threading.Thread(target=load_data_in_background)
        thread.daemon = True
        thread.start()







from django.apps import AppConfig
import threading
import json
from django.core.cache import cache
import time

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        # Start background thread to load data
        def load_data_in_background():
            # Wait for database to be ready
            time.sleep(5)
            
            try:
                from core.models import Polygon
                
                fields = ['id', 'address', 'district', 'region', 'zone', 'property_type', 
                         'area', 'area_in_me', 'status', 'latitude', 'longitude', 
                         'g_code', 'postcode', 'street', 'gpsname']
                
                # ===== CACHE GEOJSON DATA =====
                features = []
                total = Polygon.objects.count()
                
                print(f"Starting to load {total} properties for GeoJSON...")
                
                # Process in chunks
                chunk_size = 5000
                for offset in range(0, total, chunk_size):
                    print(f"Loading GeoJSON properties {offset} to {offset+chunk_size}")
                    properties = Polygon.objects.all()[offset:offset + chunk_size]
                    
                    for prop in properties:
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
                    
                    # Update cache incrementally
                    partial_data = {
                        "type": "FeatureCollection",
                        "features": features,
                        "loading_progress": f"{min(offset+chunk_size, total)}/{total}"
                    }
                    cache.set('properties_geojson', partial_data, timeout=None)
                
                # Final cache update
                final_geojson = {
                    "type": "FeatureCollection",
                    "features": features
                }
                cache.set('properties_geojson', final_geojson, timeout=None)
                print(f"Successfully loaded all {len(features)} properties for GeoJSON")
                
                # ===== CACHE PROPERTIES LIST DATA =====
                print("Starting to cache properties list data...")
                
                # Cache all properties for the list view
                all_properties = []
                total = Polygon.objects.count()
                
                for offset in range(0, total, chunk_size):
                    print(f"Loading list properties {offset} to {offset+chunk_size}")
                    properties = Polygon.objects.all()[offset:offset + chunk_size]
                    
                    for prop in properties:
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
                    
                    # Cache partial data
                    cache.set('properties_list', all_properties, timeout=None)
                
                print(f"Successfully cached {len(all_properties)} properties for list view")
                
            except Exception as e:
                print(f"Error loading properties in background: {e}")
        
        # Start background thread
        thread = threading.Thread(target=load_data_in_background)
        thread.daemon = True
        thread.start()