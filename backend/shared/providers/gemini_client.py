"""Google Gemini client for LLM interactions with OpenRouter fallback."""
import google.generativeai as genai
from shared.providers.pool_manager import provider_pool_manager, ProviderType
from typing import Optional, Dict, Any, AsyncGenerator
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# Try to import OpenRouter client (optional dependency)
try:
    from shared.providers.openrouter_client import openrouter_client
    OPENROUTER_AVAILABLE = True
except ImportError:
    OPENROUTER_AVAILABLE = False
    openrouter_client = None


class GeminiClientWrapper:
    """Gemini client wrapper with pool management."""
    
    async def generate_response(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash-lite",
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_openrouter_first: bool = True,
        interview_id: Optional[str] = None  # Optional: If provided, will check for BYOK key
    ) -> Optional[str]:
        """
        Generate response using OpenRouter (primary) or Gemini (fallback).
        
        Args:
            prompt: Input prompt
            model: Model to use (gemini-2.5-flash-lite, gemini-2.5-flash-lite, gemini-2.0-flash, etc.)
            stream: Whether to stream response (not fully supported yet)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate (used as max_output_tokens)
            use_openrouter_first: Try OpenRouter first (better rate limits), fallback to Gemini
            interview_id: Optional interview ID to check for BYOK OpenRouter key
            
        Returns:
            Generated text or None on error
        """
        # Check for BYOK OpenRouter key if interview_id is provided
        byok_key = None
        if interview_id:
            try:
                from shared.db.redis_client import redis_client
                redis_key = f"interview:{interview_id}:byok_openrouter"
                logger.info(f"🔍 Checking for BYOK key in Redis: {redis_key}")
                
                # Check if Redis is connected
                if not redis_client.redis:
                    logger.warning(f"⚠️ Redis not connected, cannot retrieve BYOK key")
                else:
                    byok_key = await redis_client.get(redis_key)
                    logger.info(f"🔍 Redis get() returned: {type(byok_key).__name__ if byok_key else 'None'}, value length: {len(str(byok_key)) if byok_key else 0}")
                    
                    if byok_key:
                        # Ensure it's a string (Redis might return different types)
                        if isinstance(byok_key, bytes):
                            byok_key = byok_key.decode('utf-8')
                        elif not isinstance(byok_key, str):
                            byok_key = str(byok_key)
                        logger.info(f"✅ Using BYOK OpenRouter key for interview {interview_id} (key length: {len(byok_key)}, type: {type(byok_key).__name__})")
                    else:
                        logger.info(f"ℹ️ No BYOK key found for interview {interview_id} (key: {redis_key}), using default OpenRouter key")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get BYOK key from Redis: {e}", exc_info=True)
        
        # Try OpenRouter first if available and enabled (better rate limits: 50 RPD vs 20 RPD)
        # NOTE: Free models on OpenRouter can be rate-limited by Google upstream (shared pool)
        # If you hit rate limits, the system will automatically fallback to Gemini direct API
        if use_openrouter_first and OPENROUTER_AVAILABLE:
            try:
                # Use BYOK key if available, otherwise use default client
                openrouter_to_use = None
                if byok_key:
                    # Create temporary OpenRouter client with BYOK key
                    from shared.providers.openrouter_client import OpenRouterClient
                    openrouter_to_use = OpenRouterClient(api_key=byok_key)
                    logger.info(f"✅ Created OpenRouter client with BYOK key (key length: {len(byok_key)})")
                elif openrouter_client:
                    openrouter_to_use = openrouter_client
                    logger.debug("Using default OpenRouter client (no BYOK key)")
                
                if openrouter_to_use:
                    # Map Gemini model names to OpenRouter model names
                    openrouter_model = self._map_gemini_to_openrouter_model(model)
                    logger.debug(f"Trying OpenRouter first with model: {openrouter_model}")
                    response = await openrouter_to_use.generate_response(
                        prompt=prompt,
                        model=openrouter_model,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    if response:
                        logger.debug("✓ OpenRouter response successful")
                        return response
                    else:
                        logger.debug("OpenRouter returned None (likely rate-limited), falling back to Gemini direct API")
            except Exception as e:
                logger.debug(f"OpenRouter request failed, falling back to Gemini direct API: {e}")
        
        # Fallback to Gemini Official API
        account = await provider_pool_manager.get_account(ProviderType.GEMINI)
        if not account:
            logger.error("No Gemini API account available")
            return None
        
        logger.debug(f"Using Gemini account for model {model} (fallback)")
        
        try:
            # Configure Gemini with API key
            if not account.api_key or not account.api_key.strip():
                logger.error("Gemini API key is empty or invalid")
                await provider_pool_manager.mark_error(account, "Empty API key")
                return None
            
            # Configure with REST transport (may help with API version compatibility)
            genai.configure(
                api_key=account.api_key,
                transport="rest"  # Use REST instead of gRPC for better compatibility
            )
            logger.debug(f"Initializing Gemini model: {model}")
            # GenerativeModel accepts model name without 'models/' prefix
            gemini_model = genai.GenerativeModel(model)
            
            # Create generation config using GenerationConfig
            from google.generativeai.types import GenerationConfig
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Add safety settings (guardrails) to prevent harmful content
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            if stream:
                # Streaming response
                response = gemini_model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    stream=True
                )
                # Collect all chunks
                text_parts = []
                for chunk in response:
                    if hasattr(chunk, 'text') and chunk.text:
                        text_parts.append(chunk.text)
                await provider_pool_manager.mark_success(account)
                return "".join(text_parts) if text_parts else None
            else:
                # Non-streaming response
                logger.debug(f"Calling Gemini API with prompt length: {len(prompt)}")
                response = gemini_model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                logger.debug(f"Gemini response type: {type(response)}, has text: {hasattr(response, 'text')}, has candidates: {hasattr(response, 'candidates')}")
                
                # Check for blocked content
                if hasattr(response, 'prompt_feedback'):
                    feedback = response.prompt_feedback
                    if hasattr(feedback, 'block_reason') and feedback.block_reason:
                        error_msg = f"Content blocked: {feedback.block_reason}"
                        if hasattr(feedback, 'safety_ratings'):
                            ratings = [f"{r.category}: {r.probability}" for r in feedback.safety_ratings]
                            error_msg += f" Safety ratings: {', '.join(ratings)}"
                        logger.error(error_msg)
                        await provider_pool_manager.mark_error(account, error_msg)
                        return None
                
                # Handle different response types
                text = None
                if hasattr(response, 'text') and response.text:
                    text = response.text
                    logger.debug(f"Got text from response.text: {len(text)} chars")
                elif hasattr(response, 'candidates') and response.candidates:
                    # Try to extract text from candidates
                    candidate = response.candidates[0]
                    logger.debug(f"Candidate type: {type(candidate)}, finish_reason: {getattr(candidate, 'finish_reason', 'N/A')}")
                    
                    # Check if candidate was blocked
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                        if finish_reason and finish_reason != 1:  # 1 = STOP (success)
                            error_msg = f"Generation stopped: finish_reason={finish_reason}"
                            if hasattr(candidate, 'safety_ratings'):
                                ratings = [f"{r.category}: {r.probability}" for r in candidate.safety_ratings]
                                error_msg += f" Safety ratings: {', '.join(ratings)}"
                            logger.error(error_msg)
                            await provider_pool_manager.mark_error(account, error_msg)
                            return None
                    
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        text_parts = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                text_parts.append(part.text)
                        text = "".join(text_parts) if text_parts else None
                        logger.debug(f"Got text from candidate.content.parts: {len(text) if text else 0} chars")
                    elif hasattr(candidate, 'text'):
                        text = candidate.text
                        logger.debug(f"Got text from candidate.text: {len(text)} chars")
                    else:
                        logger.warning(f"Could not extract text from candidate. Candidate attributes: {dir(candidate)}")
                        text = str(response)
                else:
                    logger.warning(f"Response has no text or candidates. Response attributes: {dir(response)}")
                    text = str(response) if response else None
                
                if not text:
                    error_msg = "Empty response from Gemini API"
                    logger.error(f"{error_msg}. Response object: {response}")
                    await provider_pool_manager.mark_error(account, error_msg)
                    return None
                
                logger.debug(f"Successfully got response from Gemini: {len(text)} chars")
                
                await provider_pool_manager.mark_success(account)
                return text
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API error: {error_msg}", exc_info=True)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                await provider_pool_manager.mark_error(account, error_msg, 60)
            else:
                await provider_pool_manager.mark_error(account, error_msg)
            return None
    
    def _serialize_profile(self, profile: Dict[str, Any]) -> str:
        """Serialize user profile, converting Firestore DatetimeWithNanoseconds to strings."""
        import json
        from datetime import datetime
        
        def convert_dates(obj):
            """Recursively convert datetime objects to ISO format strings."""
            if isinstance(obj, dict):
                return {k: convert_dates(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_dates(item) for item in obj]
            elif hasattr(obj, 'isoformat'):  # datetime or DatetimeWithNanoseconds
                return obj.isoformat()
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                return str(obj)  # Fallback: convert to string
        
        cleaned_profile = convert_dates(profile)
        return json.dumps(cleaned_profile, indent=2)
    
    def _map_gemini_to_openrouter_model(self, gemini_model: str) -> str:
        """
        Map Gemini model names to OpenRouter model names.
        Uses the configured OpenRouter model preference (can be Gemini, GPT, Claude, etc.)
        
        Args:
            gemini_model: Gemini model name (e.g., "gemini-2.5-flash-lite")
            
        Returns:
            OpenRouter model name (e.g., "google/gemini-2.0-flash-exp:free" or "openai/gpt-3.5-turbo:free")
        """
        # Check if OpenRouter has a preferred model configured
        if OPENROUTER_AVAILABLE and openrouter_client:
            # Use OpenRouter's default model (which respects OPENROUTER_MODEL_PREFERENCE env var)
            return openrouter_client.default_model
        
        # Fallback: Map Gemini models to OpenRouter Gemini equivalents
        model_mapping = {
            "gemini-2.5-flash-lite": "google/gemini-2.0-flash-exp:free",
            "gemini-2.5-flash": "google/gemini-2.5-flash",
            "gemini-2.0-flash": "google/gemini-2.0-flash-exp:free",
            "gemini-1.5-flash": "google/gemini-1.5-flash",
        }
        
        # Return mapped model or default to free tier Gemini
        return model_mapping.get(gemini_model, "google/gemini-2.0-flash-exp:free")

    async def generate_report(
        self,
        interview_transcript: str,
        questions: list,
        answers: list,
        role: str,
        user_profile: Optional[Dict[str, Any]] = None,
        is_complete: bool = True,
        expected_questions: int = 10,
        actual_questions: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive interview report using Gemini.
        
        Args:
            interview_transcript: Full interview transcript
            questions: List of questions asked
            answers: List of answers provided
            role: Role being interviewed for
            user_profile: User profile information
            is_complete: Whether the interview was completed
            expected_questions: Number of questions expected in full interview
            actual_questions: Number of questions actually answered
            
        Returns:
            Report dict with score, feedback, analysis, etc.
        """
        completion_percentage = (actual_questions / expected_questions * 100) if expected_questions > 0 else 0
        completion_note = ""
        if not is_complete or completion_percentage < 80:
            completion_note = f"""
⚠️ CRITICAL: This is an INCOMPLETE interview ({actual_questions}/{expected_questions} questions = {completion_percentage:.0f}% complete).

**STRICT RULES FOR INCOMPLETE INTERVIEWS:**
1. ONLY assess skills that were ACTUALLY evaluated in the questions/answers provided
2. DO NOT create section_scores for skills that were NOT assessed (e.g., if only 1 question was asked, only assess that ONE skill)
3. DO NOT generate strengths/weaknesses for skills that were NOT evaluated
4. Maximum possible score should be capped based on completion:
   - <50% complete: Cap at 50-60%
   - 50-75% complete: Cap at 60-70%
   - 75-80% complete: Cap at 70-75%
5. Recommendation MUST reflect incomplete assessment (use "maybe" or "no_hire" unless exceptional)
6. Be EXPLICITLY honest: "Limited assessment due to incomplete interview"
7. Only include skills in section_scores that were actually evaluated in the transcript
"""
        
        prompt = f"""Generate a REALISTIC and HONEST interview evaluation report for a {role} position.

**SCORING GUIDELINES (STRICT):**
- 90-100: Exceptional - Almost perfect answers, deep expertise, hire immediately
- 80-89: Strong - Very good answers, clear expertise, confident hire
- 70-79: Good - Solid answers, competent, likely hire
- 60-69: Average - Basic understanding, some gaps, maybe hire with reservations  
- 50-59: Below Average - Significant gaps, weak answers, likely no hire
- 40-49: Poor - Major deficiencies, unclear answers, no hire
- 0-39: Very Poor - Did not demonstrate competency, definite no hire

**RECOMMENDATION CRITERIA:**
- "strong_hire": Score 80+ AND demonstrated clear expertise
- "hire": Score 70-79 AND no major red flags
- "maybe": Score 60-69 OR mixed performance
- "no_hire": Score below 60 OR significant concerns
{completion_note}

Interview Transcript:
{interview_transcript}

Questions Asked ({len(questions)} total):
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

Answers Provided ({len(answers)} total):
{chr(10).join(f"{i+1}. {a}" for i, a in enumerate(answers))}

User Profile:
{self._serialize_profile(user_profile) if user_profile else "Not provided"}

**BE HONEST AND CRITICAL.** Don't inflate scores. If answers were vague, short, or incorrect, score accordingly.

**CRITICAL RULES:**
1. ONLY include skills in section_scores that were ACTUALLY evaluated in the questions/answers
2. If only 1 question was asked, ONLY assess that ONE skill - do NOT create scores for communication, problem_solving, etc. unless they were explicitly evaluated
3. DO NOT generate generic strengths like "Participated in interview" - only real, demonstrated strengths
4. If interview is incomplete, be explicit: "This assessment is limited due to incomplete interview"
5. Strengths and weaknesses must be SPECIFIC to what was actually said/demonstrated

Generate a detailed report in JSON format with:
- overall_score: integer (0-100) - BE REALISTIC based on actual performance, cap appropriately for incomplete interviews
- section_scores: object with scores ONLY for areas that were actually evaluated (e.g., if only "Introduction" was asked, only include that skill, NOT communication/problem_solving)
- strengths: list of strings (ONLY if genuinely demonstrated in the actual answers - NO generic statements)
- weaknesses: list of strings (be specific about gaps, or "Limited assessment due to incomplete interview" if incomplete)
- detailed_feedback: string (comprehensive, honest feedback - mention if incomplete)
- recommendation: string (strong_hire, hire, maybe, no_hire) - reflect incomplete status if applicable
- improvement_suggestions: list of strings (actionable suggestions, include "Complete full interview for accurate assessment" if incomplete)

Response (JSON only):"""
        
        response = await self.generate_response(
            prompt=prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=2000,
            temperature=0.3
        )
        
        if response:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    report = json.loads(response[json_start:json_end])
                    return report
                except json.JSONDecodeError:
                    pass
        
        return None


# Global Gemini client instance
gemini_client = GeminiClientWrapper()

