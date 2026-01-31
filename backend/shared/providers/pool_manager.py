"""Provider pool manager for load balancing multiple API keys."""
from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
from shared.config.settings import settings
import time


class ProviderType(Enum):
    """Provider types."""
    DEEPGRAM_STT = "deepgram_stt"
    DEEPGRAM_TTS = "deepgram_tts"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass
class ProviderAccount:
    """Provider account with rate limiting info."""
    api_key: str
    provider_type: ProviderType
    requests_count: int = 0
    error_count: int = 0
    last_used: Optional[datetime] = None
    rate_limit_reset: Optional[datetime] = None
    is_healthy: bool = True
    last_error: Optional[str] = None
    
    def reset_rate_limit(self, reset_seconds: int = 60):
        """Reset rate limit after reset_seconds."""
        self.rate_limit_reset = datetime.now() + timedelta(seconds=reset_seconds)
    
    def is_rate_limited(self) -> bool:
        """Check if account is rate limited."""
        if self.rate_limit_reset:
            return datetime.now() < self.rate_limit_reset
        return False
    
    def mark_error(self, error: str):
        """Mark account with error."""
        self.error_count += 1
        self.last_error = error
        if self.error_count > 5:
            self.is_healthy = False
    
    def mark_success(self):
        """Mark successful request."""
        self.requests_count += 1
        self.last_used = datetime.now()
        self.error_count = 0
        if not self.is_healthy and self.error_count == 0:
            self.is_healthy = True


class ProviderPoolManager:
    """Manage pools of provider accounts with load balancing."""
    
    def __init__(self):
        """Initialize provider pool manager."""
        self.pools: Dict[ProviderType, List[ProviderAccount]] = {}
        self._lock = asyncio.Lock()
        self._initialize_pools()
    
    def _initialize_pools(self):
        """Initialize provider pools from settings."""
        # Deepgram STT
        if settings.DEEPGRAM_API_KEYS:
            keys = [k.strip() for k in settings.DEEPGRAM_API_KEYS.split(",") if k.strip()]
            self.pools[ProviderType.DEEPGRAM_STT] = [
                ProviderAccount(key, ProviderType.DEEPGRAM_STT)
                for key in keys
            ]
        
        # Deepgram TTS (can reuse STT keys or separate)
        if settings.DEEPGRAM_API_KEYS:
            keys = [k.strip() for k in settings.DEEPGRAM_API_KEYS.split(",") if k.strip()]
            self.pools[ProviderType.DEEPGRAM_TTS] = [
                ProviderAccount(key, ProviderType.DEEPGRAM_TTS)
                for key in keys
            ]
        
        # OpenAI
        if settings.OPENAI_API_KEYS:
            keys = [k.strip() for k in settings.OPENAI_API_KEYS.split(",") if k.strip()]
            self.pools[ProviderType.OPENAI] = [
                ProviderAccount(key, ProviderType.OPENAI)
                for key in keys
            ]
        
        # OpenRouter (primary LLM provider)
        openrouter_keys = []
        if settings.OPENROUTER_API_KEYS:
            openrouter_keys = [k.strip() for k in settings.OPENROUTER_API_KEYS.split(",") if k.strip()]
        elif settings.OPENROUTER_API_KEY:
            openrouter_keys = [settings.OPENROUTER_API_KEY.strip()]
        
        if openrouter_keys:
            self.pools[ProviderType.OPENROUTER] = [
                ProviderAccount(key, ProviderType.OPENROUTER)
                for key in openrouter_keys
            ]
    
    async def get_account(
        self,
        provider_type: ProviderType,
        strategy: str = "round_robin"
    ) -> Optional[ProviderAccount]:
        """
        Get an account from the pool using the specified strategy.
        
        Args:
            provider_type: Type of provider
            strategy: Selection strategy ("round_robin", "least_used", "random")
            
        Returns:
            ProviderAccount or None if no healthy accounts available
        """
        async with self._lock:
            pool = self.pools.get(provider_type, [])
            if not pool:
                return None
            
            # Filter healthy, non-rate-limited accounts
            available = [
                acc for acc in pool
                if acc.is_healthy and not acc.is_rate_limited()
            ]
            
            if not available:
                # If all rate limited, return least recently rate limited
                available = sorted(
                    pool,
                    key=lambda x: x.rate_limit_reset or datetime.min,
                    reverse=True
                )
                if available and available[0].rate_limit_reset:
                    # Wait time calculation could go here
                    pass
            
            if not available:
                return None
            
            # Select account based on strategy
            if strategy == "round_robin":
                # Sort by last_used, use least recently used
                available.sort(key=lambda x: x.last_used or datetime.min)
                return available[0]
            elif strategy == "least_used":
                available.sort(key=lambda x: x.requests_count)
                return available[0]
            else:  # random or default
                import random
                return random.choice(available)
    
    async def mark_success(self, account: ProviderAccount):
        """Mark successful request for account."""
        async with self._lock:
            account.mark_success()
    
    async def mark_error(
        self,
        account: ProviderAccount,
        error: str,
        rate_limit_reset_seconds: Optional[int] = None
    ):
        """Mark error for account."""
        async with self._lock:
            account.mark_error(error)
            if rate_limit_reset_seconds:
                account.reset_rate_limit(rate_limit_reset_seconds)
    
    async def get_pool_stats(self, provider_type: ProviderType) -> Dict[str, Any]:
        """Get statistics for a provider pool."""
        pool = self.pools.get(provider_type, [])
        return {
            "total_accounts": len(pool),
            "healthy_accounts": sum(1 for acc in pool if acc.is_healthy),
            "rate_limited_accounts": sum(1 for acc in pool if acc.is_rate_limited()),
            "total_requests": sum(acc.requests_count for acc in pool),
            "total_errors": sum(acc.error_count for acc in pool),
        }


# Global provider pool manager instance
provider_pool_manager = ProviderPoolManager()

