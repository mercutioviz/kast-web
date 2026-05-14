FROM python:3.13-slim

# Build-time UID/GID — override with --build-arg if your host user differs
ARG UID=1000
ARG GID=1000

# ---------------------------------------------------------------------------
# System packages
# curl  — health check
# gcc / libffi-dev — needed by some Python wheels (cryptography, gevent)
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Non-root runtime user
# ---------------------------------------------------------------------------
RUN groupadd --gid "${GID}" appuser \
    && useradd --uid "${UID}" --gid "${GID}" --no-create-home --shell /bin/false appuser

WORKDIR /app

# ---------------------------------------------------------------------------
# Python dependencies — separate layer so rebuilds on code changes are fast
# ---------------------------------------------------------------------------
COPY requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
COPY . .

# Install the package so the kast-web console script is registered
RUN pip install --no-cache-dir --no-deps -e .

# ---------------------------------------------------------------------------
# Runtime directories
# /var/lib/kast-web   — SQLite database + scan results (mount as a volume)
# app/static/uploads  — logo uploads (persisted inside the data volume or
#                       bind-mounted separately)
# ---------------------------------------------------------------------------
RUN mkdir -p /var/lib/kast-web/results \
             /app/app/static/uploads/logos \
    && chown -R appuser:appuser /var/lib/kast-web /app/app/static/uploads

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# ---------------------------------------------------------------------------
# Runtime environment defaults (override with -e or --env-file)
# ---------------------------------------------------------------------------
ENV FLASK_ENV=production \
    DATABASE_URL=sqlite:////var/lib/kast-web/kast.db \
    CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/0 \
    KAST_RESULTS_DIR=/var/lib/kast-web/results \
    KAST_CLI_PATH=/usr/local/bin/kast \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# NOTE: SECRET_KEY and ENCRYPTION_KEY must be supplied at runtime via
# --env-file or -e. The app will refuse to start in production without them.

# NOTE: The kast CLI binary must be present at KAST_CLI_PATH inside the
# container. Bind-mount it from the host or build a combined image:
#   COPY --from=kast-builder /usr/local/bin/kast /usr/local/bin/kast

# ---------------------------------------------------------------------------
# Scan results + database are stateful — declare as a volume so Docker
# does not silently discard them on container removal.
# ---------------------------------------------------------------------------
VOLUME ["/var/lib/kast-web"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8000/ || exit 1

USER appuser

ENTRYPOINT ["docker-entrypoint.sh"]

# Default role: web server.
# Override to "worker" for the Celery container:
#   docker run kast-web worker
CMD ["serve"]
