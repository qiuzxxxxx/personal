# Backend image for the zixxx workbench.
#
# The build installs the backend requirements into a virtual environment and
# collects the static files. The frontend is built separately and served by
# Nginx (see frontend/Dockerfile).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

WORKDIR /app

# Build tools are needed for psycopg, cryptography and pymupdf wheels.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/pip" install --upgrade pip \
    && "$VIRTUAL_ENV/bin/pip" install -r /app/requirements.txt

COPY . /app

# The knowledge worker and the web process both use this image.
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /app/media /app/staticfiles /app/var

EXPOSE 8000

# Daphne serves HTTP, SSE and WebSocket on one async process (section 12.7).
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
