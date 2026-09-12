# Kubernetes

```
k8s/
├── base/
│   ├── api.yaml           Deployment, Service, HorizontalPodAutoscaler, PodDisruptionBudget
│   ├── web.yaml           Deployment and Service for the nginx-served static export
│   ├── config.yaml        ConfigMap and a Secret template
│   ├── ingress.yaml       / to the site, /api to the Python API
│   └── kustomization.yaml
└── overlays/
    ├── dev/               one replica each, no autoscaler
    └── prod/              three replicas, image tags pinned to a registry
```

## Validate and apply

```bash
kubectl kustomize k8s/overlays/dev | kubectl apply --dry-run=client -f -   # validate
kubectl apply -k k8s/overlays/dev                                          # apply
make k8s-validate                                                          # both overlays
```

Both overlays expect the images to exist. On a local cluster, build them and load them in, for example
`kind load docker-image urjakavach-api:latest`.

## Status

Both overlays render and every resource passes `kubectl apply --dry-run=client`. They have **not** been applied
to a live cluster, because no cluster was available. Treat this as reviewed-but-unrun.

## Before deploying

- **Secrets are a template.** `base/config.yaml` carries a placeholder `DATABASE_URL`. Create the real secret
  out of band, or point an external-secrets controller at the name `urjakavach-secrets`.
- **No database is included.** The manifests assume PostgreSQL exists and is reachable.
- **Alert escalation timers live in process.** They do not survive a restart and replicas do not share
  escalation state, so this is not a durable job queue.
- **The API is unauthenticated.** The role switcher in the UI is a demonstration, not access control. Do not
  expose the ingress publicly as-is.

Full deployment notes, including the Docker path, are in [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).
