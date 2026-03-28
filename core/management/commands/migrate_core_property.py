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
from collections import defaultdict

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
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing polygons before migration (use with caution!)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        replace_existing = options['replace_existing']
        clear_existing = options['clear_existing']
        
        self.stdout.write(self.style.SUCCESS('Starting core_property data migration...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        if replace_existing:
            self.stdout.write(self.style.WARNING('REPLACE MODE - Will update existing polygons'))
        
        if clear_existing:
            self.stdout.write(self.style.ERROR('WARNING: CLEAR MODE - Will delete all existing polygons!'))
            if not dry_run:
                confirm = input('Type "yes" to confirm deletion of all polygons: ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.ERROR('Operation cancelled'))
                    return
        
        # Clear existing polygons if requested
        if clear_existing and not dry_run:
            self.stdout.write('Deleting existing polygons...')
            count = Polygon.objects.all().count()
            Polygon.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} existing polygons'))
        
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
                        f"{polygon_stats['duplicates']} duplicates, "
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
            'duplicates': 0,
            'errors': 0
        }
        
        from django.db import connections
        
        try:
            # First, check what columns are available in core_property table
            with connections['property_rate'].cursor() as check_cursor:
                check_cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'core_property'
                    ORDER BY ordinal_position;
                """)
                available_columns = [row[0] for row in check_cursor.fetchall()]
                self.stdout.write(f"Available columns in core_property: {', '.join(available_columns[:10])}...")
                
                # Check if geom column exists
                has_geom = 'geom' in available_columns
                if has_geom:
                    self.stdout.write(self.style.SUCCESS("✓ Found 'geom' column in core_property table"))
                else:
                    self.stdout.write(self.style.WARNING("⚠ 'geom' column not found, will use latitude/longitude to create geometry"))
            
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
                
                # First, identify duplicates in source data
                self.stdout.write("\nChecking for duplicate g_code values in source...")
                cursor.execute("""
                    SELECT g_code, COUNT(*) 
                    FROM core_property 
                    WHERE g_code IS NOT NULL 
                    GROUP BY g_code 
                    HAVING COUNT(*) > 1;
                """)
                duplicates = cursor.fetchall()
                if duplicates:
                    self.stdout.write(self.style.WARNING(f"Found {len(duplicates)} duplicate g_code values in source"))
                    for dup in duplicates[:10]:  # Show first 10 duplicates
                        self.stdout.write(f"  {dup[0]}: appears {dup[1]} times")
                    if len(duplicates) > 10:
                        self.stdout.write(f"  ... and {len(duplicates) - 10} more")
                else:
                    self.stdout.write(self.style.SUCCESS("No duplicate g_code values found in source"))
                
                # Get count of unique records to migrate
                cursor.execute("""
                    SELECT COUNT(DISTINCT g_code) 
                    FROM core_property 
                    WHERE g_code IS NOT NULL;
                """)
                total_unique_records = cursor.fetchone()[0]
                self.stdout.write(f"\nFound {total_unique_records} unique g_code records to migrate")
                
                # Query with deduplication - take the latest record for each g_code
                # Using DISTINCT ON to get one record per g_code
                if has_geom:
                    query = """
                        SELECT DISTINCT ON (g_code)
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
                            coordinates,
                            geom
                        FROM core_property
                        WHERE g_code IS NOT NULL
                        ORDER BY g_code, ctid DESC;
                    """
                else:
                    query = """
                        SELECT DISTINCT ON (g_code)
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
                            coordinates,
                            NULL as geom
                        FROM core_property
                        WHERE g_code IS NOT NULL
                        ORDER BY g_code, ctid DESC;
                    """
                
                cursor.execute(query)
                
                # First, get all existing g_codes in polygons to avoid duplicate checks per record
                existing_g_codes = set()
                if not dry_run and not replace_existing:
                    existing_g_codes = set(Polygon.objects.values_list('g_code', flat=True))
                    self.stdout.write(f"Found {len(existing_g_codes)} existing polygons in database")
                
                polygons_to_create = []
                polygons_to_update = []
                processed_g_codes = set()
                
                for row in cursor.fetchall():
                    stats['processed'] += 1
                    
                    if has_geom:
                        (g_code, area_in_me, district, postcode, nlat, slat, 
                         wlong, elong, gpsname, region, area, addressv1, 
                         street, latitude, longitude, address, coordinates, geom_wkt) = row
                    else:
                        (g_code, area_in_me, district, postcode, nlat, slat, 
                         wlong, elong, gpsname, region, area, addressv1, 
                         street, latitude, longitude, address, coordinates, geom_wkt) = row
                    
                    # Skip if g_code is missing or already processed (shouldn't happen due to DISTINCT)
                    if not g_code:
                        stats['skipped'] += 1
                        continue
                    
                    if g_code in processed_g_codes:
                        stats['duplicates'] += 1
                        continue
                    processed_g_codes.add(g_code)
                    
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
                    
                    # Handle geometry - use geom from source if available
                    geom = None
                    if geom_wkt:
                        try:
                            if isinstance(geom_wkt, str):
                                geom = GEOSGeometry(geom_wkt, srid=4326)
                            else:
                                geom = geom_wkt
                            # Only log occasionally to avoid flooding
                            if stats['processed'] % 1000 == 0:
                                self.stdout.write(f"Using existing geometry for {g_code}")
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f"Warning: Could not parse existing geometry for {g_code}: {e}"
                            ))
                            # Fall back to creating from lat/long
                            if latitude != 0 and longitude != 0:
                                try:
                                    geom = Point(longitude, latitude, srid=4326)
                                except Exception as point_e:
                                    pass
                    else:
                        # No geometry in source, create from lat/long if available
                        if latitude != 0 and longitude != 0:
                            try:
                                geom = Point(longitude, latitude, srid=4326)
                            except Exception as e:
                                pass
                    
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
                        'division': 0,
                        'block': 0,
                        'property': 0,
                        'status': 'unassessed',
                        'accessed': False,
                    }
                    
                    if not dry_run:
                        # Check if polygon already exists
                        if g_code in existing_g_codes or (not replace_existing and Polygon.objects.filter(g_code=g_code).exists()):
                            if replace_existing:
                                # Update existing polygon
                                try:
                                    existing_polygon = Polygon.objects.get(g_code=g_code)
                                    for key, value in polygon_data.items():
                                        if key not in ['g_code']:
                                            setattr(existing_polygon, key, value)
                                    polygons_to_update.append(existing_polygon)
                                except Polygon.DoesNotExist:
                                    polygons_to_create.append(Polygon(**polygon_data))
                            else:
                                stats['skipped'] += 1
                                if stats['processed'] % 1000 == 0:
                                    self.stdout.write(f"Skipping existing polygon: {g_code}")
                        else:
                            # Create new polygon
                            polygons_to_create.append(Polygon(**polygon_data))
                            if stats['processed'] % 1000 == 0:
                                self.stdout.write(f"Will create polygon: {g_code}")
                    else:
                        # Dry run mode
                        if g_code in existing_g_codes:
                            if replace_existing:
                                self.stdout.write(f"[DRY RUN] Would update polygon: {g_code}")
                                stats['updated'] += 1
                            else:
                                self.stdout.write(f"[DRY RUN] Would skip existing polygon: {g_code}")
                                stats['skipped'] += 1
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
                    
                    # Progress indicator
                    if stats['processed'] % 5000 == 0:
                        self.stdout.write(f"Progress: {stats['processed']}/{total_unique_records} records processed")
                
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
                        
                        target_cursor.execute("SELECT COUNT(*) FROM polygons WHERE geom IS NOT NULL;")
                        geom_count = target_cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(
                            f"Records with geometry: {geom_count}"
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
                # Use ignore_conflicts=True to skip duplicates
                created = Polygon.objects.bulk_create(
                    polygons_to_create,
                    ignore_conflicts=True,
                    batch_size=len(polygons_to_create)
                )
                stats['created'] += len(created)
                if len(created) > 0:
                    self.stdout.write(f"Created {len(created)} polygons")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating polygons batch: {e}"))
            # Try creating one by one
            for polygon in polygons_to_create:
                try:
                    polygon.save()
                    stats['created'] += 1
                except IntegrityError:
                    stats['duplicates'] += 1
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