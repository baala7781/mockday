"""Check Gemini API key configuration."""
import os
import sys
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Install it with: pip install python-dotenv")

def check_api_keys():
    """Check if API keys are configured."""
    print("\n" + "="*60)
    print("Gemini API Keys Configuration Check")
    print("="*60)
    
    # Check Gemini API keys
    gemini_keys = os.getenv("GEMINI_API_KEYS", "")
    if not gemini_keys or gemini_keys == "your-gemini-api-key-here":
        print("❌ GEMINI_API_KEYS not configured")
        print("\nTo configure:")
        print("1. Open the .env file in the backend directory")
        print("2. Replace 'your-gemini-api-key-here' with your actual Gemini API key")
        print("3. Get your API key from: https://makersuite.google.com/app/apikey")
        print("\nExample:")
        print("   GEMINI_API_KEYS=AIzaSy...")
        return False
    else:
        keys = [k.strip() for k in gemini_keys.split(",") if k.strip()]
        print(f"✅ GEMINI_API_KEYS found: {len(keys)} key(s)")
        for i, key in enumerate(keys, 1):
            if len(key) > 14:
                masked_key = key[:10] + "..." + key[-4:]
            else:
                masked_key = "***"
            print(f"   Key {i}: {masked_key}")
        
        # Check if it looks like a valid key
        if keys[0].startswith("AIza"):
            print("   ✅ Key format looks valid")
        else:
            print("   ⚠️  Key format may be invalid (should start with 'AIza')")
        
        return True


def main():
    """Main function."""
    print("\n" + "="*60)
    print("Gemini API Keys Setup Checker")
    print("="*60)
    
    # Change to backend directory to find .env file
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(backend_dir)
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("\nCreating .env file template...")
        with open(".env", "w") as f:
            f.write("GEMINI_API_KEYS=your-gemini-api-key-here\n")
        print("✅ .env file created")
        print("\nPlease edit .env file and add your Gemini API key")
        return
    
    print("✅ .env file found")
    
    # Check API keys
    if check_api_keys():
        print("\n✅ API keys are configured")
        print("\nNext steps:")
        print("1. Run: python tests/test_gemini_integration.py")
        print("2. This will test the Gemini integration with your API key")
    else:
        print("\n⚠️  Please configure your API keys before testing")


if __name__ == "__main__":
    main()

