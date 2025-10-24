# Use Python 3.13 slim image for smaller size
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# FFmpeg is required for audio processing (pydub, SpeechRecognition)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p downloads_folder templates

# Expose port
EXPOSE 5080

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5080/', timeout=5)" || exit 1

# Run with gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "web_app:app"]
