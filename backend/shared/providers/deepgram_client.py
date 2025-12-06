# """
# Deepgram client for STT and TTS – fully compatible with SDK v3.6–v3.8
# Fixes:
#  - handler signature mismatch
#  - event metadata keyword issue
#  - parsing LiveResultResponse safely
#  - prevents 'result' unexpected keyword arg errors
#  - prevents channel attribute errors
# """
# from deepgram import DeepgramClient, LiveOptions, PrerecordedOptions, LiveTranscriptionEvents
# from shared.providers.pool_manager import provider_pool_manager, ProviderType
# from typing import Optional, Callable, Dict
# import asyncio
# import logging

# logger = logging.getLogger(__name__)


# # =====================================================================
# # LIVE SESSION
# # =====================================================================
# class DeepgramLiveSession:
#     def __init__(self, api_key: str, model: str, language: str, on_transcript: Callable):
#         self.api_key = api_key
#         self.model = model
#         self.language = language
#         self.on_transcript = on_transcript

#         self.client = DeepgramClient(api_key)
#         self.live_socket = None

#         self.is_open = False
#         self._lock = asyncio.Lock()

#     async def start(self):
#         async with self._lock:
#             if self.is_open:
#                 return

#             try:
#                 self.live_socket = self.client.listen.live.v("1")

#                 # ---------------------------------------
#                 # FIXED CALLBACKS (Deepgram SDK 3.6–3.8)
#                 # ---------------------------------------
#                 # Deepgram may pass arguments in different ways, so accept *args, **kwargs
#                 def handle_transcript(*args, **kwargs):
#                     try:
#                         # Deepgram sends: handler(result, metadata)
#                         result = args[0] if len(args) >= 1 else None
#                         if result is None:
#                             return

#                         # Determine alternative path
#                         alt = None
#                         if hasattr(result, "channel") and getattr(result, "channel", None):
#                             channel = result.channel
#                             if channel.alternatives:
#                                 alt = channel.alternatives[0]
#                         elif hasattr(result, "alternatives"):
#                             alts = getattr(result, "alternatives")
#                             if alts:
#                                 alt = alts[0]
#                         else:
#                             return  # nothing extractable

#                         if not alt:
#                             return

#                         transcript = getattr(alt, "transcript", None)
#                         confidence = getattr(alt, "confidence", 1.0)
#                         is_final = getattr(result, "is_final", False)

#                         if not transcript:
#                             return

#                         payload = {
#                             "text": transcript,
#                             "is_final": is_final,
#                             "confidence": confidence
#                         }

#                         # Support sync + async callback
#                         if asyncio.iscoroutinefunction(self.on_transcript):
#                             asyncio.create_task(self.on_transcript(payload))
#                         else:
#                             asyncio.get_event_loop().run_in_executor(None, self.on_transcript, payload)

#                     except Exception as e:
#                         logger.error(f"[Deepgram] Transcript handler error: {e}", exc_info=True)

#                 def handle_error(*args, **kwargs):
#                     # Extract error from args or kwargs
#                     error = args[0] if args else kwargs.get('result') or kwargs.get('event') or kwargs.get('error')
#                     logger.error(f"[Deepgram] Error: {error}")
#                     self.is_open = False

#                 def handle_close(*args, **kwargs):
#                     # Accept any number of arguments (Deepgram may pass 0, 1, or 2 positional args)
#                     logger.info("[Deepgram] WebSocket closed")
#                     self.is_open = False

#                 # Register handlers (correct signatures)
#                 self.live_socket.on(LiveTranscriptionEvents.Transcript, handle_transcript)
#                 self.live_socket.on(LiveTranscriptionEvents.Error, handle_error)
#                 self.live_socket.on(LiveTranscriptionEvents.Close, handle_close)

#                 # Live STT options
#                 opts = LiveOptions(
#                     model=self.model,
#                     language=self.language,
#                     encoding="linear16",
#                     sample_rate=16000,
#                     channels=1,
#                     interim_results=True,
#                     smart_format=True,
#                 )

#                 start_ret = self.live_socket.start(opts)
#                 if asyncio.iscoroutine(start_ret):
#                     await start_ret

#                 self.is_open = True
#                 logger.info("✓ Deepgram Live WebSocket started")

#             except Exception as e:
#                 logger.error(f"[Deepgram] Failed to start live session: {e}", exc_info=True)
#                 self.is_open = False
#                 raise

#     async def send_audio(self, audio_chunk: bytes):
#         if not self.is_open:
#             return False
#         try:
#             ret = self.live_socket.send(audio_chunk)
#             if asyncio.iscoroutine(ret):
#                 await ret
#             return True
#         except Exception as e:
#             logger.error(f"[Deepgram] Error sending audio: {e}", exc_info=True)
#             self.is_open = False
#             return False

#     async def close(self):
#         async with self._lock:
#             if not self.is_open:
#                 return
#             try:
#                 ret = self.live_socket.finish()
#                 if asyncio.iscoroutine(ret):
#                     await ret
#             except Exception as e:
#                 logger.error(f"[Deepgram] Error closing live socket: {e}", exc_info=True)
#             finally:
#                 self.is_open = False


# # =====================================================================
# # WRAPPER CLASS
# # =====================================================================
# class DeepgramClientWrapper:
#     def __init__(self):
#         self._live_sessions: Dict[str, DeepgramLiveSession] = {}
#         self._sessions_lock = asyncio.Lock()

#     # ------------------------------
#     # START LIVE STT SESSION
#     # ------------------------------
#     async def start_live_session(self, interview_id: str, on_transcript: Callable,
#                                  model="nova-2", language="en-US") -> bool:
#         account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_STT)
#         if not account:
#             logger.error("[Deepgram] No STT account available")
#             return False

