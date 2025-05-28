FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose both HTTP and WebSocket traffic on same port
EXPOSE 8000

# Use gevent worker since you're already using gevent
CMD ["gunicorn", "--worker-class=gevent", "--worker-connections=1000", "--workers=1", "--bind", "0.0.0.0:8000", "--timeout=120", "liveserver:app"]