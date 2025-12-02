# ============================================
# Multi-Agent Analytics Gateway (MAAG)
# Dockerfile
# ============================================

# 1. Base Image
FROM python:3.10-slim

# 2. Environment Setup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set Workdir
WORKDIR /app

# 4. System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy project files
COPY . .

# 6. Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 7. Expose ports (API:8000, UI:7860)
EXPOSE 8000
EXPOSE 7860

# 8. Default command is overridden in docker-compose
CMD ["python", "api/server.py"]
