# UrjaKavach web: Next.js static export served by nginx.
# Build from the repository root:  docker build -f infra/docker/web.Dockerfile -t urjakavach-web .
#
# NEXT_PUBLIC_API_URL is read at build time, not at run time, because the output is a static export with no
# server to read the environment. Pointing the image at a different backend means rebuilding it.
FROM node:24-bookworm-slim AS build
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /src

# scripts/build_offline.py generates the service worker from the finished export.
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
RUN npm ci

COPY apps/ ./apps/
# The workspace build script runs next build and then scripts/build_offline.py itself.
COPY scripts/build_offline.py ./scripts/
RUN npm run build --workspace=@urjakavach/web

FROM nginx:1.27-alpine AS runtime
RUN apk add --no-cache curl
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/out /usr/share/nginx/html
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/ || exit 1
