# Intervieu Backend - Production Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements-fastapi.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-fastapi.txt

# Copy application code
COPY . .

# Remove development files
RUN rm -rf tests/ scripts/ intervieu/ __pycache__/ *.md docs/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Railway uses dynamic PORT)
EXPOSE 8002

# Health check disabled for Railway (uses its own)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

# Start server - Railway injects PORT env var
CMD uvicorn interview_service.main:app --host 0.0.0.0 --port ${PORT:-8002} --workers 2 --ws-ping-interval 20 --ws-ping-timeout 120

