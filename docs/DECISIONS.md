# Decisions

## D001 — Complete website delivery
The latest user instruction requests the whole website and reserves deployment to the user. Build autonomously across the UI scope; do not trigger external deployments.

## D002 — Standalone Vercel web and Python backend
Use a Next.js static export with a fully working bundled demonstration, plus the original FastAPI/container path for live functions. This permits deployment of the web without cloud credentials or a running broker. Demo mutations are browser-local and clearly identified. The production API has separate setup instructions.

## D003 — Synthetic artifacts until source datasets are provided
CARE is absent. Generate deterministic synthetic scenarios with Python, save provenance, scores and estimates, and label the workspace Simulated. Do not supply dummy benchmark accuracy, CARE scores, CNN confidence or claimed avoided loss. Real-data ingestion and evaluation are separate commands requiring source files.

## D004 — Honest model comparison
B0 is a real percentile baseline on synthetic training observations. M2 demonstration uses a fitted normal-behavior regressor. M1/M3 are unavailable until an EnergyFaultDetector model is trained; do not rename heuristics as those models. The desired weather-vs-fault contrast in synthetic examples is an illustration, never held-out CARE proof.

## D005 — Failure probability
Detected-event lead times alone cannot calibrate fleet failure probability. The demonstration uses an explicit editable hazard assumption. Report P10/P50/P90 as scenario uncertainty, not calibrated confidence intervals.

## D006 — Offline calculations
The Python generator exports loss curves and CP-SAT plans for supported demo configurations. The browser looks them up and displays a precomputed-plan label. Arbitrary custom scenarios use the Python API; do not present client-side greedy heuristics as CP-SAT.

## D007 — Infrared honesty
Support real uploads via the Python endpoint. If trained CNN weights are absent, return clearly labelled image screening with no learned class probability and a thermal-intensity visualization, never call it Grad-CAM. Offline inspection supports preview, manual findings and labelled sample annotations.

## D008 — Target leakage
Each normal-behavior model excludes its target signal from its predictor columns, fits scaling on training only, and calibrates residual spread using a chronological held-out portion of the training section.

## D009 — Available dependency fallback
LightGBM was unavailable when the prototype was first built, so it used scikit-learn Ridge regression and the UI named that explicitly rather than implying the specified M2. Superseded by D010.

## D010 — CARE acquired; M2 is a temperature normal-behavior model
Supersedes the dependency half of D009. CARE To Compare v6 was downloaded and MD5-verified, and LightGBM 4.7.0 is installed and pinned, so M2 is now a real model on real data rather than a Ridge stand-in.

M2 predicts each monitored component temperature from operating conditions only (wind speed, power, rotational speed, ambient temperature, pitch angle) and scores one-sided: a developing fault shows as a component running hotter than the model expects. Power output was tried first and rejected on two grounds. It leaked, because a farm's other power channels reproduce it almost exactly and collapsed the residual spread to near zero; and it is the wrong physics, because the labelled failures are thermal (gearbox, generator bearing, transformer, hydraulic group) and each has a directly corresponding temperature sensor. Other temperatures are kept out of the predictor set so a co-drifting neighbour cannot explain away a real fault, and counters are excluded because they grow monotonically and act as a proxy for time.

Column roles are inferred per farm from that farm's own `feature_description.csv`, never hardcoded by sensor number, because the anonymized numbering differs between farms.

## D011 — Alarm thresholds are calibrated without labels, and reported as a sweep
The per-event z cut-off is set from held-out normal training rows at a fixed baseline flag rate. No event label takes part in choosing it. The criticality counter series does not depend on the alarm threshold, so the full detection-versus-false-alarm trade-off is published as a sweep instead of a single flattering operating point. Tuning either threshold until the labelled anomalies light up would be fitting to the test set and is not permitted.

## D012 — Evidence may only accumulate while the turbine is observable
The criticality counter runs over normal-operation rows alone. Counting downtime would drain the counter through an outage, and flagging downtime rows would merely be detecting that the turbine had already stopped, which is an outcome leak rather than early detection. An event whose prediction window contains under a day of running hours is reported as **not assessable** rather than as a miss or a detection, because no early-detection signal exists in it to measure.

## D013 — Thermal inertia and trend scoring
Two changes to M2, both argued from the physics rather than from the scoreboard.

A component's temperature answers to the recent history of wind and power, not to the instantaneous reading: a turbine that has been at full load for an hour is hotter than one that has just ramped up. The predictor set therefore carries trailing 1-hour, 6-hour and 24-hour means alongside the current values. They are built once over the whole time-ordered event and then sliced, because building them on a filtered subset would roll across the gaps left by downtime and silently mix unrelated periods.

A failing component drifts hot and stays hot, while measurement noise does not, so scoring judges a trailing median of the residual rather than individual readings. The cut-off must be calibrated on that same smoothed statistic; one calibrated on raw scores sits far too high for smoothed ones, because smoothing removes the spikes that set the raw quantile.

On farm B this moved detection from 2 of 6 anomaly events to 5 of 6 at zero false alarms, with a 27.6-day median warning before failure. Smoothing also makes flags much more persistent, so the criticality counter now peaks in the hundreds rather than the tens, and the published sweep was widened to span the range where the trade-off actually turns. Both thresholds remain label-free: the whole curve is reported and the operating point is never chosen by asking which value flatters the anomaly labels.

Known limitation: sensitivity rose on normal events too. The training window ends where the prediction window begins, so seasonal drift and component ageing produce a sustained offset that looks like a slow fault. A constant offset persists exactly as a fault does, which is why the low end of the sweep carries most of the false alarms.

