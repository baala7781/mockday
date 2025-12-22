"""List available Gemini models for the current API key."""
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv("GEMINI_API_KEYS", "").split(",")[0].strip() if os.getenv("GEMINI_API_KEYS") else None

if not api_key:
    print("❌ GEMINI_API_KEYS not found in environment variables")
    print("Please set GEMINI_API_KEYS in your .env file")
    sys.exit(1)

print(f"🔑 Using API key: {api_key[:10]}...{api_key[-4:]}")
print("\n📋 Listing available Gemini models...\n")

try:
    genai.configure(api_key=api_key)
    
    # List all available models
    models = genai.list_models()
    
    print("✅ Available models:\n")
    for model in models:
        # Filter for generation models only
        if 'generateContent' in model.supported_generation_methods:
            model_name = model.name.replace('models/', '')
            print(f"  • {model_name}")
            if hasattr(model, 'display_name'):
                print(f"    Display Name: {model.display_name}")
            print(f"    Supported Methods: {', '.join(model.supported_generation_methods)}")
            print()
    
    # Also try some common model names directly
    print("\n🧪 Testing common model names:\n")
    test_models = [
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-live",
        "gemini-2.5-flash-lite-live",
        "gemini-2.5-flash-lite-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    
    for model_name in test_models:
        try:
            model = genai.GenerativeModel(model_name)
            print(f"  ✅ {model_name} - Available")
        except Exception as e:
            print(f"  ❌ {model_name} - Not available: {str(e)[:80]}")
    
except Exception as e:
    print(f"❌ Error listing models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)