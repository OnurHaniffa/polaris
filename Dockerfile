# Production image (Railway). Dev uses compose.yml for Postgres and Redis only.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# collectstatic only needs the settings to import, so placeholder values are enough
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db REDIS_URL=redis://localhost:6379/0 \
    CSRF_TRUSTED_ORIGINS=https://localhost EMAIL_URL=consolemail:// \
    python manage.py collectstatic --noinput

RUN useradd --create-home app && chown -R app /app
USER app

# Migrate on start: one replica, and it works the same on Railway, a VPS or locally.
# (Railway ignores railway.toml pre-deploy commands on services created after its
# config-as-code deprecation.) Railway sets PORT.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile -"]
