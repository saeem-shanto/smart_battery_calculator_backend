FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# GNU Octave replaces MATLAB Runtime for the deployed client algorithm.
# --no-install-recommends keeps the image smaller and avoids GUI extras where possible.
RUN apt-get update \
    && apt-get install -y --no-install-recommends octave libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./scripts/entrypoint.sh"]

# Render Free: one synchronous worker means only one request executes at a time.
# The OctaveEngine also uses an in-process lock as a second safety layer.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --worker-class sync --threads 1 --timeout 180 --max-requests 25 --max-requests-jitter 5 --access-logfile -"]
