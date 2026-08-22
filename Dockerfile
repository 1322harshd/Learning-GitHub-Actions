FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Environment variables for Flask
ENV FLASK_ENV=production \
    PYTHONPATH=/app

# Install minimal build tools for dependencies needing compilation
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list first for caching
COPY requirements.txt .

# Install dependencies and Gunicorn
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m appuser
USER appuser

# Expose Flask port
EXPOSE 8000

# Use Gunicorn for production serving
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
