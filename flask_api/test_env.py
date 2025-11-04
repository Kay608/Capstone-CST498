from dotenv import load_dotenv
import os
from pathlib import Path

print("Testing environment variable loading...")

# Load .env file from current directory
load_dotenv()

# Print environment variables
print("\nEnvironment variables:")
print(f"DB_HOST = {os.environ.get('DB_HOST')}")
print(f"DB_USER = {os.environ.get('DB_USER')}")
print(f"DB_PASSWORD = {'[SET]' if os.environ.get('DB_PASSWORD') else '[NOT SET]'}")
print(f"DB_NAME = {os.environ.get('DB_NAME')}")