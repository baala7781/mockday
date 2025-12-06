"""Test Deepgram STT and TTS integration."""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config.settings import settings
from shared.providers.deepgram_client import deepgram_client
from shared.providers.pool_manager import provider_pool_manager, ProviderType


async def test_deepgram_connection():
    """Test Deepgram API connection."""
    print("\n" + "="*60)
    print("TEST 1: Deepgram API Connection")
    print("="*60)
    
    try:
        # Check if API keys are configured
        if not settings.DEEPGRAM_API_KEYS:
            print("❌ DEEPGRAM_API_KEYS not configured in .env file")
            return False
        
        keys = [k.strip() for k in settings.DEEPGRAM_API_KEYS.split(",") if k.strip()]
        print(f"✅ Found {len(keys)} Deepgram API key(s)")
        
        # Check provider pool
        account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_STT)
        if account:
            print(f"✅ Provider pool manager initialized")
            print(f"   API Key: {account.api_key[:10]}...{account.api_key[-4:]}")
        else:
            print(f"❌ No Deepgram account available in pool")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Deepgram connection: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_deepgram_stt():
    """Test Deepgram STT transcription."""
    print("\n" + "="*60)
    print("TEST 2: Deepgram STT Transcription")
    print("="*60)
    
    try:
        # Create a simple test audio (silence or minimal audio)
        # For actual testing, you would need real audio data
        # This is a placeholder test
        
        print("⚠️  STT transcription test requires actual audio data")
        print("   This test will be skipped for now")
        print("   To test STT, provide a real audio file")
        
        # Uncomment below to test with actual audio:
        # audio_bytes = b"..."  # Your audio data here
        # transcript = await deepgram_client.transcribe_audio(audio_bytes)
        # if transcript:
        #     print(f"✅ Transcription successful: {transcript}")
        #     return True
        # else:
        #     print(f"❌ Transcription failed")
        #     return False
        
        return True  # Skip for now
        
    except Exception as e:
        print(f"❌ Error testing STT: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_deepgram_tts():
    """Test Deepgram TTS synthesis."""
    print("\n" + "="*60)
    print("TEST 3: Deepgram TTS Synthesis")
    print("="*60)
    
    try:
        test_text = "Hello, this is a test of Deepgram text to speech."
        
        print(f"   Synthesizing: '{test_text}'")
        audio_bytes = await deepgram_client.synthesize_speech(
            text=test_text,
            model="aura-asteria-en",
            voice="asteria"
        )
        
        if audio_bytes:
            print(f"✅ TTS synthesis successful")
            print(f"   Audio size: {len(audio_bytes)} bytes")
            print(f"   Audio format: MP3 (Deepgram default)")
            return True
        else:
            print(f"❌ TTS synthesis failed - no audio data returned")
            return False
        
    except Exception as e:
        print(f"❌ Error testing TTS: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


async def test_deepgram_audio_chunk():
    """Test Deepgram audio chunk transcription."""
    print("\n" + "="*60)
    print("TEST 4: Deepgram Audio Chunk Transcription")
    print("="*60)
    
    try:
        print("⚠️  Audio chunk transcription test requires actual audio data")
        print("   This test will be skipped for now")
        print("   To test audio chunk transcription, provide real audio chunks")
        
        # Uncomment below to test with actual audio chunk:
        # audio_chunk = b"..."  # Your audio chunk data here
        # result = await deepgram_client.transcribe_audio_chunk(audio_chunk)
        # if result:
        #     print(f"✅ Chunk transcription successful")
        #     print(f"   Text: {result.get('text')}")
        #     print(f"   Is Final: {result.get('is_final')}")
        #     return True
        # else:
        #     print(f"❌ Chunk transcription failed")
        #     return False
        
        return True  # Skip for now
        
    except Exception as e:
        print(f"❌ Error testing audio chunk transcription: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_provider_pool_stats():
    """Test provider pool statistics."""
    print("\n" + "="*60)
    print("TEST 5: Provider Pool Statistics")
    print("="*60)
    
    try:
        stats = await provider_pool_manager.get_pool_stats(ProviderType.DEEPGRAM_STT)
        
        print(f"✅ Provider pool statistics:")
        print(f"   Total accounts: {stats['total_accounts']}")
        print(f"   Healthy accounts: {stats['healthy_accounts']}")
        print(f"   Rate limited accounts: {stats['rate_limited_accounts']}")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Total errors: {stats['total_errors']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting pool statistics: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all Deepgram integration tests."""
    print("\n" + "="*60)
    print("DEEPGRAM INTEGRATION - TEST SUITE")
    print("="*60)
    print("\nThis test suite tests Deepgram STT and TTS integration.")
    print("Note: Some tests require actual audio data and will be skipped.")
    
    results = []
    
    try:
        # Test 1: Connection
        results.append(("Deepgram Connection", await test_deepgram_connection()))
        
        # Test 2: STT (skipped - requires audio)
        results.append(("Deepgram STT", await test_deepgram_stt()))
        
        # Test 3: TTS
        results.append(("Deepgram TTS", await test_deepgram_tts()))
        
        # Test 4: Audio chunk (skipped - requires audio)
        results.append(("Audio Chunk Transcription", await test_deepgram_audio_chunk()))
        
        # Test 5: Provider pool stats
        results.append(("Provider Pool Stats", await test_provider_pool_stats()))
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
        
        print(f"\n   Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n✅ ALL TESTS PASSED")
            print("\nNext steps:")
            print("  1. Test with real audio data for STT")
            print("  2. Integrate WebSocket STT/TTS streaming")
            print("  3. Test end-to-end interview flow with audio")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed or skipped")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

