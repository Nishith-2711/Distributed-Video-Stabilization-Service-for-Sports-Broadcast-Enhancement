# Use official Python image
FROM python:3.11-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (including ffmpeg and redis)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    git \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose port (Hugging Face Spaces uses 7860)
EXPOSE 7860

# Run startup script
CMD ["./start.sh"]