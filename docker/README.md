# Container images

```
docker/
├── api.Dockerfile     Python API: FastAPI, OR-Tools CP-SAT, loss bands, image screening
├── web.Dockerfile     Next.js static export, built then served by nginx
└── nginx.conf         cache rules, security headers, static-export routing
```

## Run the whole stack

```bash
docker compose up --build     # web :8080 · API :8000 · PostgreSQL :5432
```

Or build the images on their own:

```bash
make images
docker build -f docker/api.Dockerfile -t urjakavach-api:latest .
docker build -f docker/web.Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t urjakavach-web:latest .
```

Both are built from the repository root, not from this directory, because they copy `services/` and `apps/`.

## Two things worth knowing

**The API address is baked into the web image at build time.** The frontend is a static export with no server
to read the environment, so `NEXT_PUBLIC_API_URL` is a build argument. Pointing the site at a different backend
means rebuilding the image rather than editing a variable at deploy time.

**The API image contains no compiler and no apt packages.** Every pinned dependency publishes a manylinux wheel
for CPython 3.12 and `psycopg2-binary` bundles libpq, so `--only-binary=:all:` is enough. That flag is
deliberate: if a future pin ever lacks a wheel, the build fails loudly here instead of quietly pulling a
toolchain into the image.

## Status

Both images build, and `docker compose up` brings up web, API and PostgreSQL with all three reporting healthy.
The API reports `"database":"postgresql"` rather than falling back to SQLite, and every route is served through
nginx including the service worker.
