"""Helper functions for LLM calls with BYOK support."""
import logging
from typing import Optional
from shared.providers.openrouter_pool_client import get_openrouter_client, generate_with_task_model, TASK_MODELS
from shared.db.redis_client import redis_client

logger = logging.getLogger(__name__)


async def get_byok_key(interview_id: Optional[str]) -> Optional[str]:
    """Get BYOK OpenRouter key from Redis for an interview."""
    if not interview_id:
        return None
    
    try:
        byok_key = f"interview:{interview_id}:byok_openrouter"
        if redis_client.redis:
            key_value = await redis_client.get(byok_key)
            if key_value:
                # Ensure it's a string
                if isinstance(key_value, bytes):
                    key_value = key_value.decode('utf-8')
                elif not isinstance(key_value, str):
                    key_value = str(key_value)
                logger.debug(f"Retrieved BYOK key for interview {interview_id}")
                return key_value
    except Exception as e:
        logger.warning(f"Failed to get BYOK key: {e}")
    
    return None


async def generate_with_task_and_byok(
    task: str,
    prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    interview_id: Optional[str] = None
) -> Optional[str]:
    """
    Generate response using task-specific model via OpenRouter with BYOK support.
    
    Args:
        task: Task type (question_generation, answer_evaluation, etc.)
        prompt: Input prompt
        max_tokens: Maximum tokens
        temperature: Temperature
        interview_id: Optional interview ID for BYOK key retrieval
        
    Returns:
        Generated text or None on error
    """
    # Get BYOK key if interview_id provided
    byok_key = await get_byok_key(interview_id)
    
    return await generate_with_task_model(
        task=task,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        api_key=byok_key
    )

