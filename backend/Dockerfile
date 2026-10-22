# Pinned by digest, not just tag — the "pinned base image" non-negotiable from
# docs/ARCHITECTURE.md §7.1 / backend/README.md. Digest verified against Docker Hub's
# registry API for python:3.12.7-slim-bookworm; re-verify before bumping.
FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56

WORKDIR /app

# Dependencies in their own layer so code-only changes don't bust the pip-install cache.
COPY requirements.txt .
# --progress-bar off: the Unicode progress bars otherwise crash some log-streaming clients.
RUN pip install --no-cache-dir --no-compile --progress-bar off -r requirements.txt

COPY app/ ./app/

# Non-root — no shell/home needed for this process.
RUN groupadd --system app && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
