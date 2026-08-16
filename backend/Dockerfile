FROM python:3.11-slim

# Install FFmpeg and build tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (preserving folder namespace)
COPY app/ ./backend/app/

# Set Python Path to resolve namespace imports properly
ENV PYTHONPATH=/app

EXPOSE 8000

# Run uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
