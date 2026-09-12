# Handoff state

Updated 2026-09-12. The five issues recorded at handoff have been fixed and verified; this file now records
what was done and what genuinely remains.

## Previously known issues — all resolved

1. **3D fleet rendering — fixed.** The cause was `distanceFactor` on the turbine label's drei `<Html>`. That
   prop assumes a perspective camera, and the scene uses an `OrthographicCamera`, so it produced a corrupted
   transform (one label measured roughly 30,000 x 20,000 px) that broke WebGL rendering for the whole canvas,
   not merely the label. Solar blocks were unaffected because their labels never set the prop, which is what
   isolated it. Removing it restores the full site twin.
2. **Mobile planner overflow — fixed.** At the 980px breakpoint the grids used a bare `1fr`, which is
   `minmax(auto,1fr)` and therefore cannot shrink below the Gantt's intrinsic width, so the page was pushed
   sideways instead of the Gantt scrolling inside its own container. Now `minmax(0,1fr)`, with `min-width:0`
   on `.stack`. Verified 0px horizontal overflow on all nine routes at 390x844.
3. **Journey assertion mismatch — fixed.** Product wording aligned to the brief: "Signals most associated with
   this deviation".
4. **Offline end-to-end — verified, and a related bug fixed.** The export writes RSC segment payloads at
   `<route>/__next.<segment>/__PAGE__.txt` while the router requests `<route>/__next.<segment>.__PAGE__.txt`.
   A static host cannot resolve one to the other, so every prefetch returned 404 and client-side navigation
   quietly degraded to full page loads. `scripts/build_offline.py` now mirrors each payload to the requested
   name. The built site serves all nine routes with no 404s.
5. **Accessibility and responsive review — completed.** No unnamed buttons or links, no missing image alt
   text, no unlabelled form controls, one `h1` and a `main` landmark per route. The command palette takes
   focus on open and releases it on Escape.

## Verification completed

- Playwright journey suite: 3 passed, including the full detect → investigate → plan → technician → evidence
  path, the phone overflow check and offline reload/navigation.
- Python suite: 30 passed.
- Production build: all 11 routes exported; typecheck and lint clean.
- Built output served and re-checked route by route with no console errors.
- The e2e web server now uses the bundled `serve` dependency rather than `python3`, which is not on PATH on
  Windows, and the port is overridable with `E2E_PORT`.
- Container images build and the full Compose stack runs: web, API and PostgreSQL all report healthy, the API
  reports `"database":"postgresql"`, and every route is served through nginx. Both Kubernetes overlays render
  and pass client-side validation. See `docs/DEPLOYMENT.md` for what is and is not verified.

- Infrared classifier trained on the Raptor Maps set (D016): held-out macro-F1 0.608, anomaly recall 96.1
  percent. Live API check classified one real crop per class with genuine Grad-CAM. Weights committed.

## Missing capabilities/evidence

- M1 (EnergyFaultDetector autoencoder), M3 and the M1/M2 fusion are untrained, and nothing is SHAP-explained.
  M2 is the only real model.
- The official CARE benchmark quantities (CARE score, coverage, accuracy, reliability, earliness) have not
  been computed. The Performance page reports our own measured results and leaves that table empty.
- The solar telemetry archive is still not downloaded; solar analytics use generated series.
- No model card or Hugging Face publication for the infrared classifier.
- SQLite demo record storage exists, not the normalized TimescaleDB schema and migrations from the brief.
- MQTT and webhook integration code is unverified against external infrastructure. No Slack message was sent.
- WebSocket alerts now connect (D017); the escalation path itself is still unverified against a broker.
- No production authentication, durable job queue or cross-device offline synchronization.
- API Sentry hook exists; DSN and monitoring verification are absent. Web Sentry is not wired.
- Kubernetes manifests render and validate but have never been applied to a live cluster; no cluster was available.
- No production deployment, deck, backup video or full rehearsal.

## Suggested completion order

Train M1 and the fusion, since M2 alone detects 14 of 37 anomaly events and the remaining gains are unlikely
to come from tuning it further. Then acquire the solar telemetry dataset so that screen stops running on
generated series. The infrared classifier's rare classes would benefit most from more Soiling and Hot-Spot
examples. Deployment remains the user's to perform.
