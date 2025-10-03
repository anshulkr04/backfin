FROM python:3.10-slim

# Prevent tzdata interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system packages we need: sqlite3 CLI + build deps (small)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      procps \
      sqlite3 \
      libsqlite3-dev \
      build-essential \
      tzdata \
 && rm -rf /var/lib/apt/lists/*

# Copy and install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Make scripts executable
RUN chmod +x replay.py replay_service.py

# Ensure the data directory exists and has permissive perms (container-side)
RUN mkdir -p /app/data && chmod 755 /app/data

# Use eventlet worker with single worker by default (docker-compose overrides via command)
CMD ["gunicorn", "--worker-class=eventlet", "--workers=1", "--bind=0.0.0.0:8000", "--timeout=120", "liveserver:app"]
