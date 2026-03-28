# portal/management/commands/migrate_lanma_businesses.py

import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.contrib.gis.geos import GEOSGeometry, Point
from core.models import Business, BusinessType, BusinessSubType, BusinessCategory
from django.db import IntegrityError
import traceback
import json
from collections import defaultdict

class Command(BaseCommand):
    help = 'Migrate data from lanma_businesses table to Business model'

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
            help='Replace existing businesses with new data (update instead of skip)',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing businesses before migration (use with caution!)',
        )
        parser.add_argument(
            '--map-categories',
            action='store_true',
            help='Try to map business categories to existing BusinessType/BusinessCategory models',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        replace_existing = options['replace_existing']
        clear_existing = options['clear_existing']
        map_categories = options['map_categories']
        
        self.stdout.write(self.style.SUCCESS('Starting lanma_businesses data migration...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        if replace_existing:
            self.stdout.write(self.style.WARNING('REPLACE MODE - Will update existing businesses'))
        
        if clear_existing:
            self.stdout.write(self.style.ERROR('WARNING: CLEAR MODE - Will delete all existing businesses!'))
            if not dry_run:
                confirm = input('Type "yes" to confirm deletion of all businesses: ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.ERROR('Operation cancelled'))
                    return
        
        # Clear existing businesses if requested
        if clear_existing and not dry_run:
            self.stdout.write('Deleting existing businesses...')
            count = Business.objects.all().count()
            Business.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} existing businesses'))
        
        # First, get the actual column names from the table
        column_mapping = self.get_column_mapping()
        
        # Map categories if requested
        category_mapping = {}
        if map_categories and not dry_run:
            self.stdout.write('\n' + '='*50)
            self.stdout.write('Building category mappings...')
            self.stdout.write('='*50)
            category_mapping = self.build_category_mapping(column_mapping)
        
        # Migrate Businesses from lanma_businesses
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Migrating lanma_businesses to Businesses...')
        self.stdout.write('='*50)
        
        business_stats = self.migrate_businesses(dry_run, batch_size, replace_existing, category_mapping, column_mapping)
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('MIGRATION SUMMARY')
        self.stdout.write('='*50)
        self.stdout.write(f"Businesses: {business_stats['processed']} processed, "
                        f"{business_stats['created']} created, "
                        f"{business_stats['updated']} updated, "
                        f"{business_stats['skipped']} skipped, "
                        f"{business_stats['duplicates']} duplicates, "
                        f"{business_stats['errors']} errors")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run completed - no changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))

    def get_column_mapping(self):
        """Get the actual column names from lanma_businesses table"""
        from django.db import connections
        
        column_mapping = {}
        
        try:
            with connections['property_rate'].cursor() as cursor:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'lanma_businesses'
                    ORDER BY ordinal_position;
                """)
                
                columns = [row[0] for row in cursor.fetchall()]
                
                # Create mapping from lowercase to actual column name
                for col in columns:
                    column_mapping[col.lower()] = col
                
                self.stdout.write(f"Found {len(columns)} columns in lanma_businesses table")
                self.stdout.write(f"Sample columns: {', '.join(columns[:10])}")
                
                # Check for specific columns
                expected_columns = ['account_number', 'business_name', 'business_category', 
                                   'business_class', 'owner_name', 'phone_number']
                
                for col in expected_columns:
                    if col in column_mapping:
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Found '{col}' -> '{column_mapping[col]}'"))
                    else:
                        self.stdout.write(self.style.WARNING(f"  ✗ Could not find '{col}' column"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting column mapping: {e}"))
        
        return column_mapping

    def build_category_mapping(self, column_mapping):
        """Build mapping from source categories to BusinessType and BusinessCategory"""
        from django.db import connections
        
        category_mapping = {
            'business_type': {},
            'business_category': {}
        }
        
        # Get the actual column names
        business_class_col = column_mapping.get('business_class', 'business_class')
        business_category_col = column_mapping.get('business_category', 'business_category')
        
        try:
            # Get unique business types from source
            with connections['property_rate'].cursor() as cursor:
                cursor.execute(f"""
                    SELECT DISTINCT "{business_class_col}", "{business_category_col}" 
                    FROM lanma_businesses 
                    WHERE "{business_class_col}" IS NOT NULL OR "{business_category_col}" IS NOT NULL;
                """)
                
                for row in cursor.fetchall():
                    business_class = row[0]
                    business_category = row[1]
                    
                    # Map business_class to BusinessType
                    if business_class:
                        business_type = BusinessType.objects.filter(
                            name__iexact=business_class.strip()
                        ).first()
                        
                        if business_type:
                            category_mapping['business_type'][business_class] = business_type.id
                        else:
                            self.stdout.write(self.style.WARNING(
                                f"Could not map business_class: {business_class}"
                            ))
                    
                    # Map business_category to BusinessCategory
                    if business_category:
                        business_cat = BusinessCategory.objects.filter(
                            name__iexact=business_category.strip()
                        ).first()
                        
                        if business_cat:
                            category_mapping['business_category'][business_category] = business_cat.id
                        else:
                            self.stdout.write(self.style.WARNING(
                                f"Could not map business_category: {business_category}"
                            ))
            
            self.stdout.write(self.style.SUCCESS(
                f"Mapped {len(category_mapping['business_type'])} business types and "
                f"{len(category_mapping['business_category'])} business categories"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error building category mapping: {e}"))
        
        return category_mapping

    def migrate_businesses(self, dry_run, batch_size, replace_existing, category_mapping, column_mapping):
        """Migrate data from lanma_businesses table to Business model"""
        
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        from django.db import connections
        
        # Get actual column names
        account_number_col = column_mapping.get('account_number', 'Account_Number')
        business_name_col = column_mapping.get('business_name', 'Business_Name')
        business_category_col = column_mapping.get('business_category', 'Business_Category')
        business_class_col = column_mapping.get('business_class', 'Business_Class')
        owner_name_col = column_mapping.get('owner_name', 'Owner_Name')
        email_col = column_mapping.get('email', 'Email')
        phone_number_col = column_mapping.get('phone_number', 'Phone_Number')
        house_number_col = column_mapping.get('house_number', 'House_Number')
        digital_address_col = column_mapping.get('digital_address', 'Digital_Address')
        location_col = column_mapping.get('location', 'Location')
        street_name_col = column_mapping.get('street_name', 'Street_Name')
        address_col = column_mapping.get('address', 'Address')
        structure_id_col = column_mapping.get('structure_id', 'Structure_ID')
        centroid_col = column_mapping.get('centroid', 'Centroid')
        block_col = column_mapping.get('block', 'Block')
        division_col = column_mapping.get('division', 'Division')
        lng_col = column_mapping.get('lng', 'Longitude')
        lat_col = column_mapping.get('lat', 'Latitude')
        geom_col = column_mapping.get('geom', column_mapping.get('geometry', 'Geom'))
        
        try:
            # Use the property_rate database connection
            with connections['property_rate'].cursor() as cursor:
                # Check if the table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'lanma_businesses'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    self.stdout.write(self.style.ERROR("Table 'lanma_businesses' does not exist in property_rate database!"))
                    return stats
                
                # First, identify duplicates in source data based on account_number
                self.stdout.write("\nChecking for duplicate account_number values in source...")
                cursor.execute(f"""
                    SELECT "{account_number_col}", COUNT(*) 
                    FROM lanma_businesses 
                    WHERE "{account_number_col}" IS NOT NULL 
                    GROUP BY "{account_number_col}" 
                    HAVING COUNT(*) > 1;
                """)
                duplicates = cursor.fetchall()
                if duplicates:
                    self.stdout.write(self.style.WARNING(f"Found {len(duplicates)} duplicate account_number values in source"))
                    for dup in duplicates[:10]:
                        self.stdout.write(f"  {dup[0]}: appears {dup[1]} times")
                    if len(duplicates) > 10:
                        self.stdout.write(f"  ... and {len(duplicates) - 10} more")
                else:
                    self.stdout.write(self.style.SUCCESS("No duplicate account_number values found in source"))
                
                # Get count of unique records to migrate
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT "{account_number_col}") 
                    FROM lanma_businesses 
                    WHERE "{account_number_col}" IS NOT NULL;
                """)
                total_unique_records = cursor.fetchone()[0]
                self.stdout.write(f"\nFound {total_unique_records} unique account_number records to migrate")
                
                # Query with deduplication - take the latest record for each account_number
                query = f"""
                    SELECT DISTINCT ON ("{account_number_col}")
                        "{account_number_col}",
                        "{business_name_col}",
                        "{business_category_col}",
                        "{business_class_col}",
                        "{owner_name_col}",
                        "{email_col}",
                        "{phone_number_col}",
                        "{house_number_col}",
                        "{digital_address_col}",
                        "{location_col}",
                        "{street_name_col}",
                        "{address_col}",
                        "{structure_id_col}",
                        "{centroid_col}",
                        "{block_col}",
                        "{division_col}",
                        "{lng_col}",
                        "{lat_col}",
                        "{geom_col}"
                    FROM lanma_businesses
                    WHERE "{account_number_col}" IS NOT NULL
                    ORDER BY "{account_number_col}", ctid DESC;
                """
                
                cursor.execute(query)
                
                # First, get all existing account_numbers in businesses
                existing_accounts = set()
                if not dry_run and not replace_existing:
                    existing_accounts = set(Business.objects.values_list('account_number', flat=True))
                    self.stdout.write(f"Found {len(existing_accounts)} existing businesses in database")
                
                businesses_to_create = []
                businesses_to_update = []
                processed_accounts = set()
                
                for row in cursor.fetchall():
                    stats['processed'] += 1
                    
                    (account_number, business_name, business_category, business_class, 
                     owner_name, email, phone_number, house_number, digital_address,
                     location, street_name, address, structure_id, centroid, block,
                     division, lng, lat, geom_wkt) = row
                    
                    # Skip if account_number is missing
                    if not account_number:
                        stats['skipped'] += 1
                        continue
                    
                    if account_number in processed_accounts:
                        stats['duplicates'] += 1
                        continue
                    processed_accounts.add(account_number)
                    
                    # Convert numeric values safely
                    try:
                        lng = float(lng) if lng is not None else None
                        lat = float(lat) if lat is not None else None
                    except (ValueError, TypeError) as e:
                        self.stdout.write(self.style.WARNING(
                            f"Warning: Could not convert coordinates for {account_number}: {e}"
                        ))
                        lng = None
                        lat = None
                    
                    # Handle geometry - use geom from source if available
                    geom = None
                    if geom_wkt:
                        try:
                            if isinstance(geom_wkt, str):
                                geom = GEOSGeometry(geom_wkt, srid=4326)
                            else:
                                geom = geom_wkt
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f"Warning: Could not parse existing geometry for {account_number}: {e}"
                            ))
                    
                    # If no geom from source, create from lat/lng
                    if not geom and lat and lng:
                        try:
                            geom = Point(lng, lat, srid=4326)
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(
                                f"Could not create point geometry for {account_number}: {e}"
                            ))
                    
                    # Map business types and categories if mapping is enabled
                    business_type_id = None
                    business_category_id = None
                    
                    if category_mapping:
                        if business_class and business_class in category_mapping.get('business_type', {}):
                            business_type_id = category_mapping['business_type'][business_class]
                        
                        if business_category and business_category in category_mapping.get('business_category', {}):
                            business_category_id = category_mapping['business_category'][business_category]
                    
                    # Prepare business data
                    business_data = {
                        'account_number': account_number,
                        'business_name': business_name,
                        'business_category': business_category,
                        'business_class': business_class,
                        'owner_name': owner_name,
                        'email': email,
                        'phone_number': phone_number,
                        'house_number': house_number,
                        'digital_address': digital_address,
                        'location': location,
                        'street_name': street_name,
                        'address': address,
                        'structure_id': structure_id,
                        'centroid': centroid,
                        'block': block,
                        'division': division,
                        'lng': lng,
                        'lat': lat,
                        'geometry': geom,
                        'source_sheet': 'lanma_businesses',
                        'imported_from_bops': False,
                    }
                    
                    # Add mapped IDs if available
                    if business_type_id:
                        business_data['business_type_id'] = business_type_id
                    if business_category_id:
                        business_data['business_category_value_id'] = business_category_id
                    
                    if not dry_run:
                        # Check if business already exists
                        if account_number in existing_accounts:
                            if replace_existing:
                                # Update existing business
                                try:
                                    existing_business = Business.objects.get(account_number=account_number)
                                    for key, value in business_data.items():
                                        setattr(existing_business, key, value)
                                    businesses_to_update.append(existing_business)
                                except Business.DoesNotExist:
                                    businesses_to_create.append(Business(**business_data))
                            else:
                                stats['skipped'] += 1
                                if stats['processed'] % 1000 == 0:
                                    self.stdout.write(f"Skipping existing business: {account_number}")
                        else:
                            # Create new business
                            businesses_to_create.append(Business(**business_data))
                            if stats['processed'] % 1000 == 0:
                                self.stdout.write(f"Will create business: {account_number}")
                    else:
                        # Dry run mode
                        if account_number in existing_accounts:
                            if replace_existing:
                                self.stdout.write(f"[DRY RUN] Would update business: {account_number}")
                                stats['updated'] += 1
                            else:
                                self.stdout.write(f"[DRY RUN] Would skip existing business: {account_number}")
                                stats['skipped'] += 1
                        else:
                            self.stdout.write(f"[DRY RUN] Would create business: {account_number}")
                            stats['created'] += 1
                    
                    # Process in batches
                    if not dry_run:
                        if len(businesses_to_create) >= batch_size:
                            self.create_business_batch(businesses_to_create, stats)
                            businesses_to_create = []
                        
                        if len(businesses_to_update) >= batch_size:
                            self.update_business_batch(businesses_to_update, stats)
                            businesses_to_update = []
                    
                    # Progress indicator
                    if stats['processed'] % 5000 == 0:
                        self.stdout.write(f"Progress: {stats['processed']}/{total_unique_records} records processed")
                
                # Create/update remaining businesses
                if not dry_run:
                    if businesses_to_create:
                        self.create_business_batch(businesses_to_create, stats)
                    if businesses_to_update:
                        self.update_business_batch(businesses_to_update, stats)
                
                # Final verification
                if not dry_run:
                    with connections['default'].cursor() as target_cursor:
                        target_cursor.execute("SELECT COUNT(*) FROM businesses WHERE account_number IS NOT NULL;")
                        final_count = target_cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(
                            f"\nFinal count in businesses table: {final_count}"
                        ))
                        
                        target_cursor.execute("SELECT COUNT(*) FROM businesses WHERE geometry IS NOT NULL;")
                        geom_count = target_cursor.fetchone()[0]
                        self.stdout.write(self.style.SUCCESS(
                            f"Records with geometry: {geom_count}"
                        ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error migrating businesses: {e}"))
            traceback.print_exc()
            stats['errors'] += 1
        
        return stats

    def create_business_batch(self, businesses_to_create, stats):
        """Create a batch of businesses"""
        try:
            with transaction.atomic():
                # Use ignore_conflicts=True to skip duplicates
                created = Business.objects.bulk_create(
                    businesses_to_create,
                    ignore_conflicts=True,
                    batch_size=len(businesses_to_create)
                )
                stats['created'] += len(created)
                if len(created) > 0:
                    self.stdout.write(f"Created {len(created)} businesses")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating businesses batch: {e}"))
            # Try creating one by one
            for business in businesses_to_create:
                try:
                    business.save()
                    stats['created'] += 1
                except IntegrityError:
                    stats['duplicates'] += 1
                except Exception as ex:
                    self.stdout.write(self.style.ERROR(
                        f"Could not create business {business.account_number}: {ex}"
                    ))
                    stats['errors'] += 1

    def update_business_batch(self, businesses_to_update, stats):
        """Update a batch of businesses"""
        updated_count = 0
        for business in businesses_to_update:
            try:
                business.save()
                updated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Could not update business {business.account_number}: {e}"
                ))
                stats['errors'] += 1
        stats['updated'] += updated_count
        if updated_count > 0:
            self.stdout.write(f"Updated {updated_count} businesses")