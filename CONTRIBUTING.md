# UrjaKavach engineering conventions

The product serves renewable operators, technicians and asset managers.

- Python 3.12 for models, data preparation, API, scheduling, loss and IoT. TypeScript is browser UI only.
- Next.js App Router static export in `apps/web`. Plain CSS with shared tokens; no mixed styling systems.
- `npm ci`, `npm run dev`, `npm run typecheck`, `npm run lint`, `npm run build` from the repository root.
- API: `.venv/bin/uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000`.
- Python tests: `.venv/bin/python -m pytest services tests -q`.
- Browser tests: `npm run test:e2e` (set `E2E_PORT` if 3000 is taken).
- Regenerate synthetic artifacts: `.venv/bin/python scripts/generate_demo.py`.
- Train and evaluate M2 on CARE: `.venv/bin/python scripts/train_care_nbm.py <A|B|C>`, then
  `.venv/bin/python scripts/publish_care_evaluation.py` to publish the result to the web artifact.

## Evidence rules

These are the rules that keep the product honest. They are not optional.

- Never label synthetic signals as CARE or as historical measurements. Never invent held-out performance,
  calibrated risk or savings.
- Model thresholds are calibrated on healthy data only. Tuning a threshold until the labelled faults light up
  is fitting to the test set and is not permitted.
- Report the full detection/false-alarm trade-off, not the single operating point that flatters the result.
- A rise in raw detection count is not on its own an improvement; warning time and false alarms decide whether
  a change is kept.
- Scores, estimates and charts reference artifact provenance. Empty benchmark results stay empty until the
  corresponding evaluation actually exists.
- Each feature traces to R1-R7 in docs/TRACEABILITY.md. Record consequential changes in PROGRESS.md and
  docs/DECISIONS.md.
- Keep API and artifact contracts backward compatible. Offline behaviour must survive API failures.
- Browser QA covers replay, investigation, repair scheduling, technician completion and evidence.
- Commit small logical units. Never commit secrets, raw datasets, virtual environments or model weights.
- Local demo state uses browser storage. It is not authentication and is not suitable for shared production.