#         async with self._sessions_lock:
#             if interview_id in self._live_sessions:
#                 await self._live_sessions[interview_id].close()

#             try:
#                 session = DeepgramLiveSession(
#                     api_key=account.api_key,
#                     model=model,
#                     language=language,
#                     on_transcript=on_transcript
#                 )
#                 await session.start()

#                 self._live_sessions[interview_id] = session
#                 await provider_pool_manager.mark_success(account)

#                 logger.info(f"✓ Started Live STT for interview {interview_id}")
#                 return True

#             except Exception as e:
#                 msg = str(e)
#                 logger.error(f"[Deepgram] Live session start failed: {msg}", exc_info=True)
#                 await provider_pool_manager.mark_error(account, msg)
#                 return False

#     # ------------------------------
#     # SEND AUDIO
#     # ------------------------------
#     async def send_audio_chunk(self, interview_id: str, audio_chunk: bytes):
#         async with self._sessions_lock:
#             session = self._live_sessions.get(interview_id)
#             if not session:
#                 logger.warning(f"[Deepgram] No active STT session for {interview_id}")
#                 return False
#             return await session.send_audio(audio_chunk)

#     # ------------------------------
#     # STOP LIVE SESSION
#     # ------------------------------
#     async def stop_live_session(self, interview_id: str):
#         async with self._sessions_lock:
#             session = self._live_sessions.pop(interview_id, None)
#             if session:
#                 await session.close()
#                 logger.info(f"✓ Stopped Live STT for {interview_id}")

#     # ------------------------------
#     # TTS SYNTHESIS
#     # ------------------------------
#     async def synthesize_speech(self, text: str,
#                                 model="aura-asteria-en",
#                                 voice="asteria") -> Optional[bytes]:
#         account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_TTS)
#         if not account:
#             logger.error("[Deepgram] No TTS account available")
#             return None

#         try:
#             from deepgram.clients.common.v1.options import TextSource
#             from deepgram.clients.speak.v1.rest.options import SpeakRESTOptions
#             import io

#             client = DeepgramClient(account.api_key)
#             source = TextSource(text=text)
#             opts = SpeakRESTOptions(model=model)

#             logger.info(f"[Deepgram] Generating TTS: text_len={len(text)}, model={model}")
            
#             # stream_memory() returns a BytesIO object directly
#             response = client.speak.v("1").stream_memory(source=source, options=opts)
            
#             # Extract audio bytes from response
#             audio = None
            
#             # Method 1: If it's a BytesIO object (or has read method)
#             if hasattr(response, 'read'):
#                 audio = response.read()
#                 if isinstance(audio, bytes) and len(audio) > 0:
#                     logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via read()")
#                     await provider_pool_manager.mark_success(account)
#                     return audio
            
#             # Method 2: If it has stream_memory as an attribute that returns BytesIO
#             if hasattr(response, "stream_memory"):
#                 stream_obj = response.stream_memory
#                 if callable(stream_obj):
#                     stream_obj = stream_obj()
#                 if hasattr(stream_obj, 'read'):
#                     audio = stream_obj.read()
#                     if isinstance(audio, bytes) and len(audio) > 0:
#                         logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via stream_memory().read()")
#                         await provider_pool_manager.mark_success(account)
#                         return audio
            
#             # Method 3: If it has a stream() method (iterator)
#             if hasattr(response, 'stream'):
#                 audio = b"".join(response.stream())
#                 if isinstance(audio, bytes) and len(audio) > 0:
#                     logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via stream()")
#                     await provider_pool_manager.mark_success(account)
#                     return audio
            
#             # Method 4: If it's already bytes
#             if isinstance(response, bytes):
#                 if len(response) > 0:
#                     logger.info(f"[Deepgram] TTS success: got {len(response)} bytes directly")
#                     await provider_pool_manager.mark_success(account)
#                     return response
            
#             # Method 5: Try to get bytes from response object
#             if hasattr(response, '__bytes__'):
#                 try:
#                     audio = bytes(response)
#                     if len(audio) > 0:
#                         logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via __bytes__()")
#                         await provider_pool_manager.mark_success(account)
#                         return audio
#                 except:
#                     pass
            
#             # Log what we got
#             logger.error(f"[Deepgram] TTS failed: response type={type(response)}, has_read={hasattr(response, 'read')}, has_stream={hasattr(response, 'stream')}, dir={[x for x in dir(response) if not x.startswith('_')][:10]}")
#             await provider_pool_manager.mark_error(account, "Empty TTS audio - unable to extract bytes")
#             return None

#         except Exception as e:
#             msg = str(e)
#             logger.error(f"[Deepgram] TTS error: {msg}", exc_info=True)
#             await provider_pool_manager.mark_error(account, msg)
#             return None


# # GLOBAL INSTANCE
# deepgram_client = DeepgramClientWrapper()



"""
backend/shared/providers/deepgram_client.py

STT-only Deepgram Live WebSocket client compatible with Deepgram SDK v3.6 - v3.8.

Usage:
    from shared.providers.deepgram_client import deepgram_client
    await deepgram_client.start_live_session(interview_id, on_transcript_callback)
    await deepgram_client.send_audio_chunk(interview_id, pcm16_bytes)
    await deepgram_client.stop_live_session(interview_id)
"""

from typing import Callable, Dict, Optional, Any
import asyncio
import logging
import traceback
import time

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from shared.providers.pool_manager import provider_pool_manager, ProviderType

logger = logging.getLogger(__name__)


