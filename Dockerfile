FROM python:3.11-slim

LABEL org.opencontainers.image.title="demo-banking-api" \
      org.opencontainers.image.description="Harness + Claude Code demo banking API"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

EXPOSE 8080

ENV FLASK_APP=app.main \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60", "app.main:app"]
