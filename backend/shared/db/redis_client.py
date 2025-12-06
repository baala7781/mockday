"""Redis client for caching and session management."""
import redis.asyncio as aioredis
from shared.config.settings import settings
from typing import Optional, Any
import json


class RedisClient:
    """Redis client wrapper."""
    
    def __init__(self):
        """Initialize Redis client."""
        self.redis: Optional[aioredis.Redis] = None
        self._connection_pool = None
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self._connection_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=50,
                decode_responses=True
            )
            self.redis = aioredis.Redis(connection_pool=self._connection_pool)
            # Test connection
            await self.redis.ping()
        except Exception as e:
            # Redis is optional - log at debug level if connection fails
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Redis connection failed (non-critical): {e}")
            logger.info("Continuing without Redis - using Firestore only for state persistence")
            self.redis = None
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
        if self._connection_pool:
            await self._connection_pool.disconnect()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self.redis:
            return None
        try:
            value = await self.redis.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            # Redis errors are non-critical - log at debug level
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error getting from Redis (non-critical): {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in Redis."""
        if not self.redis:
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            # Redis errors are non-critical - log at debug level
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error setting in Redis (non-critical): {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self.redis:
            return False
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error deleting from Redis (non-critical): {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.redis:
            return False
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error checking existence in Redis (non-critical): {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment value in Redis."""
        if not self.redis:
            return None
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error incrementing in Redis (non-critical): {e}")
            return None
    
    async def set_expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        if not self.redis:
            return False
        try:
            return await self.redis.expire(key, seconds)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error setting expire in Redis (non-critical): {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()

