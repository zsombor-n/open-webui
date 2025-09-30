#!/usr/bin/env python3
"""
Script to check the analytics database tables and their data.
This script connects to the cogniforce database and checks:
1. Which analytics tables exist
2. How many records are in each table
3. What data is available
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

try:
    from open_webui.internal.cogniforce_db import get_cogniforce_db, cogniforce_engine
    from sqlalchemy import text, inspect
    from datetime import datetime
    import traceback

    def check_analytics_tables():
        """Check analytics tables and their data."""
        print("=" * 60)
        print("ANALYTICS DATABASE CHECK")
        print("=" * 60)
        print(f"Timestamp: {datetime.now()}")
        print()

        try:
            # Check database connection
            print("1. DATABASE CONNECTION")
            print("-" * 30)

            with get_cogniforce_db() as db:
                # Test basic connection
                result = db.execute(text("SELECT 1 as test"))
                test_row = result.fetchone()
                print(f"✓ Database connection successful: {test_row[0] == 1}")
                print()

                # Check what tables exist
                print("2. EXISTING TABLES")
                print("-" * 30)

                inspector = inspect(cogniforce_engine)
                all_tables = inspector.get_table_names()
                print(f"Total tables in database: {len(all_tables)}")

                analytics_tables = [
                    'chat_analysis',
                    'daily_aggregates',
                    'processing_log'
                ]

                existing_analytics_tables = []
                for table in analytics_tables:
                    if table in all_tables:
                        existing_analytics_tables.append(table)
                        print(f"✓ {table} - EXISTS")
                    else:
                        print(f"✗ {table} - MISSING")

                print(f"\nAll tables in database: {all_tables}")
                print()

                # Check record counts for existing analytics tables
                if existing_analytics_tables:
                    print("3. RECORD COUNTS")
                    print("-" * 30)

                    for table in existing_analytics_tables:
                        try:
                            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                            count = result.fetchone()[0]
                            print(f"{table}: {count} records")

                            # Get sample data if records exist
                            if count > 0:
                                print(f"  Sample from {table}:")
                                sample_result = db.execute(text(f"SELECT * FROM {table} LIMIT 3"))
                                columns = sample_result.keys()
                                print(f"    Columns: {list(columns)}")

                                for i, row in enumerate(sample_result.fetchall()):
                                    row_dict = dict(zip(columns, row))
                                    # Only show first few fields to avoid overwhelming output
                                    limited_row = {k: v for k, v in list(row_dict.items())[:5]}
                                    print(f"    Row {i+1}: {limited_row}")
                                print()

                        except Exception as e:
                            print(f"✗ Error querying {table}: {e}")

                else:
                    print("3. RECORD COUNTS")
                    print("-" * 30)
                    print("No analytics tables found - cannot check record counts")
                    print()

                # Check if alembic migrations table exists
                print("4. MIGRATION STATUS")
                print("-" * 30)

                if 'alembic_version' in all_tables:
                    result = db.execute(text("SELECT version_num FROM alembic_version"))
                    version = result.fetchone()
                    if version:
                        print(f"✓ Alembic version: {version[0]}")
                    else:
                        print("✗ No alembic version found")
                else:
                    print("✗ No alembic_version table found - migrations may not have run")

                print()

                # Summary and recommendations
                print("5. SUMMARY & RECOMMENDATIONS")
                print("-" * 30)

                if not existing_analytics_tables:
                    print("❌ NO ANALYTICS TABLES FOUND")
                    print("\nThis explains why the user-breakdown endpoint returns empty arrays.")
                    print("\nTo fix this, you need to:")
                    print("1. Run database migrations to create the analytics tables")
                    print("2. Run the analytics processor to populate the tables with data")
                    print("\nCommands to run:")
                    print("  cd backend/")
                    print("  python -m alembic -c cogniforce_alembic.ini upgrade head")
                    print("  # Then trigger analytics processing via the API")

                elif sum(1 for table in existing_analytics_tables if table in ['chat_analysis', 'daily_aggregates']) == 0:
                    print("❌ ANALYTICS TABLES EXIST BUT ARE EMPTY")
                    print("\nThis explains why the user-breakdown endpoint returns empty arrays.")
                    print("\nTo fix this, you need to:")
                    print("1. Run the analytics processor to analyze existing chats")
                    print("2. This will populate chat_analysis and daily_aggregates tables")
                    print("\nThe analytics processor should run automatically, but you can trigger it manually via the API.")

                else:
                    total_chats = 0
                    total_aggregates = 0

                    if 'chat_analysis' in existing_analytics_tables:
                        result = db.execute(text("SELECT COUNT(*) FROM chat_analysis"))
                        total_chats = result.fetchone()[0]

                    if 'daily_aggregates' in existing_analytics_tables:
                        result = db.execute(text("SELECT COUNT(*) FROM daily_aggregates"))
                        total_aggregates = result.fetchone()[0]

                    if total_chats > 0 and total_aggregates > 0:
                        print("✅ ANALYTICS TABLES HAVE DATA")
                        print(f"   - {total_chats} chat analyses")
                        print(f"   - {total_aggregates} daily aggregates")
                        print("\nThe user-breakdown endpoint should return data.")
                        print("If it's still returning empty arrays, check the API logic.")
                    else:
                        print("⚠️  ANALYTICS TABLES EXIST BUT LACK SUFFICIENT DATA")
                        print(f"   - {total_chats} chat analyses")
                        print(f"   - {total_aggregates} daily aggregates")
                        print("\nYou may need to run the analytics processor to generate more data.")

        except Exception as e:
            print(f"❌ DATABASE CONNECTION FAILED: {e}")
            print("\nFull error details:")
            traceback.print_exc()
            print("\nPossible causes:")
            print("1. Database server is not running")
            print("2. Database credentials are incorrect")
            print("3. Database does not exist")
            print("4. Network connectivity issues")

        print("\n" + "=" * 60)

    if __name__ == "__main__":
        check_analytics_tables()

except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Make sure you're running this from the correct directory and all dependencies are installed.")