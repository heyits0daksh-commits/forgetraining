# FORGE — container image for Google Cloud Run (or any Docker host).
# Cloud Run injects the PORT env var at runtime (usually 8080) and expects
# the container to listen on it, so the CMD reads $PORT directly instead
# of the hardcoded API_PORT default in backend/core/config.py.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so Docker caches this layer between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app (backend + frontend + data)
COPY . .

# Cloud Run sets PORT; default to 8080 for local `docker run` testing
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
