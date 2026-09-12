# UrjaKavach

Renewable asset operations for HackOut’26: detect → investigate → prioritize → act → inspect the evidence.

## Start here

This repository contains a working production build, a simulated demonstration fleet, and an M2 model measured on real CARE turbine data. It is **not a completed, empirically validated predictive-maintenance platform** — see the verification section below for exactly what has and has not been established.

Implemented screens: fleet overview, investigation and comparison, maintenance planner, solar operations, technician jobs and image upload, performance, asset manager, loss assumptions, and about/credits.

Implemented Python services: static-artifact API, SQLite/PostgreSQL-compatible demo persistence, loss estimates with Monte Carlo bands, OR-Tools scheduling and baselines, work-order lifecycle, image-quality screening, replay/WebSocket alerts and optional Slack webhook delivery. The MQTT publisher/subscriber source is included but has not been exercised against a broker.

## Run the website

Use Node.js 24 and Python 3.12. Run commands from the extracted `urjakavach` directory:

```bash
npm ci
npm run dev
```

Open http://localhost:3000. No API key is required for the bundled demonstration.

Production build:

```bash
npm run build
npm run start
```

The build runs `python3 scripts/build_offline.py` through the web workspace script, so `python3` must be available on PATH. On Windows, install Python 3.12 and make its executable available as `python3`, or run `npx next build` from `apps/web`, followed by `py -3.12 scripts/build_offline.py` from the repository root.

## Deploy the website on Vercel

1. Upload this source to your own GitHub repository. Exclude `node_modules`, `.venv`, raw datasets, local database files and `.env` secrets.
2. Import that repository into Vercel.
3. Use the **repository root** as Root Directory and **Other** as the Framework Preset. This project deliberately produces a static Next.js export.
4. Install Command: `npm ci`.
5. Build Command: `npm run build`.
6. Output Directory: `apps/web/out`.
7. Leave `NEXT_PUBLIC_API_URL` unset for the bundled demonstration. To connect a backend later, set it to that backend's HTTPS URL and rebuild.

The Python API is a separate service; uploading the web app does not deploy it. No Vercel deployment was made from this workspace. Verify the service worker and every route on your actual deployment before presenting.

## Run the optional API

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

Windows equivalents:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs for the OpenAPI explorer and http://127.0.0.1:8000/health for health status.

Optional backend environment variables: `DATABASE_URL`, `CORS_ORIGINS` (comma-separated frontend origins), `SLACK_WEBHOOK_URL`, `ALERT_ESCALATION_SECONDS`, `SENTRY_DSN`. Keep secrets on the backend. The demo API has no production authentication; the role switcher is a simulation. In-process escalation timers do not survive restarts.

Use `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in `apps/web/.env.local` for local integration. Restart the web dev server after setting it. The offline UI uses packaged scenarios and plans; connected actions can request live optimization and persist work orders.

## Verification actually completed

- Production Next.js build passes; all routes exported. Typecheck and lint clean.
- Python domain/API/ML suite: **30 passed**.
- Browser verification **passes**: 3 Playwright journey tests covering the full detect → investigate → plan → technician → evidence path, phone layout and offline navigation. All five issues recorded at handoff are fixed; see `docs/HANDOFF.md`.
- The 384 bundled CP-SAT planning cases were actually computed. Timing artifacts are in `artifacts/demo_bundle/manifest.json`; they are local generation times, not deployed request latency.
- **M2 is measured on real CARE To Compare v6 data**: at one threshold across all three wind farms, 14 of 37 anomaly events detected, 4 of 50 healthy events raising a false alarm, 26.3-day median warning on the strongest farm. Results are on the Performance page and in `artifacts/metrics/care_m2_wind_farm_{a,b,c}.json`. This is our own normal-behavior evaluation against real CARE labels, **not** a published CARE benchmark score; the benchmark's own quantities remain uncomputed.
- No trained CNN, SHAP explanation, M1/M3 model or verified savings exists. Solar and infrared datasets are still not downloaded.

Commands to continue verification:

```bash
.venv/bin/python -m pytest tests -q
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The Playwright config starts its own local static server using the bundled `serve` dependency, so it needs no `python3` on PATH. Set `E2E_PORT` if port 3000 is taken. The `PLAYWRIGHT_CHROMIUM_EXECUTABLE` override is optional for environments with a custom installed Chromium. Use a normal local browser to review the 3D rendering.

## Datasets and models

**CARE To Compare v6 has been downloaded, MD5-verified and extracted** to `data/raw/CARE_To_Compare/` (~19 GB, gitignored, not redistributed with this source). The solar telemetry and IR image datasets are still not downloaded. Direct sources, checksums and a downloader are in `docs/DATASETS.md` and `scripts/download_datasets.py`.

All current operational series, risk indices, gallery images and planned jobs are simulated. The expectation model is a Ridge prototype trained on generated data; it is not the specified LightGBM M2. M1 and M3 are unavailable. IR upload currently performs image-quality screening, not a trained defect classification, confidence estimate or Grad-CAM.

CARE-derived data, if you later publish it, must retain the dataset's CC BY-SA 4.0 attribution and sharing terms. Keep raw datasets and large model files out of Git.

## Where to work next

- `apps/web/src`: application screens, components and shared contracts.
- `services/api/app`: API, persistence, loss and image screening.
- `services/optimizer`: CP-SAT scheduler and comparison policies.
- `services/ml`: training-only preprocessing and criticality helpers.
- `services/simulator`: MQTT replay source.
- `scripts/generate_demo.py`: reproducible generated demonstration.
- `artifacts/demo_bundle`: precomputed scenarios, scores, estimates, schedules and provenance.
- `artifacts/openapi.json`, `apps/web/src/lib/api-schema.d.ts`: exported API contract and generated TypeScript definitions.
- `docs`: design, decisions, traceability and outstanding work.

Reused packages and planned data sources are credited in the About page. Exact installed package versions are recorded in `package-lock.json` and `requirements.lock`.
