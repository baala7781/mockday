"""OpenRouter client for LLM interactions (50 RPD free tier, 1,000 RPD with $10 credit)."""
import httpx
import logging
from typing import Optional, Dict, Any
from shared.config.settings import settings
import asyncio

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """OpenRouter client with retry logic and error handling."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: Optional API key. If provided, uses this instead of settings.
                     This allows BYOK (Bring Your Own Key) support.
        """
        # Use provided key (BYOK) or fall back to settings
        self.api_key = api_key or (settings.OPENROUTER_API_KEY or None)
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Model selection priority (from env or defaults)
        # Free tier models (shared pool, can be rate-limited):
        # Note: Some free models may not be available - system will fallback to Gemini
        self.free_models = {
            "gemini": "google/gemini-2.0-flash-exp:free",  # Known to work
            "gpt": "openai/gpt-3.5-turbo",  # Try without :free suffix first
            "claude": "anthropic/claude-3-haiku",  # Try without :free suffix
            "llama": "meta-llama/llama-3.2-3b-instruct",  # Try without :free suffix
        }
        
        # Alternative free models (if primary doesn't work)
        self.free_models_alt = {
            "gpt": "openai/gpt-3.5-turbo:free",  # Alternative format
            "claude": "anthropic/claude-3-haiku:free",  # Alternative format
            "llama": "meta-llama/llama-3.2-3b-instruct:free",  # Alternative format
        }
        
        # Paid models (better rate limits, requires credits):
        self.paid_models = {
            "gemini": "google/gemini-2.5-flash",
            "gpt": "openai/gpt-4o-mini",  # Cheaper GPT-4 variant
            "claude": "anthropic/claude-3.5-sonnet",
            "llama": "meta-llama/llama-3.1-70b-instruct",
        }
        
        # Default model preference (can be set via env: OPENROUTER_MODEL_PREFERENCE)
        # Options: "gemini", "gpt", "claude", "llama", or specific model name
        model_pref = getattr(settings, 'OPENROUTER_MODEL_PREFERENCE', 'gemini').lower()
        use_paid = getattr(settings, 'OPENROUTER_USE_PAID', 'false').lower() == 'true'
        
        # Select model based on preference
        if model_pref in self.free_models and not use_paid:
            self.default_model = self.free_models[model_pref]
        elif model_pref in self.paid_models and use_paid:
            self.default_model = self.paid_models[model_pref]
        elif model_pref.startswith(('google/', 'openai/', 'anthropic/', 'meta-llama/')):
            # Direct model name provided
            self.default_model = model_pref
        else:
            # Default fallback
            self.default_model = self.free_models.get("gemini", "google/gemini-2.0-flash-exp:free")
        
        logger.info(f"OpenRouter configured with model: {self.default_model} (preference: {model_pref}, paid: {use_paid})")
    
    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        stream: bool = False,
        try_alternatives: bool = True
    ) -> Optional[str]:
        """
        Generate response using OpenRouter API.
        
        Args:
            prompt: Input prompt
            model: Model to use (defaults to free tier model)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            stream: Whether to stream response (not fully supported yet)
            try_alternatives: If model not found (404), try alternative model names
            
        Returns:
            Generated text or None on error
        """
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            return None
        
        model = model or self.default_model
        models_to_try = [model]
        
        # If 404 error and try_alternatives, add alternative model names
        if try_alternatives:
            # Extract provider/model name
            if model in self.free_models.values():
                # Find which key this model belongs to
                for key, val in self.free_models.items():
                    if val == model and key in self.free_models_alt:
                        models_to_try.append(self.free_models_alt[key])
                        break
            elif "gpt" in model.lower() and ":free" not in model:
                models_to_try.append(model + ":free")
            elif "claude" in model.lower() and ":free" not in model:
                models_to_try.append(model + ":free")
            elif "llama" in model.lower() and ":free" not in model:
                models_to_try.append(model + ":free")
        
        for attempt_model in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "HTTP-Referer": getattr(settings, 'OPENROUTER_REFERER_URL', 'https://mockday.io'),
                            "X-Title": "MockDay AI Interview Platform"
                        },
                        json={
                            "model": attempt_model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": max_tokens,
                            "temperature": temperature
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("message", {}).get("content", "")
                        if content:
                            if attempt_model != model:
                                logger.info(f"OpenRouter: Model {model} not found, successfully used {attempt_model} instead")
                            logger.debug(f"OpenRouter response received: {len(content)} chars")
                            return content
                        else:
                            logger.warning("OpenRouter returned empty content")
                            continue  # Try next model
                    else:
                        logger.error(f"OpenRouter response missing choices: {data}")
                        continue  # Try next model
                        
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        pass
                    
                    error_msg = error_data.get("error", {}).get("message", "")
                    if "No endpoints found" in error_msg or "not found" in error_msg.lower():
                        logger.warning(f"OpenRouter model '{attempt_model}' not found: {error_msg}")
                        if attempt_model == models_to_try[-1]:
                            # Last attempt failed
                            logger.error(f"All OpenRouter model attempts failed. Last error: {error_msg}")
                            return None
                        # Try next model
                        continue
                    else:
                        logger.error(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text}")
                        return None
                elif e.response.status_code == 429:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        pass
                    
                    # Check if it's upstream rate limit (Google rate-limiting the free model)
                    error_msg = error_data.get("error", {}).get("message", "")
                    if "upstream" in error_msg.lower() or "rate-limited upstream" in str(error_data):
                        logger.warning(
                            f"OpenRouter free model rate-limited by Google upstream. "
                            f"This is expected - free models are shared. Falling back to Gemini direct API. "
                            f"To avoid this, either: 1) Use paid OpenRouter model, 2) Add your Google API key to OpenRouter (BYOK), "
                            f"or 3) Use Gemini directly (already configured as fallback)."
                        )
                    else:
                        logger.warning(f"OpenRouter rate limit exceeded: {e.response.text}")
                    return None
                elif e.response.status_code == 401:
                    logger.error("OpenRouter API key invalid or expired")
                    return None
                else:
                    logger.error(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text}")
                    return None
            except httpx.TimeoutException:
                logger.error("OpenRouter request timeout")
                if attempt_model == models_to_try[-1]:
                    return None
                continue  # Try next model
            except Exception as e:
                logger.error(f"OpenRouter API error: {e}", exc_info=True)
                if attempt_model == models_to_try[-1]:
                    return None
                continue  # Try next model
        
        return None
    
    async def generate_response_with_fallback(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        fallback_to_gemini: bool = True
    ) -> Optional[str]:
        """
        Generate response with automatic fallback to Gemini if OpenRouter fails.
        
        Args:
            prompt: Input prompt
            model: Model to use
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            fallback_to_gemini: Whether to fallback to Gemini on error
            
        Returns:
            Generated text or None on error
        """
        # Try OpenRouter first
        response = await self.generate_response(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if response:
            return response
        
        # Fallback to Gemini if enabled
        if fallback_to_gemini:
            logger.info("OpenRouter failed, falling back to Gemini")
            try:
                from shared.providers.gemini_client import gemini_client
                return await gemini_client.generate_response(
                    prompt=prompt,
                    model="gemini-2.5-flash",
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            except Exception as e:
                logger.error(f"Gemini fallback also failed: {e}")
                return None
        
        return None


# Global OpenRouter client instance
openrouter_client = OpenRouterClient()