class DeepgramLiveSession:
    """
    Manages a single Deepgram Live WebSocket session for real-time STT.

    - `on_transcript` should accept a dict: {"text": str, "is_final": bool, "confidence": float}
    - This class is defensive against Deepgram SDK variants (sync vs async start/send/finish)
    """

    def __init__(self, api_key: str, model: str, language: str, on_transcript: Callable[[dict], Any]):
        # Log API key info (masked for security)
        api_key_preview = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        logger.info(f"[Deepgram] Initializing DeepgramLiveSession with API key: {api_key_preview} (length: {len(api_key)})")
        logger.info(f"[Deepgram] Model: {model}, Language: {language}")
        
        # Validate API key format
        if not api_key or len(api_key.strip()) == 0:
            logger.error("[Deepgram] ERROR: API key is empty!")
            raise ValueError("Deepgram API key cannot be empty")
        if len(api_key) < 20:
            logger.warning(f"[Deepgram] WARNING: API key seems too short (length: {len(api_key)}). Deepgram keys are usually longer.")
        # Note: Deepgram API keys can have various formats, not all start with 'dg_'
        # The prefix check is informational only, not a hard requirement
        if not api_key.startswith(('dg_', 'DEEPGRAM_')):
            logger.debug(f"[Deepgram] API key format: First 10 chars: {api_key[:10]} (format may vary)")
        
        self.api_key = api_key
        self.model = model
        self.language = language
        self.on_transcript = on_transcript

        # Deepgram client
        logger.info(f"[Deepgram] Creating DeepgramClient...")
        try:
            self.client = DeepgramClient(api_key)
            logger.info(f"[Deepgram] DeepgramClient created successfully")
        except Exception as e:
            logger.error(f"[Deepgram] ERROR creating DeepgramClient: {type(e).__name__}: {e}", exc_info=True)
            raise
        
        self.live_socket = None

        self.is_open = False
        self._lock = asyncio.Lock()

        # small helper to allow graceful shutdown
        self._closing = False
        
        # Track if error occurred during start (set by error handler)
        self._start_error = False
        self._last_error = None
        
        # Store main event loop reference for thread-safe callback scheduling
        # Deepgram SDK calls handlers from background threads without event loops
        self._main_loop = None

    async def start(self) -> None:
        """Start the Deepgram Live connection and register handlers."""
        async with self._lock:
            if self.is_open:
                logger.debug("DeepgramLiveSession.start() called but session already open")
                return

            # Store reference to the main event loop for thread-safe callback scheduling
            # Deepgram SDK calls handlers from background threads that don't have event loops
            try:
                self._main_loop = asyncio.get_running_loop()
                logger.debug(f"[Deepgram] Stored main event loop reference: {self._main_loop}")
            except RuntimeError:
                # If no running loop, try to get the current one
                try:
                    self._main_loop = asyncio.get_event_loop()
                    logger.debug(f"[Deepgram] Stored event loop reference: {self._main_loop}")
                except RuntimeError:
                    logger.warning("[Deepgram] Could not get event loop reference - callbacks may fail")

            try:
                # create the live socket client object (SDK provides listen.live.v("1"))
                logger.info(f"[Deepgram] Creating live socket with client.listen.live.v('1')...")
                try:
                    self.live_socket = self.client.listen.live.v("1")
                    logger.info(f"[Deepgram] Live socket created successfully: {type(self.live_socket).__name__}")
                except Exception as e:
                    logger.error(f"[Deepgram] ERROR creating live socket: {type(e).__name__}: {e}", exc_info=True)
                    raise

                # ---------- Handlers ----------
                # Deepgram calls handlers as: handler(result, metadata)
                # But some older/newer variants may pass slight variations; accept *args/**kwargs and be defensive.

                def _safe_extract_result_from_args(args, kwargs) -> Optional[Any]:
                    """
                    Extract the transcript result from handler arguments.
                    Deepgram may pass the socket as first arg, so we skip it if it's ListenWebSocketClient.
                    """
                    # Strategy: Deepgram SDK v3.6+ may pass (socket, event) or just (event)
                    # Check all args to find the one that looks like a transcript result
                    
                    # First, check if any arg is NOT the socket
                    for arg in args:
                        # Skip socket objects
                        if hasattr(arg, 'send') and hasattr(arg, 'on') and hasattr(arg, 'finish'):
                            continue
                        # This arg is not the socket, likely the event
                        if isinstance(arg, dict) or hasattr(arg, 'channel') or hasattr(arg, 'alternatives') or hasattr(arg, 'results'):
                            return arg
                        # Even if it doesn't have expected attrs, if it's not the socket, try it
                        if not (hasattr(arg, 'send') and hasattr(arg, 'on')):
                            return arg
                    
                    # If all args are sockets or we have no args, check kwargs
                    if kwargs:
                        # Try common event parameter names
                        for key in ['result', 'event', 'data', 'message', 'payload']:
                            if key in kwargs:
                                val = kwargs[key]
                                # Skip if it's the socket
                                if not (hasattr(val, 'send') and hasattr(val, 'on') and hasattr(val, 'finish')):
                                    return val
                    
                    # Last resort: if we have args, return the last one (might be event even if it looks like socket)
                    if args:
                        return args[-1]
                    
                    return None

                def handle_transcript(*args, **kwargs):
                    """
                    Called when Deepgram emits a transcript event.
                    Accepts either:
                    - object-like result with attributes channel / alternatives
                    - dict-like result with results->channels->alternatives
                    """
                    try:
                        logger.debug(f"[Deepgram] handle_transcript called: args={len(args)}, kwargs={list(kwargs.keys())}")
                        if args:
                            logger.debug(f"[Deepgram] First arg type: {type(args[0]).__name__}")
                            if len(args) > 1:
                                logger.debug(f"[Deepgram] Second arg type: {type(args[1]).__name__}")
                            # Log all args types for debugging
                            logger.debug(f"[Deepgram] All args types: {[type(a).__name__ for a in args]}")
                        result = _safe_extract_result_from_args(args, kwargs)
                        if result is None:
                            logger.warning("[Deepgram] transcript handler: no result found in args/kwargs")
                            return
                        
                        # Check if result is still the socket (extraction failed)
                        if hasattr(result, 'send') and hasattr(result, 'on') and hasattr(result, 'finish'):
                            logger.warning(f"[Deepgram] Extracted result is still the socket object. args={len(args)}, kwargs keys={list(kwargs.keys())}")
                            # Try to get from kwargs explicitly
                            if kwargs:
                                result = kwargs.get("result") or kwargs.get("event") or kwargs.get("data") or kwargs.get("message")
                            if result is None or (hasattr(result, 'send') and hasattr(result, 'on')):
                                logger.error(f"[Deepgram] Cannot extract transcript from handler arguments. args={args}, kwargs={kwargs}")
                                return
                        
                        logger.debug(f"[Deepgram] transcript handler: result type={type(result).__name__}, has_channel={hasattr(result, 'channel')}, has_alternatives={hasattr(result, 'alternatives')}, is_dict={isinstance(result, dict)}")

                        # Try object-style access first (LiveResultResponse)
                        alt = None
                        is_final = False
                        confidence = 1.0
                        transcript_text = None

                        # Object-like: result.channel.alternatives[0].transcript
                        # LiveResultResponse has a 'channel' attribute
                        if hasattr(result, "channel") and getattr(result, "channel", None):
                            channel = getattr(result, "channel")
                            # channel may be a simple object with alternatives attr
                            try:
                                # Check if channel has alternatives
                                if hasattr(channel, "alternatives"):
                                    alts = getattr(channel, "alternatives", None)
                                    if alts and len(alts) > 0:
                                        alt = alts[0]
                                        transcript_text = getattr(alt, "transcript", None) or getattr(alt, "text", None)
                                        confidence = float(getattr(alt, "confidence", 1.0) if hasattr(alt, "confidence") else 1.0)
                                        is_final = bool(getattr(result, "is_final", False))
                                # Some LiveResultResponse might not have alternatives (metadata events)
                                # In that case, skip this event gracefully
                                elif not hasattr(channel, "alternatives"):
                                    logger.debug("[Deepgram] LiveResultResponse has channel but no alternatives - likely metadata event, skipping")
                                    return  # Skip this event - no transcript to process
                            except Exception:
                                # fall through to other parsing
                                logger.debug("[Deepgram] transcript handler: object-channel parsing error", exc_info=True)

                        # Dict-like: result["results"]["channels"][0]["alternatives"][0]["transcript"]
                        if not transcript_text and isinstance(result, dict):
                            try:
                                results = result.get("results", {})
                                channels = results.get("channels", []) or []
                                if channels:
                                    first_channel = channels[0]
                                    alternatives = first_channel.get("alternatives", []) or []
                                    if alternatives:
                                        alt_dict = alternatives[0]
                                        transcript_text = alt_dict.get("transcript")
                                        confidence = float(alt_dict.get("confidence", 1.0))
                                        is_final = bool(results.get("is_final", False))
                            except Exception:
                                logger.debug("[Deepgram] transcript handler: dict-style parsing error", exc_info=True)

                        # Some SDK variants expose alternatives directly on result
                        if not transcript_text and hasattr(result, "alternatives"):
                            try:
                                alts = getattr(result, "alternatives")
                                if alts and len(alts) > 0:
                                    alt = alts[0]
                                    transcript_text = getattr(alt, "transcript", None)
                                    confidence = float(getattr(alt, "confidence", 1.0))
                                    is_final = bool(getattr(result, "is_final", False))
                            except Exception:
                                logger.debug("[Deepgram] transcript handler: alternatives parsing error", exc_info=True)

                        if not transcript_text:
                            # Nothing we can extract - might be metadata/finalize event
                            # Check if this looks like a metadata-only event (has is_final but no transcript)
                            is_metadata_event = hasattr(result, "is_final") and hasattr(result, "channel") and hasattr(result, "metadata")
                            if is_metadata_event:
                                logger.debug(f"[Deepgram] Metadata-only event (no transcript), skipping. result type={type(result).__name__}")
                            else:
                                logger.debug(f"[Deepgram] No transcript found in result. result type={type(result).__name__}, dir={[x for x in dir(result) if not x.startswith('_')][:10]}")
                            return  # Skip this event gracefully

                        payload = {
                            "text": transcript_text,
                            "is_final": bool(is_final),
                            "confidence": float(confidence)
                        }

                        logger.info(f"[Deepgram] ✓ Extracted transcript: '{transcript_text}' (final={is_final}, conf={confidence})")
                        
                        # Schedule callback on main event loop (thread-safe)
                        # Deepgram SDK calls this handler from background threads without event loops
                        # We need to use call_soon_threadsafe() to schedule on the main loop
                        try:
                            if asyncio.iscoroutinefunction(self.on_transcript):
                                # Async callback - schedule on main loop using call_soon_threadsafe
                                if self._main_loop and self._main_loop.is_running():
                                    logger.debug(f"[Deepgram] Scheduling async callback on main loop (thread-safe)")
                                    # Use call_soon_threadsafe to schedule from background thread to main loop
                                    self._main_loop.call_soon_threadsafe(
                                        lambda: self._main_loop.create_task(self.on_transcript(payload))
                                    )
                                else:
                                    # Try to get running loop in current thread (fallback)
                                    try:
                                        loop = asyncio.get_running_loop()
                                        loop.create_task(self.on_transcript(payload))
                                        logger.debug("[Deepgram] Scheduled callback on running loop in current thread")
                                    except RuntimeError:
                                        logger.error("[Deepgram] No running event loop available for async callback")
                                        # Last resort: try to call sync if possible
                                        if hasattr(self.on_transcript, '__call__'):
                                            logger.warning("[Deepgram] Attempting to call async callback as sync (may fail)")
                                            try:
                                                # This won't work for async, but log the attempt
                                                logger.error("[Deepgram] Cannot call async callback without event loop")
                                            except Exception as e3:
                                                logger.error(f"[Deepgram] Failed to call callback: {e3}")
                            else:
                                # Sync callback - run in executor if we have a loop, otherwise call directly
                                if self._main_loop and self._main_loop.is_running():
                                    logger.debug("[Deepgram] Scheduling sync callback on main loop via executor (thread-safe)")
                                    # Schedule on main loop via call_soon_threadsafe
                                    self._main_loop.call_soon_threadsafe(
                                        lambda: self._main_loop.run_in_executor(None, self.on_transcript, payload)
                                    )
                                else:
                                    # No loop available, call directly (blocking)
                                    logger.debug("[Deepgram] Calling sync callback directly (no event loop)")
                                    self.on_transcript(payload)
                        except Exception as e:
                            logger.error(f"[Deepgram] Error scheduling on_transcript callback: {e}", exc_info=True)
                            # Last resort: try direct call for sync callbacks
                            if not asyncio.iscoroutinefunction(self.on_transcript):
                                try:
                                    logger.warning("[Deepgram] Attempting direct sync callback call as fallback")
                                    self.on_transcript(payload)
                                except Exception as e2:
                                    logger.error(f"[Deepgram] Failed to call on_transcript directly: {e2}", exc_info=True)

                    except Exception as e:
                        logger.error(f"[Deepgram] Transcript parse error: {e}\n{traceback.format_exc()}")

                def handle_error(*args, **kwargs):
                    err = _safe_extract_result_from_args(args, kwargs)
                    error_msg = str(err) if err else "Unknown error"
                    # CRITICAL: Log Deepgram errors with full details for debugging timeout issues
                    logger.error(f"[DG] ✗ Live error event: {err}, timestamp={time.time():.3f}")
                    if "timeout" in error_msg.lower() or "1011" in error_msg:
                        logger.error(f"[DG] ✗✗✗ TIMEOUT ERROR DETECTED! {error_msg}")
                    # mark closed so send_audio will stop trying
                    self.is_open = False
                    # Track if this error occurred during start
                    self._start_error = True
                    # Store error message for better reporting
                    self._last_error = error_msg

                def handle_close(*args, **kwargs):
                    # Extract close reason and code if available
                    close_info = _safe_extract_result_from_args(args, kwargs)
                    close_code = getattr(close_info, 'code', None) if close_info else None
                    close_reason = getattr(close_info, 'reason', None) if close_info else None
                    close_msg = str(close_info) if close_info else "Unknown"
                    
                    # CRITICAL: Log Deepgram close with full details for debugging timeout issues
                    logger.warning(f"[DG] ✗ Live socket closed. code={close_code}, reason={close_reason or close_msg}, timestamp={time.time():.3f}")
                    if close_code == 1011 or (close_reason and "timeout" in str(close_reason).lower()):
                        logger.error(f"[DG] ✗✗✗ KEEPALIVE TIMEOUT DETECTED! code={close_code}, reason={close_reason or close_msg}")
                    self.is_open = False

                # Register handlers. `.on(event, handler)` is required by SDK v3.6+
                # Wrap handlers in lambdas to ensure correct argument extraction
                try:
                    # Use lambda to ensure we pass all args correctly
                    self.live_socket.on(LiveTranscriptionEvents.Transcript, lambda *a, **kw: handle_transcript(*a, **kw))
                    self.live_socket.on(LiveTranscriptionEvents.Error, lambda *a, **kw: handle_error(*a, **kw))
                    self.live_socket.on(LiveTranscriptionEvents.Close, lambda *a, **kw: handle_close(*a, **kw))
                except Exception as e:
                    # Some SDK versions provide callback registration differently — attempt decorator fallback
                    # But avoid raising; prefer to log and proceed (our earlier experience shows .on(...) should work)
                    logger.debug("[Deepgram] registering handlers with .on() failed, attempting decorator-style", exc_info=True)
                    try:
                        # decorator-style registration fallback (less common)
                        @self.live_socket.on_message  # type: ignore
                        def _msg(m, **kw):  # pragma: no cover - fallback
                            handle_transcript(m, kw)
                    except Exception:
                        logger.error("[Deepgram] Failed to register handlers on Deepgram Live socket", exc_info=True)
                        raise

                # Configure options (linear16, 16kHz, mono)
                # Start with minimal options to avoid HTTP 400 errors
                # If this works, we can add more parameters later
                logger.info(f"[Deepgram] Configuring LiveOptions: model={self.model}, language={self.language}, encoding=linear16, sample_rate=16000, channels=1")
                
                # Try minimal configuration first to avoid parameter-related HTTP 400 errors
                try:
                    options = LiveOptions(
                        model=self.model,
                        language=self.language,
                        encoding="linear16",
                        sample_rate=16000,
                        channels=1,
                        interim_results=True,
                        smart_format=True
                    )
                    logger.debug(f"[Deepgram] LiveOptions created with minimal config: {options}")
                except Exception as e:
                    logger.error(f"[Deepgram] ERROR creating LiveOptions: {e}")
                    # Try even more minimal config
                    logger.info(f"[Deepgram] Trying minimal LiveOptions (no smart_format)...")
                    try:
                        options = LiveOptions(
                            model=self.model,
                            language=self.language,
                            encoding="linear16",
                            sample_rate=16000,
                            channels=1,
                            interim_results=True
                        )
                        logger.debug(f"[Deepgram] LiveOptions created with minimal config (no smart_format)")
                    except Exception as e2:
                        logger.error(f"[Deepgram] ERROR creating minimal LiveOptions: {e2}")
                        # Last resort: absolute minimum
                        options = LiveOptions(
                            model=self.model,
                            language=self.language,
                            encoding="linear16",
                            sample_rate=16000,
                            channels=1
                        )
                        logger.warning(f"[Deepgram] Using absolute minimal LiveOptions")
                
                # DO NOT set utterance_end_ms or endpointing - these may cause HTTP 400
                # We'll handle keepalive via sending silence chunks instead
                logger.debug(f"[Deepgram] Final LiveOptions: model={options.model}, language={options.language}, encoding={getattr(options, 'encoding', 'N/A')}, sample_rate={getattr(options, 'sample_rate', 'N/A')}")

                # Reset error flag before starting
                self._start_error = False
                self._last_error = None
                
                # Log API key info (masked)
                api_key_preview = self.api_key[:8] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "***"
                logger.info(f"[Deepgram] About to call live_socket.start() with API key: {api_key_preview}")
                logger.info(f"[Deepgram] Options being sent: model={options.model}, language={options.language}, encoding={getattr(options, 'encoding', 'N/A')}, sample_rate={getattr(options, 'sample_rate', 'N/A')}")
                
                # start() might be sync (returns True/False) or async (coroutine)
                # Wrap in try-except to catch any exceptions from start() itself (like HTTP 400)
                try:
                    logger.debug(f"[Deepgram] Calling live_socket.start(options)...")
                    start_ret = self.live_socket.start(options)
                    logger.debug(f"[Deepgram] live_socket.start() returned: {start_ret} (type: {type(start_ret)})")
                    if asyncio.iscoroutine(start_ret):
                        logger.debug(f"[Deepgram] start() returned coroutine, awaiting...")
                        await start_ret
                        logger.debug(f"[Deepgram] start() coroutine completed")
                    else:
                        # If start_ret is False, this indicates connection was rejected
                        if start_ret is False:
                            error_msg = "Deepgram start() returned False - connection rejected by server (likely HTTP 400)"
                            logger.error(f"[Deepgram] {error_msg}")
                            logger.error(f"[Deepgram] This usually means:")
                            logger.error(f"[Deepgram]   1. Invalid API key or API key format")
                            logger.error(f"[Deepgram]   2. API key doesn't have Live API access enabled")
                            logger.error(f"[Deepgram]   3. Invalid request parameters")
                            logger.error(f"[Deepgram]   4. Account restrictions or billing issues")
                            logger.error(f"[Deepgram]   5. API key may be expired or revoked")
                            self.is_open = False
                            raise Exception(error_msg)
                        elif start_ret is not True and start_ret is not None:
                            # Some SDK versions return None on success; only treat explicit False as failure
                            logger.warning(f"[Deepgram] live_socket.start() returned {start_ret} (not True/None/False)")
                except Exception as start_exception:
                    # start() itself raised an exception (e.g., WebSocketException with HTTP 400)
                    error_type = type(start_exception).__name__
                    error_msg = str(start_exception)
                    error_repr = repr(start_exception)
                    logger.error(f"[Deepgram] start() raised exception: {error_type}: {error_msg}")
                    logger.error(f"[Deepgram] Full exception: {error_repr}")
                    logger.error(f"[Deepgram] Exception args: {start_exception.args if hasattr(start_exception, 'args') else 'N/A'}")
                    # Check for HTTP 400 specifically
                    if "400" in error_msg or "HTTP 400" in error_msg:
                        logger.error(f"[Deepgram] HTTP 400 error detected! This usually means:")
                        logger.error(f"[Deepgram]   1. Invalid API key")
                        logger.error(f"[Deepgram]   2. Invalid request parameters")
                        logger.error(f"[Deepgram]   3. API key doesn't have Live API access")
                        logger.error(f"[Deepgram]   4. Account restrictions or billing issues")
                    self.is_open = False
                    self._start_error = False
                    # Don't try to verify connection if start() already failed
                    raise Exception(f"Deepgram WebSocket connection failed during start(): {error_msg}")
                
                # If we get here, start() completed without raising an exception
                # Wait a bit longer to see if error event fires (connection might fail asynchronously)
                # HTTP 400 errors are often reported asynchronously via the error handler
                logger.debug(f"[Deepgram] Waiting for async error events (if any)...")
                await asyncio.sleep(0.5)  # Increased wait time for async errors
                
                # Check if error occurred during start (set by error handler)
                if self._start_error:
                    error_detail = self._last_error or "Unknown error"
                    logger.error(f"[Deepgram] Error event received during start: {error_detail}")
                    logger.error(f"[Deepgram] This indicates the connection was rejected by Deepgram server")
                    self.is_open = False
                    raise Exception(f"Deepgram WebSocket connection failed - error event received during start: {error_detail}")
                
                # Verify connection is actually established before marking as open
                # Only check if start() didn't raise an exception
                try:
                    # Try to check connection status, but handle AttributeError if _socket doesn't exist
                    connection_verified = False
                    try:
                        if hasattr(self.live_socket, 'is_connected'):
                            # Wrap in try-except because is_connected() might access _socket which doesn't exist if connection failed
                            try:
                                if self.live_socket.is_connected():
                                    connection_verified = True
                            except AttributeError:
                                # _socket doesn't exist, connection failed
                                connection_verified = False
                        elif hasattr(self.live_socket, '_socket'):
                            if self.live_socket._socket is not None:
                                connection_verified = True
                    except AttributeError:
                        # _socket attribute doesn't exist, connection failed
                        connection_verified = False
                    
                    if not connection_verified:
                        self.is_open = False
                        raise Exception("Deepgram WebSocket connection failed - connection not established after start()")
                except AttributeError as e:
                    # If _socket doesn't exist, connection failed
                    self.is_open = False
                    raise Exception(f"Deepgram WebSocket connection failed - socket attribute error: {e}")
                
                # If we get here, connection is verified
                self.is_open = True
                logger.info("✓ Deepgram Live WebSocket started and verified")

            except Exception as e:
                logger.error(f"[Deepgram] Error starting Live session: {e}", exc_info=True)
                self.is_open = False
                raise

    async def send_audio(self, audio_chunk: bytes) -> bool:
        """
        Send a PCM16 audio chunk (raw bytes) to Deepgram Live socket.
        Return True on success, False on failure.
        """
        if not self.is_open or self.live_socket is None:
            logger.debug("[Deepgram] send_audio called but live socket is not open")
            return False

        # Verify connection is actually established before sending
        try:
            if hasattr(self.live_socket, 'is_connected'):
                if not self.live_socket.is_connected():
                    logger.warning("[Deepgram] Socket reports not connected, marking as closed")
                    self.is_open = False
                    return False
            elif hasattr(self.live_socket, '_socket'):
                if self.live_socket._socket is None:
                    logger.warning("[Deepgram] Socket _socket is None, marking as closed")
                    self.is_open = False
                    return False
        except Exception as e:
            logger.debug(f"[Deepgram] Error checking connection status: {e}")
            # Continue anyway - might be a version difference

        try:
            # Send audio chunk (DEBUG level to reduce spam)
            chunk_size = len(audio_chunk)
            logger.debug(f"[DG] → audio {chunk_size} bytes")
            send_ret = self.live_socket.send(audio_chunk)
            if asyncio.iscoroutine(send_ret):
                await send_ret
            return True
        except Exception as e:
            logger.warning(f"[DG] ✗ Error sending audio chunk: {e}")
            self.is_open = False
            return False

    async def finish(self) -> None:
        """Finish / close the live session gracefully."""
        async with self._lock:
            # guard against repeated closes
            if not self.is_open or self.live_socket is None:
                self.is_open = False
                return

            try:
                finish_ret = self.live_socket.finish()
                if asyncio.iscoroutine(finish_ret):
                    await finish_ret
            except Exception as e:
                logger.warning(f"[Deepgram] Exception during finish(): {e}", exc_info=True)
            finally:
                self.is_open = False


