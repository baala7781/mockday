# Intervieu Backend - Production Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements from backend folder
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Remove development files
RUN rm -rf tests/ scripts/ intervieu/ __pycache__/ *.md docs/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Railway uses PORT env var
CMD uvicorn interview_service.main:app --host 0.0.0.0 --port ${PORT:-8002} --workers 2 --ws-ping-interval 20 --ws-ping-timeout 120

