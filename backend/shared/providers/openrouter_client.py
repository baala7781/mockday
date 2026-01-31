"""OpenRouter client for LLM interactions with pool management support."""
import httpx
import logging
from typing import Optional, Dict, Any
from shared.config.settings import settings
import asyncio

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """OpenRouter client with retry logic and error handling."""
    
    def __init__(self, api_key: Optional[str] = None, use_pool: bool = False):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: Optional API key. If provided, uses this instead of pool/settings.
                     This allows BYOK (Bring Your Own Key) support.
            use_pool: If True, use pool manager for key selection (for multiple keys)
        """
        # Use provided key (BYOK) or use pool/fall back to settings
        self.api_key = api_key  # Will be set per-request if using pool
        self.use_pool = use_pool and not api_key  # Only use pool if no explicit key provided
        self.base_url = "https://openrouter.ai/api/v1"
    
    async def _get_api_key(self) -> Optional[str]:
        """Get API key from pool or use instance key."""
        if self.api_key:
            return self.api_key
        
        if self.use_pool:
            try:
                from shared.providers.pool_manager import provider_pool_manager, ProviderType
                account = await provider_pool_manager.get_account(ProviderType.OPENROUTER, strategy="round_robin")
                if account:
                    return account.api_key
            except Exception as e:
                logger.warning(f"Failed to get key from pool: {e}")
        
        # Fallback to settings
        if settings.OPENROUTER_API_KEY:
            return settings.OPENROUTER_API_KEY
        
        # Try first key from OPENROUTER_API_KEYS if available
        if settings.OPENROUTER_API_KEYS:
            keys = [k.strip() for k in settings.OPENROUTER_API_KEYS.split(",") if k.strip()]
            if keys:
                return keys[0]
        
        return None
    
    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Optional[str]:
        """
        Generate response using OpenRouter API.
        
        Args:
            prompt: Input prompt
            model: Model to use (defaults to free tier model)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            stream: Whether to stream response (not fully supported yet)
            
        Returns:
            Generated text or None on error
        """
        api_key = await self._get_api_key()
        if not api_key:
            logger.error("OpenRouter API key not configured")
            return None
        
        if not model:
            logger.error("Model must be specified")
            return None
        
        models_to_try = [model]
        
        for attempt_model in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
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