class DeepgramClientWrapper:
    """
    Wrapper that manages multiple live sessions keyed by interview_id.
    Exposes:
      - start_live_session
      - send_audio_chunk
      - stop_live_session
    """

    def __init__(self):
        self._live_sessions: Dict[str, DeepgramLiveSession] = {}
        self._sessions_lock = asyncio.Lock()

    async def start_live_session(
        self,
        interview_id: str,
        on_transcript: Callable[[dict], Any],
        model: str = "nova-2",
        language: str = "en-US"
    ) -> bool:
        """
        Start or replace a live session for an interview.
        Returns True on success, False on failure.
        """
        logger.info(f"[Deepgram] Starting live session for interview {interview_id} with model={model}, language={language}")
        
        account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_STT)
        if not account:
            logger.error("[Deepgram] No STT account available in provider pool")
            return False

        # Log API key info (masked for security)
        api_key_preview = account.api_key[:8] + "..." + account.api_key[-4:] if len(account.api_key) > 12 else "***"
        logger.info(f"[Deepgram] Using API key: {api_key_preview} (length: {len(account.api_key)})")
        logger.info(f"[Deepgram] Account status: healthy={account.is_healthy}, rate_limited={account.is_rate_limited()}, last_error={account.last_error}")

        async with self._sessions_lock:
            # close existing session if present
            existing = self._live_sessions.get(interview_id)
            if existing:
                logger.info(f"[Deepgram] Closing existing session for {interview_id}")
                try:
                    await existing.finish()
                except Exception as e:
                    logger.debug(f"[Deepgram] existing session finish() raised: {e}, continuing")

            logger.info(f"[Deepgram] Creating new DeepgramLiveSession for {interview_id}")
            session = DeepgramLiveSession(
                api_key=account.api_key,
                model=model,
                language=language,
                on_transcript=on_transcript
            )

            try:
                logger.info(f"[Deepgram] Calling session.start() for {interview_id}")
                await session.start()
                self._live_sessions[interview_id] = session
                await provider_pool_manager.mark_success(account)
                logger.info(f"✓ Started Live STT for interview {interview_id}")
                return True
            except Exception as e:
                msg = str(e)
                error_type = type(e).__name__
                logger.error(f"[Deepgram] Failed to start live session for {interview_id}: {error_type}: {msg}", exc_info=True)
                logger.error(f"[Deepgram] Full exception details: {repr(e)}")
                # mark provider as error (rate limit/backoff handled by pool manager)
                await provider_pool_manager.mark_error(account, msg)
                return False

    async def send_keepalive(self, interview_id: str) -> bool:
        """
        Send explicit KeepAlive message to Deepgram Live WebSocket.
        This prevents Deepgram from timing out when there are gaps in audio.
        """
        try:
            async with self._sessions_lock:
                session = self._live_sessions.get(interview_id)
                if not session:
                    logger.debug(f"[Deepgram] send_keepalive: no active session for {interview_id}")
                    return False
                
                if not session.is_open:
                    logger.debug(f"[Deepgram] send_keepalive: session not open for {interview_id}")
                    return False
                
                # Send Deepgram KeepAlive message (JSON format)
                # Deepgram Live API expects: {"type": "KeepAlive"}
                # Note: Deepgram SDK may not support JSON KeepAlive directly, so we send silence as fallback
                # But we'll try the JSON format first if the SDK supports it
                try:
                    # Try sending as JSON string (if SDK supports it)
                    import json
                    keepalive_msg = json.dumps({"type": "KeepAlive"}).encode('utf-8')
                    logger.debug(f"[DG] → KeepAlive")
                    send_ret = session.live_socket.send(keepalive_msg)
                    if asyncio.iscoroutine(send_ret):
                        await send_ret
                    return True
                except Exception as e:
                    # If JSON format fails, fallback to silence chunk (which also works as keepalive)
                    logger.debug(f"[DG] KeepAlive JSON not supported, using silence chunk: {e}")
                    # Return False so caller can use silence chunk fallback
                    return False
        except Exception as e:
            logger.error(f"[Deepgram] Error in send_keepalive: {e}", exc_info=True)
            return False
    
    async def send_audio_chunk(self, interview_id: str, audio_chunk: bytes) -> bool:
        """
        Send PCM16 bytes to the active live session.
        Returns True if successfully queued/sent; False otherwise.
        """
        async with self._sessions_lock:
            session = self._live_sessions.get(interview_id)
            if not session:
                logger.debug(f"[Deepgram] send_audio_chunk: no active session for {interview_id}")
                return False

            # ensure chunk is bytes
            if not isinstance(audio_chunk, (bytes, bytearray)):
                logger.warning(f"[Deepgram] audio_chunk is not bytes for {interview_id} (type={type(audio_chunk)})")
                return False

            # send
            success = await session.send_audio(audio_chunk)
            if not success:
                # if send failed, attempt to close and drop session
                try:
                    await session.finish()
                except Exception:
                    pass
                if interview_id in self._live_sessions:
                    del self._live_sessions[interview_id]
            return success

    async def stop_live_session(self, interview_id: str) -> None:
        """Stop and remove the live session for the interview (if present)."""
        async with self._sessions_lock:
            session = self._live_sessions.pop(interview_id, None)
            if session:
                try:
                    await session.finish()
                except Exception:
                    logger.debug("[Deepgram] stop_live_session: finish() raised", exc_info=True)
                logger.info(f"✓ Stopped Live STT for {interview_id}")

    async def synthesize_speech(
        self,
        text: str,
        model: str = "aura-asteria-en",
        voice: str = "asteria",
        max_retries: int = 2
    ) -> Optional[bytes]:
        """
        Synthesize speech using Deepgram TTS with retry logic.
        Returns audio bytes on success, None on failure.
        """
        import time
        
        for attempt in range(max_retries + 1):
            account = await provider_pool_manager.get_account(ProviderType.DEEPGRAM_TTS)
            if not account:
                logger.error("[Deepgram] No TTS account available")
                return None

            try:
                from deepgram.clients.common.v1.options import TextSource
                from deepgram.clients.speak.v1.rest.options import SpeakRESTOptions
                import io

                client = DeepgramClient(account.api_key)
                source = TextSource(text=text)
                opts = SpeakRESTOptions(model=model)

                logger.info(f"[Deepgram] Generating TTS: text_len={len(text)}, model={model}")
                
                # stream_memory() returns a BytesIO object directly
                response = client.speak.v("1").stream_memory(source=source, options=opts)
                
                # Extract audio bytes from response
                audio = None
                
                # Method 1: If it's a BytesIO object (or has read method)
                if hasattr(response, 'read'):
                    audio = response.read()
                    if isinstance(audio, bytes) and len(audio) > 0:
                        logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via read()")
                        await provider_pool_manager.mark_success(account)
                        return audio
                
                # Method 2: If it has stream_memory as an attribute that returns BytesIO
                if hasattr(response, "stream_memory"):
                    stream_obj = response.stream_memory
                    if callable(stream_obj):
                        stream_obj = stream_obj()
                    if hasattr(stream_obj, 'read'):
                        audio = stream_obj.read()
                        if isinstance(audio, bytes) and len(audio) > 0:
                            logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via stream_memory().read()")
                            await provider_pool_manager.mark_success(account)
                            return audio
                
                # Method 3: If it has a stream() method (iterator)
                if hasattr(response, 'stream'):
                    audio = b"".join(response.stream())
                    if isinstance(audio, bytes) and len(audio) > 0:
                        logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via stream()")
                        await provider_pool_manager.mark_success(account)
                        return audio
                
                # Method 4: If it's already bytes
                if isinstance(response, bytes):
                    if len(response) > 0:
                        logger.info(f"[Deepgram] TTS success: got {len(response)} bytes directly")
                        await provider_pool_manager.mark_success(account)
                        return response
                
                # Method 5: Try to get bytes from response object
                if hasattr(response, '__bytes__'):
                    try:
                        audio = bytes(response)
                        if len(audio) > 0:
                            logger.info(f"[Deepgram] TTS success: got {len(audio)} bytes via __bytes__()")
                            await provider_pool_manager.mark_success(account)
                            return audio
                    except:
                        pass
                
                # Log what we got
                logger.error(f"[Deepgram] TTS failed: response type={type(response)}, has_read={hasattr(response, 'read')}, has_stream={hasattr(response, 'stream')}, dir={[x for x in dir(response) if not x.startswith('_')][:10]}")
                await provider_pool_manager.mark_error(account, "Empty TTS audio - unable to extract bytes")
                return None

            except Exception as e:
                msg = str(e)
                is_timeout = "timeout" in msg.lower() or "ssl" in msg.lower() or "connect" in msg.lower()
                
                if is_timeout and attempt < max_retries:
                    logger.warning(f"[Deepgram] TTS timeout (attempt {attempt + 1}/{max_retries + 1}), retrying in 1s...")
                    await provider_pool_manager.mark_error(account, msg)
                    time.sleep(1)  # Brief delay before retry
                    continue
                
                logger.error(f"[Deepgram] TTS error (attempt {attempt + 1}/{max_retries + 1}): {msg}", exc_info=True)
                await provider_pool_manager.mark_error(account, msg)
                return None
        
        return None  # All retries exhausted


# single global instance for import
deepgram_client = DeepgramClientWrapper()
