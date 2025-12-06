"""WebSocket handler for real-time interview communication with STT/TTS."""
import asyncio
import base64
import logging
import time
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

from shared.providers.deepgram_client import deepgram_client
from shared.providers.gemini_client import gemini_client
from interview_service.models import Answer, InterviewPhase, InterviewFlowState, InterviewStatus
from interview_service.interview_state import load_interview_state
from interview_service.answer_evaluator import evaluate_answer
from interview_service.phased_flow import select_next_question_phased, update_phase_question_count
from interview_service.interview_state import save_interview_state, save_interview_state_to_firestore

logger = logging.getLogger(__name__)


class InterviewWebSocketHandler:
    """Handles WebSocket communication for interview sessions."""
    
    def __init__(self, connection_manager):
        """Initialize WebSocket handler."""
        self.connection_manager = connection_manager
        # Store audio buffers for each interview (for accumulating chunks)
        self.audio_buffers: Dict[str, list] = {}
        # Store transcript accumulators for each interview (rolling buffer)
        self.transcript_accumulators: Dict[str, str] = {}  # interview_id -> accumulated transcript
        # Store last speech end time for silence detection
        self.last_speech_times: Dict[str, float] = {}  # interview_id -> timestamp
        # Track if Live session is active for each interview
        self._live_session_active: Dict[str, bool] = {}  # interview_id -> bool
        # Track if WebSocket connection is active for each interview
        self._websocket_active: Dict[str, bool] = {}  # interview_id -> bool
        # Track last audio chunk time for keepalive
        self._last_audio_time: Dict[str, float] = {}  # interview_id -> timestamp
        # Keepalive tasks
        self._keepalive_tasks: Dict[str, asyncio.Task] = {}  # interview_id -> task
    
    def _create_transcript_callback(self, interview_id: str):
        """Create transcript callback for Deepgram Live session."""
        async def on_transcript(transcript_data: dict):
            """Handle transcript from Deepgram Live API."""
            # Check if WebSocket is still connected before processing transcript
            if not self._websocket_active.get(interview_id, False):
                logger.debug(f"[Transcript Callback] WebSocket not active for {interview_id}, skipping transcript")
                return
            try:
                logger.debug(f"[Transcript Callback] Called for {interview_id}: {transcript_data}")
                transcript_text = transcript_data.get("text", "").strip()
                is_final = transcript_data.get("is_final", False)
                confidence = transcript_data.get("confidence", 1.0)
                
                if not transcript_text:
                    logger.debug(f"[Transcript Callback] Empty transcript for {interview_id}, ignoring")
                    return
                
                # Log transcripts at DEBUG level (only log final transcripts at INFO)
                if is_final:
                    logger.info(f"✓ Transcript (final): '{transcript_text[:50]}...' (conf: {confidence:.2f})")
                else:
                    logger.debug(f"[Transcript] interim: '{transcript_text[:30]}...'")
                
                # Accumulate transcript (interim and final)
                if interview_id not in self.transcript_accumulators:
                    self.transcript_accumulators[interview_id] = ""
                    logger.debug(f"[Transcript Callback] Initialized accumulator for {interview_id}")
                
                # For interim results, replace the last interim part
                # For final results, append to accumulated transcript
                current_accumulated = self.transcript_accumulators[interview_id]
                logger.debug(f"[Transcript Callback] Before accumulation: '{current_accumulated}' (length: {len(current_accumulated)})")
                
                if is_final:
                    # Final transcript - append it
                    # Remove any trailing "..." from interim markers first
                    if current_accumulated.endswith("..."):
                        current_accumulated = current_accumulated.rstrip(". ")
                    
                    if current_accumulated:
                        # Remove interim version if it exists at the end
                        # Check if the final transcript contains more content than what's accumulated
                        # Simple approach: if accumulated ends with partial match, replace it
                        accumulated_lower = current_accumulated.lower().rstrip()
                        transcript_lower = transcript_text.lower().strip()
                        
                        # If accumulated is a substring of final, replace it with final
                        if accumulated_lower in transcript_lower:
                            self.transcript_accumulators[interview_id] = transcript_text
                            logger.debug(f"[Transcript Callback] Replaced accumulated with final: '{transcript_text}'")
                        # If final is not in accumulated, append it
                        elif transcript_lower not in accumulated_lower:
                            self.transcript_accumulators[interview_id] = current_accumulated + " " + transcript_text
                            logger.debug(f"[Transcript Callback] Appended final: '{current_accumulated}' + ' {transcript_text}'")
                        else:
                            # Already contains it, keep as is
                            logger.debug(f"[Transcript Callback] Final transcript already in accumulated, keeping as is")
                    else:
                        self.transcript_accumulators[interview_id] = transcript_text
                        logger.debug(f"[Transcript Callback] Set initial final transcript: '{transcript_text}'")
                    
                    # Update last speech time for final transcripts
                    self.last_speech_times[interview_id] = time.time()
                else:
                    # Interim transcript - store it, will be replaced by final
                    # Remove previous interim if exists (anything ending with "...")
                    if current_accumulated.endswith("..."):
                        # Remove the last interim part
                        parts = current_accumulated.rsplit("...", 1)
                        current_accumulated = parts[0].rstrip() if parts[0] else ""
                    
                    # Append new interim with marker
                    if current_accumulated:
                        self.transcript_accumulators[interview_id] = current_accumulated + " " + transcript_text + "..."
                    else:
                        self.transcript_accumulators[interview_id] = transcript_text + "..."
                    logger.debug(f"[Transcript Callback] Added interim: '{self.transcript_accumulators[interview_id]}'")
                
                # Log transcript accumulation at DEBUG level to reduce spam
                logger.debug(f"[Transcript] Accumulated: '{self.transcript_accumulators[interview_id][:50]}...' (len: {len(self.transcript_accumulators[interview_id])})")
                
                # Send transcript to frontend via WebSocket
                # Frontend expects: { type: "transcript", text: "...", is_final: bool }
                # CRITICAL: Wrap in try-except to prevent transcript callback from crashing the entire flow
                try:
                    await self.connection_manager.send_message(interview_id, {
                        "type": "transcript",
                        "text": transcript_text,  # Send current transcript (interim or final)
                        "is_final": is_final,
                        "accumulated": self.transcript_accumulators[interview_id]  # Keep for reference
                    })
                except Exception as send_err:
                    # CRITICAL: Don't let send_message errors crash the transcript callback
                    # Log the error but continue - transcript callback should never break the interview flow
                    logger.error(f"[Transcript Callback] Error sending transcript message for {interview_id}: {send_err}", exc_info=True)
                    # Don't re-raise - just log and continue
                
            except Exception as e:
                # CRITICAL: Catch all exceptions in transcript callback to prevent crashes
                logger.error(f"[Transcript Callback] Error in transcript callback for {interview_id}: {e}", exc_info=True)
                # Don't re-raise - transcript callback errors should not crash the interview
        
        return on_transcript
    
    async def handle_audio_chunk(
        self,
        interview_id: str,
        audio_data: dict
    ) -> Optional[dict]:
        """
        Handle incoming audio chunk for real-time STT using Deepgram Live API.
        
        Args:
            interview_id: Interview ID
            audio_data: Audio data dictionary with chunk, sample_rate, channels
            
        Returns:
            None (transcripts are sent via WebSocket callback)
        """
        try:
            # Load interview state to check if interview is completed
            state = await load_interview_state(interview_id)
            
            # CRITICAL: If interview is completed, ignore all audio chunks to prevent reconnecting Deepgram
            if state:
                # Check if interview is completed by status or flow_state
                if (state.status == InterviewStatus.COMPLETED or 
                    state.flow_state == InterviewFlowState.INTERVIEW_COMPLETE):
                    logger.debug(f"⚠️ Interview {interview_id} is completed, ignoring audio chunk")
                    # Ensure Deepgram session is stopped
                    if self._live_session_active.get(interview_id, False):
                        self._live_session_active[interview_id] = False
                        try:
                            await self.stop_live_session(interview_id)
                        except Exception as e:
                            logger.debug(f"Error stopping session for completed interview: {e}")
                    return None
            
            # For manual recording, we always process audio chunks
            # Flow state check is not strict - allow processing if state exists
            if state and state.flow_state != InterviewFlowState.USER_SPEAKING:
                # Log but don't block - manual recording should work
                logger.debug(f"Audio chunk received with flow state {state.flow_state} (expected USER_SPEAKING) - processing anyway for manual recording")
                # Update flow state to USER_SPEAKING when audio arrives (manual recording started)
                state.flow_state = InterviewFlowState.USER_SPEAKING
                await save_interview_state(state)
            
            chunk_base64 = audio_data.get("chunk", "")
            sample_rate = audio_data.get("sample_rate", 16000)
            channels = audio_data.get("channels", 1)
            
            if not chunk_base64:
                return None
            
            # Decode base64 audio chunk
            try:
                audio_bytes = base64.b64decode(chunk_base64)
            except Exception as e:
                logger.error(f"Error decoding audio chunk: {e}")
                return None
            
            # CRITICAL: Check if WebSocket connection is still active before processing audio
            # Check both flags to ensure we don't process chunks after disconnection
            if not self._websocket_active.get(interview_id, False) or interview_id not in self.connection_manager.active_connections:
                logger.warning(f"⚠️ WebSocket connection not active for {interview_id}, ignoring audio chunk")
                # Mark session as inactive and stop Deepgram immediately
                self._live_session_active[interview_id] = False
                self._websocket_active[interview_id] = False
                # Stop Deepgram session to prevent timeout
                try:
                    await self.stop_live_session(interview_id)
                except Exception as e:
                    logger.debug(f"Error stopping session after disconnect: {e}")
                return None
            
            # Mark WebSocket as active
            self._websocket_active[interview_id] = True
            
            # Start Deepgram Live session if not already started
            if not self._live_session_active.get(interview_id, False):
                logger.info(f"🎤 Starting Deepgram Live session for {interview_id}")
                callback = self._create_transcript_callback(interview_id)
                logger.info(f"✓ Created transcript callback for {interview_id}")
                success = await deepgram_client.start_live_session(
                    interview_id=interview_id,
                    on_transcript=callback,
                    model="nova-2",
                    language="en-US"
                )
                
                if not success:
                    logger.error(f"❌ Failed to start Deepgram Live session for {interview_id}")
                    self._live_session_active[interview_id] = False
                    # No fallback - return None and let the caller handle it
                    # The frontend should show an error message to the user
                    logger.error("Deepgram Live session failed - no fallback available. User should retry or check API key.")
                    return None
                
                self._live_session_active[interview_id] = True
                logger.info(f"✓ Deepgram Live session started successfully for {interview_id}")
                # Initialize transcript accumulator
                if interview_id not in self.transcript_accumulators:
                    self.transcript_accumulators[interview_id] = ""
                    logger.debug(f"✓ Initialized transcript accumulator for {interview_id}")
                
                # Start keepalive now that Deepgram session is active
                # This ensures keepalive only runs during active recording
                self._start_keepalive(interview_id)
            
            # Double-check session is still active before sending
            # Check both flags to ensure we don't send after disconnection
            if not self._live_session_active.get(interview_id, False) or not self._websocket_active.get(interview_id, False):
                logger.warning(f"⚠️ Session or WebSocket not active for {interview_id}, skipping audio chunk")
                # If WebSocket is disconnected, stop Deepgram session immediately
                if not self._websocket_active.get(interview_id, False):
                    try:
                        await self.stop_live_session(interview_id)
                    except Exception as e:
                        logger.debug(f"Error stopping session: {e}")
                return None
            
            # Log audio chunk reception (DEBUG level to reduce spam)
            logger.debug(f"[DG] ← Received audio chunk from frontend for {interview_id}: {len(audio_bytes)} bytes")
            
            # Send audio chunk to Deepgram Live API
            # CRITICAL: Wrap in try-except to catch any exceptions that might stop the forwarding loop
            try:
                logger.debug(f"[DG] → Sending audio chunk to Deepgram for {interview_id}: {len(audio_bytes)} bytes")
                success = await deepgram_client.send_audio_chunk(
                    interview_id=interview_id,
                    audio_chunk=audio_bytes
                )
                
                if not success:
                    logger.warning(f"[DG] ✗ Failed to send audio chunk to Deepgram for {interview_id} - session may be closed")
                    self._live_session_active[interview_id] = False
                    # Stop the session to prevent further attempts
                    try:
                        await self.stop_live_session(interview_id)
                    except Exception as e:
                        logger.debug(f"[DG] Error stopping session after send failure: {e}")
                    return None
                
                logger.debug(f"[DG] ✓ Audio chunk sent to Deepgram for {interview_id}")
                
                # Update last audio time for keepalive
                self._last_audio_time[interview_id] = time.time()
            except Exception as send_exception:
                # CRITICAL: Log any exception during send - this might be silently killing the loop
                logger.error(f"[DG] ✗✗✗ EXCEPTION during audio send for {interview_id}: {send_exception}", exc_info=True)
                logger.error(f"[DG] This exception may have stopped audio forwarding! Check stack trace above.")
                # Don't mark as inactive immediately - might be transient
                # But log it so we can see if this is the cause
                raise  # Re-raise to be caught by outer try-except
            
            # Return None - transcripts come via callback
            return None
            
        except Exception as e:
            logger.error(f"Error handling audio chunk for {interview_id}: {e}", exc_info=True)
            return None
    
    async def stop_live_session(self, interview_id: str):
        """Stop Deepgram Live session for an interview."""
        try:
            if self._live_session_active.get(interview_id, False):
                await deepgram_client.stop_live_session(interview_id)
                self._live_session_active[interview_id] = False
                logger.info(f"✓ Stopped Deepgram Live session for {interview_id}")
        except Exception as e:
            logger.error(f"Error stopping Live session for {interview_id}: {e}", exc_info=True)
        finally:
            # Always mark as inactive and stop keepalive
            self._live_session_active[interview_id] = False
            self._stop_keepalive(interview_id)
    
    def mark_websocket_connected(self, interview_id: str):
        """Mark WebSocket as connected. Keepalive will start when Deepgram session starts."""
        self._websocket_active[interview_id] = True
        self._last_audio_time[interview_id] = time.time()
        logger.debug(f"✓ WebSocket marked as connected for {interview_id}")
        # NOTE: Keepalive will start automatically when Deepgram Live session starts (in handle_audio_chunk)
    
    def mark_websocket_disconnected(self, interview_id: str):
        """Mark WebSocket as disconnected and stop Deepgram session immediately."""
        logger.info(f"🔌 Marking WebSocket as disconnected for {interview_id}")
        
        # Mark as inactive FIRST to prevent any further audio processing
        self._websocket_active[interview_id] = False
        self._live_session_active[interview_id] = False
        
        # Stop keepalive task immediately
        self._stop_keepalive(interview_id)
        
        # Stop Deepgram session immediately to prevent timeout errors
        # Use get_event_loop() to safely create task from sync method
        try:
            loop = asyncio.get_running_loop()
            # Event loop is running, create task
            # Use create_task to ensure it runs asynchronously
            task = loop.create_task(self.stop_live_session(interview_id))
            # Don't await, but log that we're stopping
            logger.debug(f"✓ Scheduled Deepgram session stop for {interview_id}")
        except RuntimeError:
            # No event loop running, schedule it for later
            # This should rarely happen, but if it does, we'll just log
            logger.warning(f"No running event loop when marking {interview_id} as disconnected")
            # Don't try to stop session if no event loop - it will be cleaned up later
    
    def get_accumulated_transcript(self, interview_id: str) -> str:
        """Get accumulated transcript for an interview."""
        return self.transcript_accumulators.get(interview_id, "")
    
    def clear_accumulated_transcript(self, interview_id: str):
        """Clear accumulated transcript for an interview."""
        if interview_id in self.transcript_accumulators:
            del self.transcript_accumulators[interview_id]
        if interview_id in self.last_speech_times:
            del self.last_speech_times[interview_id]
    
    def check_silence_detected(self, interview_id: str, silence_duration: float = 1.5) -> bool:
        """
        Check if silence has been detected (no speech for silence_duration seconds).
        
        Args:
            interview_id: Interview ID
            silence_duration: Duration in seconds to consider as silence (default 1.5s)
            
        Returns:
            True if silence detected, False otherwise
        """
        if interview_id not in self.last_speech_times:
            return False
        
        elapsed = time.time() - self.last_speech_times[interview_id]
        return elapsed >= silence_duration
    
    def _start_keepalive(self, interview_id: str):
        """Start keepalive task to send silence chunks only during active recording to prevent Deepgram timeout."""
        # Cancel existing keepalive if any
        self._stop_keepalive(interview_id)
        
        async def keepalive_loop():
            """
            Send KeepAlive messages to Deepgram every 2 seconds to prevent timeout.
            Deepgram requires continuous messages (audio or KeepAlive) with <3 second gaps.
            This keeps Deepgram connection alive during long pauses (user thinking, muted, etc.)
            """
            loop_iteration = 0
            try:
                logger.info(f"[DG Keepalive] ✓ Keepalive loop STARTED for {interview_id}")
                while self._websocket_active.get(interview_id, False) and self._live_session_active.get(interview_id, False):
                    loop_iteration += 1
                    # CRITICAL: Log heartbeat every 10 iterations (20 seconds) to verify loop is running
                    if loop_iteration % 10 == 0:
                        logger.info(f"[DG Keepalive] 💓 Heartbeat: Loop iteration {loop_iteration} for {interview_id} (loop is alive)")
                    
                    # Check every 2 seconds to ensure we never exceed Deepgram's 3-second timeout
                    await asyncio.sleep(2)
                    
                    # Double-check connection is still active
                    if not self._websocket_active.get(interview_id, False):
                        logger.warning(f"[DG Keepalive] WebSocket no longer active for {interview_id}, exiting loop")
                        break
                    if not self._live_session_active.get(interview_id, False):
                        logger.warning(f"[DG Keepalive] Deepgram session no longer active for {interview_id}, exiting loop")
                        break
                    
                    # Check if audio was sent recently
                    last_audio = self._last_audio_time.get(interview_id, 0)
                    elapsed = time.time() - last_audio
                    
                    # CRITICAL: Deepgram requires messages every 2-3 seconds to prevent timeout
                    # Send keepalive if no audio sent in last 2 seconds (much more aggressive)
                    # Deepgram's timeout is strict - we must send something (audio or KeepAlive) frequently
                    if elapsed >= 2:
                        try:
                            # Try sending explicit Deepgram KeepAlive message first (preferred)
                            logger.debug(f"[DG Keepalive] Sending KeepAlive (elapsed: {elapsed:.1f}s)")
                            keepalive_sent = await deepgram_client.send_keepalive(interview_id)
                            if keepalive_sent:
                                logger.debug(f"[DG Keepalive] ✓ Sent KeepAlive (elapsed: {elapsed:.1f}s)")
                                self._last_audio_time[interview_id] = time.time()
                            else:
                                # Fallback: send silence chunk if KeepAlive not supported
                                logger.info(f"[DG Keepalive] KeepAlive JSON failed, using silence chunk fallback for {interview_id} (iteration: {loop_iteration})")
                                silence_chunk = b'\x00' * 1600  # 50ms of silence at 16kHz
                                success = await deepgram_client.send_audio_chunk(interview_id, silence_chunk)
                                if success:
                                    logger.info(f"[DG Keepalive] ✓ Sent keepalive silence chunk for {interview_id} (elapsed: {elapsed:.1f}s - fallback, iteration: {loop_iteration})")
                                    self._last_audio_time[interview_id] = time.time()
                                else:
                                    logger.error(f"[DG Keepalive] ✗✗✗ Keepalive failed for {interview_id} - session may be closed (iteration: {loop_iteration})")
                                    self._live_session_active[interview_id] = False
                                    break
                        except Exception as e:
                            logger.error(f"[DG Keepalive] ✗✗✗ Keepalive EXCEPTION for {interview_id} (iteration: {loop_iteration}): {e}", exc_info=True)
                            logger.error(f"[DG Keepalive] This exception may have stopped the keepalive loop! Check stack trace above.")
                            # If error, mark as inactive
                            self._live_session_active[interview_id] = False
                            break
            except asyncio.CancelledError:
                logger.info(f"[DG Keepalive] Keepalive task CANCELLED for {interview_id} (was at iteration {loop_iteration})")
            except Exception as e:
                logger.error(f"[DG Keepalive] ✗✗✗ Keepalive loop CRASHED for {interview_id} (was at iteration {loop_iteration}): {e}", exc_info=True)
                logger.error(f"[DG Keepalive] This crash stopped the keepalive loop! This is likely the root cause of Deepgram timeout.")
        
        # Start keepalive task
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(keepalive_loop())
            self._keepalive_tasks[interview_id] = task
            logger.debug(f"✓ Started keepalive task for {interview_id}")
        except RuntimeError:
            logger.warning(f"No running event loop to start keepalive for {interview_id}")
    
    def _stop_keepalive(self, interview_id: str):
        """Stop keepalive task for an interview."""
        task = self._keepalive_tasks.pop(interview_id, None)
        if task:
            task.cancel()
            logger.debug(f"✓ Stopped keepalive task for {interview_id}")
    
    async def handle_answer_submission(
        self,
        interview_id: str,
        answer_data: dict
    ) -> Optional[dict]:
        """
        Handle answer submission via WebSocket.
        
        Args:
            interview_id: Interview ID
            answer_data: Answer data dictionary
            
        Returns:
            Response dictionary with evaluation and next question
        """
        try:
            # Load interview state
            state = await load_interview_state(interview_id)
            if not state or not state.current_question:
                return {
                    "type": "error",
                    "message": "Interview not found or no current question"
                }
            
            # Get accumulated transcript if answer is empty or use provided answer
            answer_text = answer_data.get("answer", "")
            code = answer_data.get("code", "")
            language = answer_data.get("language", "")
            
            # For coding questions, code is the primary answer
            if code and len(code.strip()) > 0:
                # Code submission - use code as answer
                logger.info(f"📝 [Code Submission] Detected code submission for {interview_id}")
                # If no text answer, use placeholder
                if not answer_text or len(answer_text.strip()) < 10:
                    answer_text = f"[Code submission in {language}]"
            else:
                # Text answer - check length
                if not answer_text or len(answer_text.strip()) < 10:
                    # Use accumulated transcript if answer is empty or too short
                    answer_text = self.get_accumulated_transcript(interview_id)
                    if not answer_text or len(answer_text.strip()) < 10:
                        return {
                            "type": "error",
                            "message": "Answer is too short or empty. Please provide a meaningful answer."
                        }
            
            # Log the answer text that will be sent to LLM for evaluation
            logger.info(f"📝 [Answer Submission] Submitting answer for evaluation:")
            logger.info(f"   Interview ID: {interview_id}")
            logger.info(f"   Answer length: {len(answer_text)} chars")
            logger.info(f"   Code length: {len(code)} chars" if code else "   No code")
            logger.info(f"   Answer text: {answer_text[:300]}..." if len(answer_text) > 300 else f"   Answer text: {answer_text}")
            if code:
                logger.info(f"   Code preview: {code[:200]}..." if len(code) > 200 else f"   Code: {code}")
            
            # Update flow state to AI_THINKING
            state.flow_state = InterviewFlowState.AI_THINKING
            await save_interview_state(state)
            
            # Clear accumulated transcript (already used)
            self.clear_accumulated_transcript(interview_id)
            
            # Create Answer object
            answer = Answer(
                answer=answer_text,
                code=code if code else None,
                language=language if language else None
            )
            
            # Build conversation context (sliding window - last N QA pairs)
            context_qa_pairs = state.conversation_history[-state.max_context_pairs:] if state.conversation_history else []
            
            # Parallel execution: Evaluate answer AND generate next question concurrently
            # Task 1: Evaluate answer
            evaluation_task = evaluate_answer(
                question=state.current_question,
                answer=answer,
                previous_evaluations=[
                    e.model_dump() for eval_list in state.answered_skills.values()
                    for e in eval_list
                ],
                state=state
            )
            
            # Task 2: Generate next question (pre-generate while evaluating)
            next_question_task = select_next_question_phased(state)
            
            # Run both tasks in parallel
            evaluation, next_question = await asyncio.gather(
                evaluation_task,
                next_question_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(evaluation, Exception):
                logger.error(f"Error evaluating answer: {evaluation}")
                return {
                    "type": "error",
                    "message": f"Error evaluating answer: {str(evaluation)}"
                }
            
            if isinstance(next_question, Exception):
                logger.error(f"Error generating next question: {next_question}")
                next_question = None
            
            # Update state
            if state.current_project:
                # Project-phase answer
                if state.current_project not in state.answered_projects:
                    state.answered_projects[state.current_project] = []
                state.answered_projects[state.current_project].append(evaluation)
            
            if state.current_question.skill:
                if state.current_question.skill not in state.answered_skills:
                    state.answered_skills[state.current_question.skill] = []
                state.answered_skills[state.current_question.skill].append(evaluation)
            
            # Update phase and difficulty
            update_phase_question_count(state)
            state.current_difficulty = evaluation.next_difficulty
            state.total_questions += 1
            state.questions_asked.append(state.current_question)
            
            # Add to conversation history (sliding window)
            qa_pair = {
                "question": state.current_question.question,
                "question_id": state.current_question.question_id,
                "skill": state.current_question.skill,
                "answer": answer_text,
                "evaluation": evaluation.model_dump()
            }
            state.conversation_history.append(qa_pair)
            # Keep only last N pairs
            if len(state.conversation_history) > state.max_context_pairs:
                state.conversation_history = state.conversation_history[-state.max_context_pairs:]
            
            # Check if interview is complete (time-based: 30 minutes)
            time_limit_reached = False
            if state.started_at:
                from datetime import datetime
                elapsed = (datetime.utcnow() - state.started_at).total_seconds() / 60  # minutes
                time_limit_reached = elapsed >= state.interview_duration_minutes
            
            if time_limit_reached or not next_question:
                from interview_service.interview_state import complete_interview
                state.flow_state = InterviewFlowState.INTERVIEW_COMPLETE
                await complete_interview(interview_id)
                
                # Generate report asynchronously
                from interview_service.report_generator import generate_interview_report
                from shared.db.firestore_client import firestore_client
                profile_data = await firestore_client.get_document("users", state.user_id)
                # Create task for background report generation (don't await)
                # We're in an async context, so we can safely use create_task
                asyncio.create_task(generate_interview_report(interview_id, state, profile_data))
                await save_interview_state(state)
                return {
                    "type": "completed",
                    "evaluation": evaluation.model_dump(),
                    "message": "Interview completed"
                }
            
            # Set next question
            state.current_question = next_question
            state.current_skill = next_question.skill
            # Set/clear current_project based on phase
            if state.current_phase == InterviewPhase.PROJECTS and next_question.context and next_question.context.get("project"):
                state.current_project = next_question.context.get("project")
            elif state.current_phase != InterviewPhase.PROJECTS:
                state.current_project = None
            
            # Update flow state to AI_SPEAKING (will send TTS soon)
            state.flow_state = InterviewFlowState.AI_SPEAKING
            
            # Save updated state
            await save_interview_state(state)
            await save_interview_state_to_firestore(state)
            
            # NOTE: TTS generation is handled by main.py after receiving this response
            # It properly uses tts_text for coding questions instead of full question
            
            return {
                "type": "answer_response",
                "evaluation": evaluation.model_dump(),
                "next_question": next_question.model_dump() if next_question else None,
                "flow_state": state.flow_state.value,  # Send flow state to frontend
                "completed": False
            }
            
        except Exception as e:
            logger.error(f"Error handling answer submission: {e}")
            return {
                "type": "error",
                "message": str(e)
            }
    
    async def generate_question_audio(self, question_text: str) -> Optional[str]:
        """
        Generate TTS audio for a question.
        
        Args:
            question_text: Question text to synthesize
            
        Returns:
            Base64 encoded audio or None
        """
        try:
            audio_bytes = await deepgram_client.synthesize_speech(
                text=question_text,
                model="aura-asteria-en",
                voice="asteria"
            )
            
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode('utf-8')
            return None
            
        except Exception as e:
            logger.error(f"Error generating question audio: {e}")
            return None

