# Deployment

Three supported paths. Per-directory detail lives in [docker/README.md](../docker/README.md) and
[k8s/README.md](../k8s/README.md).

## 1. Static site only

The frontend ships a precomputed demo bundle and needs no backend at all. This is the deployment the project
was designed around.

| Vercel setting | Value |
|---|---|
| Root Directory | `.` (repository root) |
| Framework Preset | Other — the static export is deliberate |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `apps/web/out` |

Leave `NEXT_PUBLIC_API_URL` unset for the bundled demonstration. To attach a backend later, set it to that
backend's HTTPS URL and rebuild, because a static export reads it at build time rather than at runtime.

## 2. Docker Compose

```bash
docker compose up --build     # web :8080 · API :8000 · PostgreSQL :5432
```

Verified: all three services report healthy, the API reports `"database":"postgresql"` rather than falling back
to SQLite, and every route is served through nginx including the service worker.

## 3. Kubernetes

```bash
kubectl kustomize k8s/overlays/dev | kubectl apply --dry-run=client -f -   # validate
kubectl apply -k k8s/overlays/dev                                          # apply
```

Both overlays render and pass client-side validation. They have **not** been applied to a live cluster, because
no cluster was available. Treat this path as reviewed-but-unrun.

## What must be settled before a public deployment

These are properties of the current build, not deployment bugs, and none of them are fixed by choosing a
different host.

- **The API has no authentication.** The role switcher in the UI is a demonstration, not access control.
- **Secrets are templates.** `k8s/base/config.yaml` carries a placeholder `DATABASE_URL`. Create the real
  secret out of band or use an external-secrets controller.
- **Alert escalation timers live in process.** They do not survive a restart, and replicas do not share
  escalation state, so this is not a durable job queue.
- **Demo mutations are browser-local.** Local demo state is browser storage, not shared server state.
- **The operational fleet shown in the app is simulated.** Only the CARE evaluation on the Performance page is
  measured on real turbine data, and it is kept visibly separate from the simulated fleet.
