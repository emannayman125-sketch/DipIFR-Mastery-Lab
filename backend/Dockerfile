FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
# Shell form (not JSON array) so ${PORT} actually expands — Railway (and
# most PaaS hosts) inject a dynamic PORT at runtime; the app must listen on
# it, not a hardcoded port, or the deploy's health check will fail even
# after a successful build. Falls back to 8000 for local `docker run`.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
