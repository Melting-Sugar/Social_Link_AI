# §5: same image serves both the FastAPI process and the Celery worker
# process (see infra/docker-compose.yml) — they share this build, just
# with a different CMD, since they need the same code and dependencies.
FROM python:3.11-slim

# ffmpeg: audio normalization + per-speaker slicing (§3.4, app/audio/).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

ENV PATH="/app/.venv/bin:$PATH"

# Runs as a non-root user — the container previously ran as root by
# default, unnecessary privilege for a process that only needs to read
# its own code, write to /tmp (world-writable by default; see
# app/audio/temp_storage.py's TEMP_AUDIO_DIR), and talk to the network.
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
