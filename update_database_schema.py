#!/usr/bin/env python3
"""
Script to update JawsDB orders table to add missing columns
Run this once to fix the database schema
"""

import pymysql
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)

DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

def update_database_schema():
    """Add missing columns to orders table"""
    
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[ERROR] Database credentials not configured")
        return False
    
    try:
        # Connect to database
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with conn.cursor() as cur:
            # Check which columns exist
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'orders'
            """, (DB_NAME,))
            
            existing_columns = {row['COLUMN_NAME'] for row in cur.fetchall()}
            print(f"[INFO] Existing columns: {', '.join(sorted(existing_columns))}")
            
            changes_made = False
            
            # Add restaurant column if missing
            if 'restaurant' not in existing_columns:
                print("[INFO] Adding restaurant column...")
                cur.execute("""
                    ALTER TABLE orders 
                    ADD COLUMN restaurant VARCHAR(255)
                """)
                changes_made = True
                
            # Add status column if missing
            if 'status' not in existing_columns:
                print("[INFO] Adding status column...")
                cur.execute("""
                    ALTER TABLE orders 
                    ADD COLUMN status VARCHAR(50) DEFAULT 'pending'
                """)
                changes_made = True
                
            # Add timestamp column if missing
            if 'ts' not in existing_columns:
                print("[INFO] Adding timestamp column...")
                cur.execute("""
                    ALTER TABLE orders 
                    ADD COLUMN ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                changes_made = True
                
            if changes_made:
                conn.commit()
                print("[SUCCESS] Database schema updated successfully!")
                
                # Show updated table structure
                cur.execute("DESCRIBE orders")
                columns = cur.fetchall()
                print("\nUpdated table structure:")
                for col in columns:
                    print(f"  {col['Field']}: {col['Type']} {'NULL' if col['Null'] == 'YES' else 'NOT NULL'}")
            else:
                print("[INFO] All required columns already exist")
                
            return True
                
    except pymysql.MySQLError as e:
        print(f"[ERROR] Database error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    print("=== JawsDB Schema Update ===")
    print("Checking and updating orders table schema...")
    print()
    
    success = update_database_schema()
    
    if success:
        print("\n✅ Database schema check complete!")
        print("Your Flask app should now work properly with orders.")
    else:
        print("\n❌ Database update failed!")
        print("Please check your database credentials and try again.")