## D014 — Common-mode rejection tried and rejected
Hypothesis: seasonal warming and ageing lift every temperature together while a real fault lifts one, so subtracting the across-sensor median at each step should strip the drift and leave the fault. Implemented and measured on farm B, and it does not pay for itself.

It does make the one missed event detectable, reaching 6 of 6 at criticality 288. But the best operating point that raises no false alarm falls from 5 of 6 with a 27.6-day median warning to 3 of 6 with a 3.2-day warning, and 288 itself now costs 2 false alarms with warning down to 10.1 days. A three-day warning does not leave time to schedule a crane and a crew, so the headline detection count improves while the model gets less useful. A healthy turbine, event 82, rose from 195 to 848: with no fault present the median cancels the shared signal and whichever sensor merely sits offset is left looking anomalous.

Kept behind `--common-mode-rejection` for ablation, off by default, with the measured comparison in `artifacts/metrics/care_m2_wind_farm_b_cmr.json`. Recorded rather than deleted so the idea is not retried from scratch.

A rise in the raw detection count is not on its own an improvement. Warning time and false alarms decide whether the model is worth acting on, and a change is only kept when it improves the operating point as a whole.

## D015 — Farm C is the honest number
Farm B's headline did not survive contact with a larger sample, which is exactly why farm C was held back and
never tuned against. Farm B offers 6 anomaly events, so a single event moves detection by 17 points. Farm C
offers 27 anomaly events and 31 healthy ones, all of them assessable.

Reported results therefore use one threshold for every farm rather than a per-farm best. In service you deploy
a single alarm level and discover the rest; a per-farm tuned threshold quietly reports the best case as if it
were the expected one. The threshold is the most sensitive whose false-alarm rate across all healthy events
stays under 10 percent, chosen on the healthy events alone.

At that point, criticality 432: 14 of 37 anomaly events detected, 4 of 50 healthy events raising a false alarm,
and a 26.3-day median warning on the strongest farm. Per farm it is 0 of 4 on A, 5 of 6 on B and 9 of 27 on C.
The spread between B and C is wide, so the aggregate is the number to quote and the farm B figure must never be
presented on its own.

## D016 — The infrared classifier is a real CNN, judged on macro-F1
Supersedes the "weights absent" half of D007. IRNet, a small convolutional network, is trained from scratch on
the Raptor Maps Infrared Solar Modules set: 20,000 real 24x40 thermal crops in twelve classes, MIT licensed.
It is committed at `artifacts/models/ir_classifier.pt` (1.17 MB) under the weights rule in CONTRIBUTING.md.

The collection is severely imbalanced. Half of it is No-Anomaly and Diode-Multi has 175 images, so accuracy is
a misleading headline: predicting No-Anomaly for everything already scores 50 percent. Training uses
class-balanced loss, the split is stratified 70/15/15, the model is selected on validation macro-F1, and the
test split is scored exactly once.

Held-out test: macro-F1 0.608, accuracy 75.2 percent. Operationally the first question is whether a module
needs a person to look at it, and on that binary the model flags 96.1 percent of faulty modules at 85 percent
precision. The weak spots are the rare and visually similar classes: Soiling (30 test images, F1 0.30),
Hot-Spot-Multi (0.32) and Hot-Spot (0.39). Diode faults are near-perfect (0.96). These are in line with
published from-scratch results on this benchmark and are reported as measured, not rounded up.

The heatmap the technician sees is now genuine Grad-CAM over the final convolutional block. Without weights, or
with torch absent, the endpoint degrades to the original contrast check and says so in every field of the
response. A prediction remains a prompt to look, never a diagnosis.

## D017 — WebSocket support is a dependency, not a code path
The alert stream is advertised under R7 and the `/ws/{channel}` route was correct, but uvicorn ships no
WebSocket protocol implementation of its own. With neither `websockets` nor `wsproto` installed it answered
every handshake with 404, so the live alert feed silently did nothing in the venv and in the container while
the in-process test client kept passing, because Starlette's TestClient implements WebSockets itself and never
touches uvicorn's protocol layer. `websockets` is now pinned in requirements.lock.

The browser's CORS default was widened to include port 3001. Next.js moves to the next free port when 3000 is
taken, and the resulting failure is a CORS error in the console rather than anything the UI can explain, which
reads to a user as "the button is broken". Deployments should still set CORS_ORIGINS explicitly.

## D018 — The classifier refuses input it was not built for
A twelve-class softmax has no "none of these" option, so an unrelated image is not merely mis-scored: the model
is forced to name a fault. Uploading a colour photograph of a window returned No-Anomaly, and the interface
presented it exactly like a real reading. Nothing in the response revealed that the input was never solar at all.

Every image in the Raptor Maps collection is true single-channel thermal data. Measured across 400 of them the
mean per-pixel spread between RGB channels is 0.00, while an ordinary colour photograph measures in the
hundreds, so a limit of 10 separates them with an enormous margin and still tolerates JPEG chroma noise. Input
above it is refused before the model runs, with no class, no confidence and no explanation map, because a
Grad-CAM over an image that was never classified would be theatre.

Predictions below 0.30 confidence are additionally marked low confidence and name their top three candidates.
Chance is 8.3 percent across twelve classes, and a 24 percent answer is closer to guessing than to knowing;
reporting the shape of the doubt is more useful to a technician than a single dressed-up label.

This is a narrow guard, not out-of-distribution detection. A grayscale photograph of something that is not a
solar module will still pass it and be classified.
