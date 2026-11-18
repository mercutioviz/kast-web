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
# Runtime directories — all under /var/lib/kast-web so they land on the volume
# declared below and survive container removal.
# /var/lib/kast-web/results — scan output
# /var/lib/kast-web/logos   — report logos. 2.0.14/2.0.15 moved logo storage
#   out of the static tree (it was reachable unauthenticated through nginx);
#   LOGO_STORAGE_DIR is set below so it does not fall back to /app/instance,
#   which appuser cannot write and which is not on the volume.
# ---------------------------------------------------------------------------
RUN mkdir -p /var/lib/kast-web/results \
             /var/lib/kast-web/logos \
    && chown -R appuser:appuser /var/lib/kast-web

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
    LOGO_STORAGE_DIR=/var/lib/kast-web/logos \
    KAST_CLI_PATH=/usr/local/bin/kast \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# NOTE: SECRET_KEY and ENCRYPTION_KEY must be supplied at runtime via
# --env-file or -e. The app will refuse to start in production without them.

# NOTE: The kast CLI binary must be present at KAST_CLI_PATH inside the
# container. Bind-mount it from the host or build a combined image:
#   COPY --from=kast-builder /usr/local/bin/kast /usr/local/bin/kast

# NOTE: Cloud scanning (app/cloud) shells out to `terraform`, which is NOT
# installed here — it would add ~80MB to an image most deployments do not use
# it in. Local and remote ZAP execution modes work without it. For cloud mode,
# bind-mount a terraform binary or extend this image:
#   RUN curl -fsSL https://releases.hashicorp.com/terraform/... -o /tmp/tf.zip \
#       && unzip /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip

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
