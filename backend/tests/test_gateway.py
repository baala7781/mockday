"""Test script for API Gateway."""
import sys
import os

# Add backend directory to path (tests directory is one level deep)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports
try:
    from shared.config.settings import settings
    print("✅ Settings imported successfully")
    print(f"   API Gateway Port: {settings.API_GATEWAY_PORT}")
    print(f"   Frontend URL: {settings.FRONTEND_URL}")
    
    from shared.db.redis_client import redis_client
    print("✅ Redis client imported successfully")
    
    from api_gateway.main import app
    print("✅ API Gateway imported successfully")
    print(f"   App title: {app.title}")
    print(f"   App version: {app.version}")
    
    print("\n✅ All imports successful! API Gateway is ready to run.")
    print("\nTo start the API Gateway, run:")
    print("  cd api_gateway")
    print("  PYTHONPATH=.. uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print("\nOr from the backend directory:")
    print("  PYTHONPATH=. uvicorn api_gateway.main:app --host 0.0.0.0 --port 8000 --reload")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

