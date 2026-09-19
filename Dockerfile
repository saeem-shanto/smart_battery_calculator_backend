FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends octave \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Ensure staticfiles directory exists with correct write permissions for user 'app'
RUN mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles
RUN chmod +x scripts/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["./scripts/entrypoint.sh"]

CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --worker-class gthread --threads 2 --timeout 180 --graceful-timeout 30 --max-requests 50 --max-requests-jitter 10 --access-logfile - --error-logfile -"]
