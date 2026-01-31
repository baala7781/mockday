"""Application settings and configuration."""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings."""
    
    # API Gateway
    API_GATEWAY_HOST: str = "0.0.0.0"
    API_GATEWAY_PORT: int = 8000
    
    # Service URLs
    USER_SERVICE_URL: str = "http://localhost:8001"
    INTERVIEW_SERVICE_URL: str = "http://localhost:8002"
    REPORT_SERVICE_URL: str = "http://localhost:8003"
    ANALYTICS_SERVICE_URL: str = "http://localhost:8004"
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH",
        os.path.join(os.path.dirname(__file__), "../../firebase-service-account.json")
    )
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv(
        "FIREBASE_STORAGE_BUCKET",
        "intervieu-7a3bb.appspot.com"  # Legacy Firebase project ID (keep as-is)
    )
    
    # Database
    POSTGRES_URL: str = os.getenv(
        "POSTGRES_URL",
        "postgresql+asyncpg://user:password@localhost:5432/mockday"  # Updated to mockday
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Provider API Keys (comma-separated)
    DEEPGRAM_API_KEYS: str = os.getenv("DEEPGRAM_API_KEYS", "")
    OPENAI_API_KEYS: str = os.getenv("OPENAI_API_KEYS", "")
    GEMINI_API_KEYS: str = os.getenv("GEMINI_API_KEYS", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")  # Single key (for backward compatibility)
    OPENROUTER_API_KEYS: str = os.getenv("OPENROUTER_API_KEYS", "")  # Comma-separated keys for pool management
    OPENROUTER_REFERER_URL: str = os.getenv("OPENROUTER_REFERER_URL", "https://mockday.io")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS
    FRONTEND_URL: str = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5174"
    )
    
    # ALLOWED_ORIGINS - accept comma-separated string from env
    # Don't use List[str] type to avoid Pydantic JSON parsing issues
    ALLOWED_ORIGINS_STR: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5174,http://localhost:3000")
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS allowed origins from environment or defaults."""
        origins_str = self.ALLOWED_ORIGINS_STR
        if origins_str == "*":
            return ["*"]
        if origins_str:
            return [origin.strip() for origin in origins_str.split(",")]
        return ["http://localhost:5174", "http://localhost:3000"]
    
    # Queue
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Audio Processing
    AUDIO_CHUNK_SIZE: int = 4096  # bytes
    AUDIO_SAMPLE_RATE: int = 16000  # Hz
    AUDIO_CHANNELS: int = 1  # mono
    
    # Session Management
    SESSION_TIMEOUT: int = 3600  # seconds (1 hour)
    SESSION_CLEANUP_INTERVAL: int = 300  # seconds (5 minutes)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Ignore extra fields (like VITE_* variables which are frontend-only)
        extra = "ignore"


# Global settings instance
settings = Settings()

