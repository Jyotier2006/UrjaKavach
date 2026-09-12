# Infrastructure

Container images and Kubernetes manifests for UrjaKavach.

```
infra/
├── docker/
│   ├── api.Dockerfile     Python API: FastAPI, OR-Tools, loss and image screening
│   ├── web.Dockerfile     Next.js static export built and served by nginx
│   └── nginx.conf         Cache rules, security headers, static-export routing
└── k8s/
    ├── base/              Deployments, services, config, ingress, HPA, PDB
    └── overlays/
        ├── dev/           One replica each, no autoscaler
        └── prod/          Three replicas, pinned image tags
```

## What has actually been verified

| | Status |
|---|---|
| `docker build` for both images | passes |
| `docker compose up` full stack | all three services healthy |
| API reaching PostgreSQL | `/health` reports `"database":"postgresql"` |
| App served through nginx | all routes 200, service worker served |
| `kubectl kustomize` both overlays | renders clean |
| `kubectl apply --dry-run=client` | all resources validate |
| **Applied to a live cluster** | **not done — no cluster was available** |

The manifests are real and schema-valid, but they have never been scheduled onto running nodes. Treat the
Kubernetes path as reviewed-but-unrun until someone applies it to an actual cluster.

## Local stack

```bash
docker compose up --build      # web :8080, API :8000, PostgreSQL :5432
```

The web image bakes `NEXT_PUBLIC_API_URL` at build time because the frontend is a static export with no server
to read the environment. Pointing it at a different backend means rebuilding the image, which is why
`docker-compose.yml` passes the address as a build argument rather than an environment variable.

## Kubernetes

```bash
kubectl kustomize infra/k8s/overlays/dev | kubectl apply --dry-run=client -f -   # validate
kubectl apply -k infra/k8s/overlays/dev                                          # apply
```

Both overlays expect the images to exist. For a local cluster, build them and load them in, for example
`kind load docker-image urjakavach-api:latest`. The prod overlay instead pins tags from a registry.

### Things worth knowing before deploying

- **Secrets are a template only.** `base/config.yaml` carries a placeholder `DATABASE_URL`. Create the real
  secret out of band or point an external-secrets controller at the name `urjakavach-secrets`.
- **No database is included.** The manifests assume PostgreSQL exists and is reachable. Compose runs one for
  local work; production should use a managed instance.
- **Alert escalation timers live in process.** They do not survive a restart and are not a durable job queue,
  so replicas do not share escalation state.
- **The API is unauthenticated.** The role switcher in the UI is a demonstration, not access control. Do not
  expose the ingress publicly as-is.
