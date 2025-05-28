FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use eventlet worker with single worker
CMD ["gunicorn", "--worker-class=eventlet", "--workers=1", "--bind=0.0.0.0:8000", "--timeout=120", "liveserver:app"]