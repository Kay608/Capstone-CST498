#!/usr/bin/env python3
"""
Utility script to manually download and cache face encodings from JawsDB.
Run this when you have internet to prepare for offline operation.

Usage:
    python sync_encodings.py              # Download and cache
    python sync_encodings.py --check      # Check cache status
    python sync_encodings.py --clear      # Clear local cache
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_facial_recognition import load_encodings_from_db, save_encodings_cache, load_encodings_cache, BASE_DIR


def sync_encodings():
    """Download encodings from database and save to cache."""
    print("=" * 50)
    print("Syncing Face Encodings to Local Cache")
    print("=" * 50)
    
    print("\n[1/3] Connecting to JawsDB...")
    encodings, names = load_encodings_from_db()
    
    if not encodings:
        print("[ERROR] No encodings loaded from database!")
        print("  - Check your .env file has correct DB credentials")
        print("  - Ensure at least one face is enrolled via Flask app")
        return False
    
    print(f"[2/3] Downloaded {len(encodings)} face encoding(s)")
    for banner_id, name in names:
        print(f"  - {name} ({banner_id})")
    
    print("\n[3/3] Saving to local cache...")
    if save_encodings_cache(encodings, names):
        print("\n✓ Sync complete! Robot can now run offline.")
        return True
    else:
        print("\n✗ Failed to save cache")
        return False


def check_cache():
    """Check status of local cache."""
    print("=" * 50)
    print("Local Cache Status")
    print("=" * 50)
    
    cache_file = BASE_DIR / "cache" / "face_encodings.npz"
    
    if not cache_file.exists():
        print("\n✗ No cache file found")
        print(f"  Expected location: {cache_file}")
        print("\n  Run: python sync_encodings.py")
        print("  to download and cache encodings.")
        return False
    
    print(f"\n✓ Cache file exists: {cache_file}")
    print(f"  Size: {cache_file.stat().st_size / 1024:.1f} KB")
    print(f"  Modified: {cache_file.stat().st_mtime}")
    
    print("\nLoading cache...")
    encodings, names = load_encodings_cache()
    
    if encodings is None:
        print("✗ Failed to load cache")
        return False
    
    print(f"\n✓ Cache contains {len(encodings)} face encoding(s):")
    for banner_id, name in names:
        print(f"  - {name} ({banner_id})")
    
    print("\n✓ Robot can run offline with these faces.")
    return True


def clear_cache():
    """Clear local cache."""
    cache_file = BASE_DIR / "cache" / "face_encodings.npz"
    
    if not cache_file.exists():
        print("No cache to clear.")
        return
    
    try:
        cache_file.unlink()
        print(f"✓ Cleared cache: {cache_file}")
    except Exception as e:
        print(f"✗ Failed to clear cache: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage local face encoding cache for offline operation."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check cache status without syncing"
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear local cache"
    )
    
    args = parser.parse_args()
    
    if args.clear:
        clear_cache()
    elif args.check:
        check_cache()
    else:
        sync_encodings()


if __name__ == "__main__":
    main()
