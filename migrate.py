# portal/management/commands/migrate_core_property.py

import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.contrib.gis.geos import GEOSGeometry, Point
from core.models import Polygon
from django.db import IntegrityError
import traceback
import json

class Command(BaseCommand):
    help = 'Migrate data from core_property table to Polygon model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually saving to the database',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch (default: 1000)',
        )
        parser.add_argument(
            '--replace-existing',
            action='store_true',
            help='Replace existing polygons with new data (update instead of skip)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        replace_existing = options['replace_existing']
        
        self.stdout.write(self.style.SUCCESS('Starting core_property data migration...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        if replace_existing:
            self.stdout.write(self.style.WARNING('REPLACE MODE - Will update existing polygons'))
        
        # Migrate Polygons from core_property
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Migrating core_property to Polygons...')
        self.stdout.write('='*50)
        
        polygon_stats = self.migrate_polygons(dry_run, batch_size, replace_existing)
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('MIGRATION SUMMARY')
        self.stdout.write('='*50)
        self.stdout.write(f"Polygons: {polygon_stats['processed']} processed, "
                        f"{polygon_stats['created']} created, "
                        f"{polygon_stats['updated']} updated, "
                        f"{polygon_stats['skipped']} skipped, "
                        f"{polygon_stats['errors']} errors")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run completed - no changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))

    def migrate_polygons(self, dry_run, batch_size, replace_existing):
        """Migrate data from core_property table to Polygon model"""
        
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Note: core_property is in a different database (property_rate)
        # We need to use the database connection for property_rate
        from django.db import connections
        
        try:
            # Use the property_rate database connection
            with connections['property_rate'].cursor() as cursor:
                # Check if the table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'core_property'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    self.stdout.write(self.style.ERROR("Table 'core_property' does not exist in property_rate database!"))
                    return stats
                
                # Get count of records to migrate
                cursor.execute("SELECT COUNT(*) FROM core_property WHERE g_code IS NOT NULL;")
                total_records = cursor.fetchone()[0]
                self.stdout.write(f"Found {total_records} records to migrate")
                
                # Query all core_property records
                cursor.execute("""
                    SELECT 
                        g_code,
                        area_in_me,
                        district,
                        postcode,
                        nlat,
                        slat,
                        wlong,
                        elong,
                        gpsname,
                        region,
                        area,
                        addressv1,
                        street,
                        latitude,
                        longitude,
                        address,
                        coordinates
                    FROM core_property
                    WHERE g_code IS NOT NULL
                    ORDER BY g_code;
                """)
                
                polygons_to_create = []
                polygons_to_update = []
                
                for row in cursor.fetchall():
                    stats['processed'] += 1
                    
                    (g_code, area_in_me, district, postcode, nlat, slat, 
                     wlong, elong, gpsname, region, area, addressv1, 
                     street, latitude, longitude, address, coordinates) = row
                    
                    # Skip if g_code is missing (should not happen due to WHERE clause)
                    if not g_code:
                        self.stdout.write(self.style.WARNING(
                            f"Skipping record with no g_code (record #{stats['processed']})"
                        ))
                        stats['skipped'] += 1
                        continue
                    
                    # Convert numeric values safely
                    try:
                        area_in_me = float(area_in_me) if area_in_me is not None else 0.0
                        nlat = float(nlat) if nlat is not None else 0.0
                        slat = float(slat) if slat is not None else 0.0
                        wlong = float(wlong) if wlong is not None else 0.0
                        elong = float(elong) if elong is not None else 0.0
                        latitude = float(latitude) if latitude is not None else 0.0
                        longitude = float(longitude) if longitude is not None else 0.0
                    except (ValueError, TypeError) as e:
                        self.stdout.write(self.style.WARNING(
                            f"Warning: Could not convert numeric values for {g_code}: {e}"
                        ))
                        area_in_me = 0.0
                        nlat = 0.0
                        slat = 0.0
                        wlong = 0.0
                        elong = 0.0
                        latitude = 0.0
                        longitude = 0.0
                    
                    # Handle coordinates JSON
                    coordinates_data = []
                    if coordinates:
                        try:
                            if isinstance(coordinates, str):
                                coordinates_data = json.loads(coordinates)
                            elif isinstance(coordinates, (dict, list)):
                                coordinates_data = coordinates
                            else:
                                coordinates_data = []
                        except (json.JSONDecodeError, TypeError) as e:
                            self.stdout.write(self.style.WARNING(
                                f"Warning: Could not parse coordinates for {g_code}: {e}"
                            ))
                            coordinates_data = []
                    
                    # Create geometry point
                    geom = None
                    if latitude != 0 and longitude != 0:
                        try:
                            geom = Point(longitude, latitude, srid=4326)
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f"Warning: Could not create point geometry for {g_code}: {e}"
                            ))
                    
                    # Prepare polygon data
                    polygon_data = {
                        'g_code': g_code,
                        'area_in_me': area_in_me,
                        'district': district,
                        'postcode': postcode,
                        'nlat': nlat,
                        'slat': slat,
                        'wlong': wlong,
                        'elong': elong,
                        'gpsname': gpsname,
                        'region': region,
                        'area': area,
                        'addressv1': addressv1,
                        'street': street,
                        'latitude': latitude,
                        'longitude': longitude,
                        'address': address,
                        'coordinates': coordinates_data,
                        'geom': geom,
                        # Default values for required fields
                        'division': 0,
                        'block': 0,
                        'property': 0,
                        'status': 'unassessed',
                        'accessed': False,
                    }
                    
                    if not dry_run:
                        # Check if polygon already exists
                        existing_polygon = Polygon.objects.filter(g_code=g_code).first()
                        
                        if existing_polygon:
                            if replace_existing:
                                # Update existing polygon
                                for key, value in polygon_data.items():
                                    if key not in ['g_code']:  # Don't update the g_code
                                        setattr(existing_polygon, key, value)
                                polygons_to_update.append(existing_polygon)
                                if stats['processed'] % 100 == 0:
                                    self.stdout.write(f"Will update polygon: {g_code}")
                            else:
                                self.stdout.write(f"Polygon '{g_code}' already exists - skipping")
                                stats['skipped'] += 1
                        else:
                            # Create new polygon
                            polygons_to_create.append(Polygon(**polygon_data))
                            if stats['processed'] % 100 == 0:
                                self.stdout.write(f"Will create polygon: {g_code}")
                    else:
                        # Dry run mode
                        existing = Polygon.objects.filter(g_code=g_code).first()
                        if existing and not replace_existing:
                            self.stdout.write(f"[DRY RUN] Would skip existing polygon: {g_code}")
                            stats['skipped'] += 1
                        elif existing and replace_existing:
                            self.stdout.write(f"[DRY RUN] Would update polygon: {g_code}")
                            stats['updated'] += 1
                        else:
                            self.stdout.write(f"[DRY RUN] Would create polygon: {g_code}")
                            stats['created'] += 1
                    
                    # Process in batches
                    if not dry_run:
                        if len(polygons_to_create) >= batch_size:
                            self.create_polygon_batch(polygons_to_create, stats)
                            polygons_to_create = []
                        
                        if len(polygons_to_update) >= batch_size:
                            self.update_polygon_batch(polygons_to_update, stats)
                            polygons_to_update = []
                
                # Create/update remaining polygons
                if not dry_run:
                    if polygons_to_create:
                        self.create_polygon_batch(polygons_to_create, stats)
                    if polygons_to_update:
                        self.update_polygon_batch(polygons_to_update, stats)
                
                # Final verification
                if not dry_run:
                    with connections['default'].cursor() as target_cursor:
                        target_cursor.execute("SELECT COUNT(*) FROM polygons WHERE g_code IS NOT NULL;")
                        final_count = target_cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(
                            f"\nFinal count in polygons table: {final_count}"
                        ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error migrating polygons: {e}"))
            traceback.print_exc()
            stats['errors'] += 1
        
        return stats

    def create_polygon_batch(self, polygons_to_create, stats):
        """Create a batch of polygons"""
        try:
            with transaction.atomic():
                created = Polygon.objects.bulk_create(
                    polygons_to_create,
                    ignore_conflicts=False,
                    batch_size=len(polygons_to_create)
                )
                stats['created'] += len(created)
                self.stdout.write(f"Created {len(created)} polygons")
        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(f"Integrity error creating polygons: {e}"))
            # Try creating one by one to identify problematic records
            for polygon in polygons_to_create:
                try:
                    polygon.save()
                    stats['created'] += 1
                except Exception as ex:
                    self.stdout.write(self.style.ERROR(
                        f"Could not create polygon {polygon.g_code}: {ex}"
                    ))
                    stats['errors'] += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating polygons batch: {e}"))
            # Try creating one by one
            for polygon in polygons_to_create:
                try:
                    polygon.save()
                    stats['created'] += 1
                except Exception as ex:
                    self.stdout.write(self.style.ERROR(
                        f"Could not create polygon {polygon.g_code}: {ex}"
                    ))
                    stats['errors'] += 1

    def update_polygon_batch(self, polygons_to_update, stats):
        """Update a batch of polygons"""
        updated_count = 0
        for polygon in polygons_to_update:
            try:
                polygon.save()
                updated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Could not update polygon {polygon.g_code}: {e}"
                ))
                stats['errors'] += 1
        stats['updated'] += updated_count
        if updated_count > 0:
            self.stdout.write(f"Updated {updated_count} polygons")