#!/usr/bin/env python3
"""
Check existing users in the database
"""

import pymysql
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path('.').resolve()
load_dotenv(BASE_DIR / '.env', override=False)
load_dotenv(BASE_DIR / 'flask_api' / '.env', override=False)

DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

try:
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    print('=== Available Banner IDs in Users Table ===')
    cursor.execute('SELECT banner_id, first_name, last_name FROM users LIMIT 10')
    users = cursor.fetchall()
    
    for banner_id, first_name, last_name in users:
        print(f'{banner_id}: {first_name} {last_name}')
    
    if len(users) == 10:
        cursor.execute('SELECT COUNT(*) FROM users')
        total = cursor.fetchone()[0]
        print(f'... and {total - 10} more users')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'Error: {e}')