# ============================================================
# Safe Pickup API — imagen de producción
# ============================================================
# Build:  docker build -t safe-pickup-api .
# Run:    docker run --env-file .env -p 8000:8000 safe-pickup-api
# (las credenciales de Supabase se pasan por variables de entorno,
#  nunca se copian dentro de la imagen)

# ---------- etapa 1: instalar dependencias en un venv ----------
FROM python:3.11-slim AS builder

WORKDIR /build

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------- etapa 2: imagen final, sin herramientas de build ----------
FROM python:3.11-slim

RUN groupadd -r app && useradd -r -g app -d /app app

WORKDIR /app

COPY --from=builder /venv /venv
COPY app ./app

ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# WEB_CONCURRENCY y PORT son sobreescribibles por la plataforma de hosting
# (Render/Railway/Fly suelen inyectar PORT automáticamente).
CMD gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-2} \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
