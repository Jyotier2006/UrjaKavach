# UrjaKavach Python API: loss estimation, CP-SAT scheduling, work orders, image screening, alert replay.
# Build from the repository root:  docker build -f infra/docker/api.Dockerfile -t urjakavach-api .
#
# Every pinned dependency publishes a manylinux wheel for CPython 3.12, and psycopg2-binary bundles libpq, so
# the image needs no compiler and no apt packages at all. `--only-binary=:all:` makes that contract explicit:
# if a future pin ever lacks a wheel the build fails loudly here rather than silently pulling in a toolchain.
FROM python:3.12-slim AS deps
WORKDIR /build
COPY requirements.lock ./
RUN pip install --no-cache-dir --only-binary=:all: --prefix=/install -r requirements.lock

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000
RUN useradd --create-home --uid 10001 urja
COPY --from=deps /install /usr/local
WORKDIR /app

# Only what the API actually serves. Raw datasets and the web app are deliberately absent.
COPY services/ ./services/
COPY artifacts/demo_bundle/ ./artifacts/demo_bundle/
COPY artifacts/openapi.json ./artifacts/openapi.json

# db.py writes the SQLite fallback here when DATABASE_URL is unset.
RUN mkdir -p /app/.state && chown -R urja:urja /app
USER urja
EXPOSE 8000

# urllib rather than curl, so the image stays free of apt entirely.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["sh", "-c", "uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT}"]
