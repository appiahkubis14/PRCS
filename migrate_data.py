# migrate_data.py - Fixed version with proper transaction handling

import os
import sys
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import uuid
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database configurations - UPDATE THESE!
SOURCE_DB = {
    'dbname': 'gema_db',
    'user': 'postgres',  # Change to your username
    'password': 'sak@2001server',  # Change to your password
    'host': 'localhost',
    'port': 5432
}

TARGET_DB = {
    'dbname': 'gema_new_db',
    'user': 'postgres',  # Change to your username
    'password': 'sak@2001server',  # Change to your password
    'host': 'localhost',
    'port': 5432
}

# Tables in order of dependency
TABLES_IN_ORDER = [
    'users',
    'lookup_groups',
    'lookup_values',
    'business_types',
    'business_sub_types',
    'business_categories',
    'businesses',
    'polygons',
    'block_boundaries',
    'assignments',
    'sessions',
    'pr_entries',
    'bop_entries',
    'bills',
    'payments',
    'collector_notifications',
    'notifications',
    'otp_codes',
    'refresh_tokens',
    'system_settings',
    'audit_log',
    'bank_statements',
    'fee_schedule',
    'property_rates',
    'version_tbl'
]


class SafeDataMigrator:
    def __init__(self):
        self.source_conn = None
        self.target_conn = None
        self.source_cursor = None
        self.target_cursor = None
        
    def connect(self):
        """Connect to both databases with autocommit off"""
        try:
            self.source_conn = psycopg2.connect(**SOURCE_DB)
            self.source_conn.autocommit = False
            self.source_cursor = self.source_conn.cursor(cursor_factory=RealDictCursor)
            logger.info("✓ Connected to source database")
            
            self.target_conn = psycopg2.connect(**TARGET_DB)
            self.target_conn.autocommit = False
            self.target_cursor = self.target_conn.cursor()
            logger.info("✓ Connected to target database")
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Close database connections"""
        try:
            if self.target_conn:
                self.target_conn.commit()
        except:
            pass
        
        if self.source_cursor:
            self.source_cursor.close()
        if self.target_cursor:
            self.target_cursor.close()
        if self.source_conn:
            self.source_conn.close()
        if self.target_conn:
            self.target_conn.close()
        logger.info("Disconnected from databases")
    
    def get_table_row_count(self, table_name):
        """Get number of rows in table"""
        try:
            query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name))
            self.source_cursor.execute(query)
            return self.source_cursor.fetchone()['count']
        except Exception as e:
            logger.error(f"Error getting row count for {table_name}: {e}")
            return 0
    
    def get_table_columns(self, table_name):
        """Get column names for a table"""
        try:
            query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """
            self.source_cursor.execute(query, (table_name,))
            return [row['column_name'] for row in self.source_cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return []
    
    def truncate_table(self, table_name):
        """Truncate table before migration with proper error handling"""
        try:
            self.target_cursor.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.Identifier(table_name)))
            self.target_conn.commit()
            logger.info(f"✓ Truncated table: {table_name}")
            return True
        except Exception as e:
            logger.warning(f"Could not truncate {table_name}: {e}")
            self.target_conn.rollback()
            return False
    
    def migrate_table(self, table_name):
        """Migrate data with proper transaction handling per batch"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating table: {table_name}")
        
        # Get row count
        row_count = self.get_table_row_count(table_name)
        if row_count == 0:
            logger.info(f"✓ No data in {table_name}, skipping")
            return True
        
        logger.info(f"Found {row_count} rows to migrate")
        
        # Get columns
        columns = self.get_table_columns(table_name)
        if not columns:
            logger.warning(f"No columns found for {table_name}, skipping")
            return True
        
        # Prepare select query
        select_query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))
        
        # Prepare insert query
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() * len(columns))
        )
        
        # Migrate in batches with separate transactions
        batch_size = 500
        offset = 0
        inserted = 0
        failed = 0
        
        while True:
            try:
                # Fetch batch
                self.source_cursor.execute(select_query)
                rows = self.source_cursor.fetchmany(batch_size)
                
                if not rows:
                    break
                
                # Process each row with its own transaction
                for row in rows:
                    try:
                        values = [row[col] for col in columns]
                        self.target_cursor.execute(insert_query, values)
                        inserted += 1
                        
                        # Commit every 100 rows
                        if inserted % 100 == 0:
                            self.target_conn.commit()
                            logger.info(f"  Progress: {inserted}/{row_count} rows inserted")
                            
                    except Exception as row_error:
                        failed += 1
                        logger.error(f"  ✗ Failed to insert row: {row_error}")
                        logger.error(f"    Row data: {dict(row)}")
                        self.target_conn.rollback()
                        continue
                
                # Commit remaining rows in this batch
                self.target_conn.commit()
                offset += len(rows)
                logger.info(f"Batch complete: {inserted}/{row_count} rows inserted, {failed} failed")
                
            except Exception as batch_error:
                logger.error(f"Error processing batch: {batch_error}")
                self.target_conn.rollback()
                continue
        
        logger.info(f"✓ Completed migration of {table_name}: {inserted} inserted, {failed} failed")
        return failed == 0
    
    def verify_migration(self):
        """Verify that data was migrated correctly"""
        logger.info("\n" + "="*60)
        logger.info("VERIFYING MIGRATION")
        logger.info("="*60)
        
        verification_results = []
        
        for table_name in TABLES_IN_ORDER:
            try:
                # Get counts from source
                query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name))
                self.source_cursor.execute(query)
                source_count = self.source_cursor.fetchone()['count']
                
                # Get counts from target
                self.target_cursor.execute(query)
                target_count = self.target_cursor.fetchone()[0]
                
                status = "✓" if source_count == target_count else "⚠"
                verification_results.append({
                    'table': table_name,
                    'source': source_count,
                    'target': target_count,
                    'status': status
                })
                
                if source_count == target_count:
                    logger.info(f"{status} {table_name}: {source_count:,} rows")
                else:
                    logger.warning(f"{status} {table_name}: Source={source_count:,}, Target={target_count:,}")
                    
            except Exception as e:
                logger.error(f"Error verifying {table_name}: {e}")
                verification_results.append({
                    'table': table_name,
                    'source': 'ERROR',
                    'target': 'ERROR',
                    'status': '✗'
                })
        
        return verification_results
    
    def migrate_all_tables(self):
        """Migrate all tables in order"""
        successful = []
        failed = []
        
        for table_name in TABLES_IN_ORDER:
            try:
                # Start a fresh transaction for each table
                self.target_conn.rollback()  # Clear any pending transaction
                
                # Truncate table
                self.truncate_table(table_name)
                
                # Migrate data
                success = self.migrate_table(table_name)
                
                if success:
                    successful.append(table_name)
                else:
                    failed.append(table_name)
                    
            except Exception as e:
                logger.error(f"Failed to migrate {table_name}: {e}")
                logger.error(traceback.format_exc())
                self.target_conn.rollback()
                failed.append(table_name)
        
        return successful, failed
    
    def create_summary_report(self, successful, failed, verification):
        """Create migration summary report"""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION SUMMARY REPORT")
        logger.info("="*60)
        
        if successful:
            logger.info(f"\n✓ SUCCESSFUL TABLES ({len(successful)}):")
            for table in successful:
                logger.info(f"  ✓ {table}")
        
        if failed:
            logger.info(f"\n✗ FAILED TABLES ({len(failed)}):")
            for table in failed:
                logger.info(f"  ✗ {table}")
        
        logger.info("\nVERIFICATION RESULTS:")
        total_source = 0
        total_target = 0
        
        for result in verification:
            if isinstance(result['source'], int):
                total_source += result['source']
                total_target += result['target']
            logger.info(f"  {result['status']} {result['table']}: {result['source']} → {result['target']}")
        
        logger.info(f"\nTOTAL ROWS MIGRATED:")
        logger.info(f"  Source total: {total_source:,}")
        logger.info(f"  Target total: {total_target:,}")
        logger.info(f"  Difference: {total_source - total_target:,}")
        
        if total_source == total_target and len(failed) == 0:
            logger.info("\n✓✓✓ MIGRATION COMPLETED SUCCESSFULLY! ✓✓✓")
        else:
            logger.warning("\n⚠⚠⚠ MIGRATION COMPLETED WITH ISSUES! ⚠⚠⚠")
    
    def run(self):
        """Run the complete migration process"""
        start_time = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting migration at {start_time}")
        logger.info(f"Source: {SOURCE_DB['dbname']}")
        logger.info(f"Target: {TARGET_DB['dbname']}")
        logger.info(f"{'='*60}\n")
        
        if not self.connect():
            return False
        
        try:
            # Migrate all tables
            successful, failed = self.migrate_all_tables()
            
            # Verify migration
            verification = self.verify_migration()
            
            # Create summary report
            self.create_summary_report(successful, failed, verification)
            
            end_time = datetime.now()
            duration = end_time - start_time
            logger.info(f"\nMigration completed at {end_time}")
            logger.info(f"Total duration: {duration}")
            
            return len(failed) == 0
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            logger.error(traceback.format_exc())
            self.target_conn.rollback()
            return False
        finally:
            self.disconnect()


# ============================================================
# Quick Fix: Direct PostgreSQL Dump/Restore
# ============================================================

def direct_pg_dump_restore():
    """Alternative: Use pg_dump and pg_restore directly"""
    import subprocess
    
    logger.info("Using pg_dump/pg_restore for migration...")
    
    # Dump from source
    dump_cmd = [
        'pg_dump',
        '-h', SOURCE_DB['host'],
        '-p', str(SOURCE_DB['port']),
        '-U', SOURCE_DB['user'],
        '-d', SOURCE_DB['dbname'],
        '--no-owner',
        '--no-privileges',
        '-f', 'temp_dump.sql'
    ]
    
    # Restore to target
    restore_cmd = [
        'psql',
        '-h', TARGET_DB['host'],
        '-p', str(TARGET_DB['port']),
        '-U', TARGET_DB['user'],
        '-d', TARGET_DB['dbname'],
        '-f', 'temp_dump.sql'
    ]
    
    try:
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = SOURCE_DB['password']
        
        # Dump
        logger.info("Dumping source database...")
        result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Dump failed: {result.stderr}")
            return False
        
        logger.info("Dump completed successfully")
        
        # Restore
        env['PGPASSWORD'] = TARGET_DB['password']
        logger.info("Restoring to target database...")
        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Restore failed: {result.stderr}")
            return False
        
        logger.info("Restore completed successfully")
        
        # Clean up
        os.remove('temp_dump.sql')
        
        return True
        
    except Exception as e:
        logger.error(f"Direct migration failed: {e}")
        return False


def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("DATABASE MIGRATION TOOL")
    print("="*60)
    print(f"Source: {SOURCE_DB['dbname']}")
    print(f"Target: {TARGET_DB['dbname']}")
    print("="*60)
    
    print("\nChoose migration method:")
    print("1. Python script migration (with error handling)")
    print("2. Direct pg_dump/pg_restore (faster for large databases)")
    print("3. Cancel")
    
    choice = input("\nEnter choice (1, 2, or 3): ").strip()
    
    if choice == '1':
        print("\n⚠ WARNING: This will replace all data in the target database!")
        response = input("Do you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            sys.exit(0)
        
        migrator = SafeDataMigrator()
        success = migrator.run()
        
        if success:
            print("\n✓ Migration completed successfully!")
            sys.exit(0)
        else:
            print("\n✗ Migration completed with errors!")
            sys.exit(1)
            
    elif choice == '2':
        print("\n⚠ WARNING: This will replace all data in the target database!")
        response = input("Do you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            sys.exit(0)
        
        success = direct_pg_dump_restore()
        
        if success:
            print("\n✓ Migration completed successfully!")
            sys.exit(0)
        else:
            print("\n✗ Migration failed!")
            sys.exit(1)
    else:
        print("Migration cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()