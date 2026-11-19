# Emergexia en un solo servicio (Render, Railway, cualquier servidor con Docker):
# 1) construye las pantallas de React, 2) las copia junto al backend de FastAPI, que sirve
# la API en /api y las pantallas en todo lo demás.
#
#   docker build -t emergexia .
#   docker run -p 8000:8000 --env-file backend/.env emergexia
#
# Spark es opcional y necesita Java (≈200 MB más de imagen y bastante memoria). Por defecto no
# se instala: todo funciona igual y en Configuración Spark aparece como no disponible. Para
# incluirlo:  docker build --build-arg INCLUIR_JAVA=true -t emergexia .

# ── 1. Pantallas ──────────────────────────────────────────────────────────
FROM node:22-alpine AS pantallas
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 2. Backend + pantallas ────────────────────────────────────────────────
FROM python:3.12-slim
ARG INCLUIR_JAVA=false
RUN if [ "$INCLUIR_JAVA" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
      && rm -rf /var/lib/apt/lists/*; \
    fi
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIR=/app/static \
    DATA_DIR=/app/data

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY --from=pantallas /front/dist ./static
RUN mkdir -p /app/data && useradd --create-home emergexia && chown -R emergexia /app/data
USER emergexia

EXPOSE 8000
# Render indica el puerto en $PORT. Un solo proceso: los avisos al instante y los modelos de IA
# viven en memoria.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
