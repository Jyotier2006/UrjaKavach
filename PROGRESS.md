# Build progress

## Scope
Complete website with all product screens and working demo interactions, Python services shipped separately, deployed to Vercel. Absent datasets must never produce invented results.

## Done
- Selected the problem statement and guidelines from the HackOut'26 brief.
- Created fleet and maintenance design concepts.
- Defined a static-export web delivery and optional Python API integration.

## In progress
- Application, reproducible synthetic demo bundle, Python domains and source documentation.

## CARE ingestion and first real M2 (2026-09-12)
- CARE To Compare v6 downloaded and MD5-verified against the provider checksum, extracted to `data/raw/CARE_To_Compare/` (95 events, 3 farms, ~19 GB, gitignored).
- LightGBM 4.7.0 installed and pinned in `requirements.lock`, replacing the Ridge stand-in for M2 (see D010).
- `services/ml/care_loader.py` infers column roles per farm from that farm's own feature description; `services/ml/normal_behavior.py` fits one temperature model per component; `scripts/train_care_nbm.py` evaluates against the dataset's own labels.
- Thermal-inertia predictors and trend scoring added (D013), and common-mode rejection tried then rejected on measurement (D014).
- **All three farms evaluated at one deployable threshold (D015): 14 of 37 anomaly events detected, 4 of 50 healthy events raising a false alarm, 26.3-day median warning on the strongest farm.** Per farm: 0 of 4 on A, 5 of 6 on B, 9 of 27 on C. Farm C was never tuned against and is the honest test; the farm B figure must not be quoted alone.
- Farm A contributes little: 8 of its 12 anomaly events have no running hours in the prediction window and are reported as not assessable rather than as misses. That is how farm A's windows were cut, not a tuning failure.
- Results published to the Performance page via `scripts/publish_care_evaluation.py`, sitting above the official CARE benchmark table, which stays empty because those quantities have not been computed.
- Results in `artifacts/metrics/care_m2_wind_farm_{a,b,c}.json`, ablation in `care_m2_wind_farm_b_cmr.json`.
- All five handoff issues fixed and verified: 3D rendering, mobile overflow, journey wording, offline/RSC prefetch 404s, accessibility. See docs/HANDOFF.md.
- Verification: 30 Python tests, 3 Playwright journey tests, production build, typecheck and lint all pass.

## Infrastructure (2026-09-12)
- Container images for the API and web app, both building and running. Compose brings up web, API and PostgreSQL with all three healthy and the API actually on Postgres rather than the SQLite fallback.
- Kubernetes base manifests with dev and prod overlays: probes, resource bounds, non-root and read-only-root security contexts, HPA, PodDisruptionBudget and ingress. Both overlays render and pass `kubectl apply --dry-run=client`. Never applied to a live cluster.
- CI workflow covering Python tests, typecheck/lint/build, the browser journey, both image builds and manifest validation.
- Fixed along the way: `scripts/build_offline.py` failed on a fresh clone because `artifacts/metrics/` did not exist, and `/health` hardcoded `care_evaluated: false`, which had gone stale.

## Outstanding evidence
- M1 (EnergyFaultDetector autoencoder), M3 and the M1/M2 fusion are still untrained; SHAP explanations are still absent. Only M2 exists as a real model.
- The fleet, solar and planner screens still run on the synthetic demo bundle and remain labelled Simulated. The measured CARE results appear only on the Performance page, and are kept visibly separate from that simulated fleet.
- Reported CARE numbers come from our own normal-behavior approach on real CARE labels. They are not a published CARE benchmark score and must never be presented as one.
- Docker runtime and deployed cloud infrastructure are unavailable in the current runtime; no cloud deployment will be claimed.
- Sentry DSNs, Slack webhook and trained IR weights are not supplied.

## Next
- Complete the interaction flows, run Python and browser tests, build production assets and package source.
