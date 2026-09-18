# Web app: React frontend built in a Node stage, served by the FastAPI backend.
# The Cosmos NIM runs as its own container (see docker-compose.yml); this image needs no GPU.

FROM node:20-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# vite.config.ts writes to ../backend/static
RUN mkdir -p /build/backend && npm run build

FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY tools/ tools/
COPY products/ products/
COPY --from=frontend /build/backend/static backend/static

RUN useradd --create-home --uid 1000 app && mkdir -p /app/outputs && chown -R app /app/outputs
USER app
ENV OUTPUTS_DIR=/app/outputs
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/products', timeout=4)"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
