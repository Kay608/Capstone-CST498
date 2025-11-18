#!/usr/bin/env python3
"""
Flask Connection Test
====================

Tests connectivity to Flask admin panel and finds the correct URL.
"""

import requests
import time

# URLs to test
test_urls = [
    "http://localhost:5000",
    "http://127.0.0.1:5000", 
    "http://localhost:5001",
    "http://127.0.0.1:5001",
    "http://10.202.65.203:5001"  # Original IP
]

def test_flask_connection():
    """Test connection to Flask app on multiple URLs."""
    print("🧪 Testing Flask App Connectivity")
    print("=" * 50)
    
    working_urls = []
    
    for url in test_urls:
        try:
            print(f"📡 Testing {url}...")
            
            # Try a simple GET request first
            response = requests.get(f"{url}/", timeout=3)
            
            if response.status_code == 200:
                print(f"✅ {url} - Flask app is running!")
                working_urls.append(url)
                
                # Test API endpoints
                try:
                    api_response = requests.get(f"{url}/api/health", timeout=2)
                    if api_response.status_code == 200:
                        print(f"   ✅ API endpoint working")
                    else:
                        print(f"   ⚠️ API endpoint returned {api_response.status_code}")
                except:
                    print(f"   ⚠️ No health API endpoint")
                    
            else:
                print(f"❌ {url} - HTTP {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {url} - Connection refused (Flask not running)")
        except requests.exceptions.Timeout:
            print(f"❌ {url} - Connection timeout")
        except Exception as e:
            print(f"❌ {url} - Error: {e}")
    
    print("\\n" + "=" * 50)
    
    if working_urls:
        print(f"✅ Found {len(working_urls)} working Flask URL(s):")
        for url in working_urls:
            print(f"   🌐 {url}")
        
            print(f"\\n🔧 To update recognition_core.py:")
            print(f'   Set FLASK_APP_URL = "{working_urls[0]}"')
        
    else:
        print("❌ No working Flask URLs found!")
        print("\\n🚀 To start Flask app:")
        print("   cd flask_api")
        print("   python app.py")
        print("\\n   Or use integrated system:")
        print("   python integrated_recognition_system.py")
    
    return working_urls

def start_flask_app():
    """Instructions for starting Flask app."""
    print("\\n🚀 Starting Flask App Instructions:")
    print("=" * 50)
    print("1. Open a new terminal")
    print("2. Navigate to flask_api directory:")
    print("   cd flask_api")
    print("3. Run the Flask app:")
    print("   python app.py")
    print("4. The app should start on http://localhost:5000 or http://localhost:5001")
    print("5. You should see output like:")
    print("   * Running on all addresses (0.0.0.0)")
    print("   * Running on http://127.0.0.1:5001")

if __name__ == "__main__":
    working_urls = test_flask_connection()
    
    if not working_urls:
        start_flask_app()
    
    print("\\n🔄 Run this test again after starting Flask to verify connectivity.")