"""UrjaKavach optional Python API. All bundled operational data is simulated."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from services.api.app import db
from services.api.app.domain.downsample import lttb
from services.api.app.domain.inspection import screen_image
from services.api.app.domain.loss import Assumptions, estimate_loss
from services.optimizer.scheduler import Job, PROFILES, demo_jobs, optimize

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / 'artifacts/demo_bundle'


def artifact(name: str):
    return json.loads((ARTIFACTS / f'{name}.json').read_text())


def scenario_or_404(scenario_id: str):
    scenario = next((s for s in artifact('scenarios') if s['id'] == scenario_id), None)
    if scenario is None: raise HTTPException(404, 'Scenario not found')
    return scenario


class Hub:
    def __init__(self): self.sockets: dict[str, set[WebSocket]] = {'alerts': set(), 'telemetry': set()}
    async def publish(self, channel: str, data: dict):
        for socket in list(self.sockets[channel]):
            try: await socket.send_json(data)
            except Exception: self.sockets[channel].discard(socket)


hub = Hub()
replay_task: asyncio.Task | None = None
escalations: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    for order in artifact('bundle')['workorders']:
        if not db.get('workorders', order['id']): db.save('workorders', order['id'], order)
    for alert in artifact('bundle')['alerts']:
        if not db.get('alerts', alert['id']): db.save('alerts', alert['id'], alert)
    yield
    if replay_task and not replay_task.done(): replay_task.cancel()
    for task in escalations: task.cancel()


if os.getenv('SENTRY_DSN'):
    import sentry_sdk
    sentry_sdk.init(dsn=os.environ['SENTRY_DSN'], traces_sample_rate=.1, send_default_pii=False)

app = FastAPI(title='UrjaKavach API', version='1.0.0', description='Optional demo API. Simulated artifacts, assumption-driven estimates and local demo roles. No production authentication.', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(','), allow_methods=['GET', 'POST', 'PUT', 'PATCH'], allow_headers=['Content-Type'], allow_credentials=False)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class AssumptionValues(StrictModel):
    capacity_mw: float = Field(2.1, ge=0, le=1000)
    capacity_factor: float = Field(.30, ge=0, le=1)
    tariff_inr_kwh: float = Field(3, ge=0, le=100)
    daily_hazard: float = Field(.08, ge=0, le=1)
    hazard_shape: float = Field(1.35, ge=.1, le=4)
    alarm_age_days: float = Field(1, ge=0, le=365)
    planned_downtime_hours: float = Field(6, ge=0, le=720)
    reactive_downtime_days: float = Field(5, ge=0, le=365)
    planned_repair_inr: float = Field(18000, ge=0, le=1e9)
    reactive_repair_inr: float = Field(250000, ge=0, le=1e9)
    derating_fraction: float = Field(.08, ge=0, le=1)
    maintenance_window_factor: float = Field(.65, ge=0, le=1)
    uncertainty_fraction: float = Field(.2, ge=0, le=1)


class LossRequest(StrictModel):
    assumptions: AssumptionValues = Field(default_factory=AssumptionValues)
    delay_days: int = Field(3, ge=0, le=90)
    horizon_days: int = Field(14, ge=1, le=90)
    draws: int = Field(1000, ge=100, le=10000)
    seed: int = Field(2026, ge=0, le=2**32 - 1)


class JobInput(StrictModel):
    id: str = Field(max_length=80)
    asset_id: str = Field(max_length=80)
    title: str = Field(max_length=200)
    skill: Literal['mechanical', 'electrical', 'solar']
    duration_hours: int = Field(ge=1, le=9)
    risk: int = Field(ge=0, le=100)
    group: Literal['wind', 'solar']
    parts_ready_hour: int = Field(0, ge=0, le=10000)
    repair_now_inr: int = Field(ge=0, le=10**9)
    delay_cost_per_day_inr: int = Field(ge=0, le=10**9)
    no_action_inr: int = Field(ge=0, le=10**9)
    min_day: int = Field(0, ge=0, le=365)
    lock_start: int | None = Field(None, ge=0, le=10000)
    lock_crew: int | None = Field(None, ge=0, le=7)


class WeatherHour(StrictModel):
    hour: int = Field(ge=0, le=336)
    wind_speed_ms: float = Field(ge=0, le=150)
    rain_mm: float = Field(0, ge=0, le=1000)


class PlanRequest(StrictModel):
    crew_count: int = Field(2, ge=1, le=4)
    horizon_days: int = Field(7, ge=1, le=14)
    profile: Literal['balanced', 'mechanical', 'electrical', 'solar'] = 'balanced'
    delay_days: int = Field(0, ge=0, le=14)
    locked: bool = False
    jobs: list[JobInput] | None = Field(None, max_length=30)
    crews: list[list[Literal['mechanical', 'electrical', 'solar']]] | None = Field(None, min_length=1, max_length=8)
    weather: list[WeatherHour] | None = Field(None, max_length=336)
    max_wind_ms: float = Field(12, ge=0, le=35)
    previous: list[dict] | None = Field(None, max_length=30)


class CheckItem(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    done: bool = False


class WorkOrder(StrictModel):
    id: str = Field(default_factory=lambda: f'WO-{uuid4().hex[:10]}', max_length=80)
    asset_id: str = Field(max_length=80)
    title: str = Field(min_length=1, max_length=250)
    status: Literal['Assigned', 'In progress', 'Awaiting review', 'Completed'] = 'Assigned'
    priority: Literal['High', 'Medium', 'Low'] = 'Medium'
    crew: str = Field('Unassigned', max_length=80)
    skill: str = Field('electrical', max_length=40)
    duration_hours: int = Field(2, ge=1, le=72)
    checklist: list[CheckItem] = Field(default_factory=list, max_length=30)
    notes: str = Field('', max_length=10000)
    provenance: str = Field('User-submitted work order', max_length=300)
    created_at: str | None = None


class WorkPatch(StrictModel):
    status: Literal['Assigned', 'In progress', 'Awaiting review', 'Completed'] | None = None
    checklist: list[CheckItem] | None = Field(None, max_length=30)
    notes: str | None = Field(None, max_length=10000)
    crew: str | None = Field(None, max_length=80)


class ReplayRequest(StrictModel):
    scenario_id: str = 'sim-gearbox-drift'
    start_step: int = Field(170, ge=0, le=287)
    interval_seconds: float = Field(.25, ge=.05, le=30)


@app.get('/health')
def health():
    with db.engine.connect() as connection:
        from sqlalchemy import text
        connection.execute(text('SELECT 1'))
    # Reported from the artifact that is actually present, so the flag cannot drift away from the truth.
    # data_mode stays 'simulated': the operational series this API serves are generated, and the CARE
    # evaluation is a separate measurement on real turbines rather than a live feed.
    try:
        from services.ml import ir_classifier
        trained_ir = ir_classifier.available()
    except ImportError:  # torch not installed: screening degrades to the contrast check
        trained_ir = False
    return {'status': 'ok', 'version': '1.0.0', 'data_mode': 'simulated', 'database': db.engine.dialect.name, 'trained_ir_model': trained_ir, 'care_evaluated': (ARTIFACTS / 'care-evaluation.json').exists()}


@app.get('/sites')
def sites(): return [artifact('bundle')['site']]


@app.get('/assets')
def assets(): return artifact('bundle')['assets']


@app.get('/assets/{asset_id}')
def asset(asset_id: str):
    result = next((a for a in assets() if a['id'] == asset_id), None)
    if result is None: raise HTTPException(404, 'Asset not found')
    return result


@app.get('/scenarios')
def scenarios(): return [{k: v for k, v in s.items() if k != 'data'} for s in artifact('scenarios')]


@app.get('/scenarios/{scenario_id}/telemetry')
def telemetry(scenario_id: str, signals: str = 'gearbox_temperature,expected_temperature', start: int = Query(0, alias='from', ge=0), end: int = Query(10000, alias='to', ge=0), max_points: int = Query(200, ge=3, le=5000)):
    scenario = scenario_or_404(scenario_id)
    if end < start: raise HTTPException(422, 'to must be greater than or equal to from')
    names = [s.strip() for s in signals.split(',')]
    allowed = {k for k, v in scenario['data'][0].items() if isinstance(v, (float, int))}
    if not names or any(n not in allowed for n in names): raise HTTPException(422, 'Unknown or nonnumeric signal')
    filtered = [p for p in scenario['data'] if start <= p['relative_minutes'] <= end]
    sampled = lttb(filtered, max_points, names[0])
    return {'scenario_id': scenario_id, 'provenance': scenario['provenance'], 'units': 'relative minutes; see artifact schema for signal units', 'total_points': len(filtered), 'data': [{k: p[k] for k in dict.fromkeys(['step', 'relative_minutes', *names])} for p in sampled]}


@app.get('/scenarios/{scenario_id}/scores')
def scores(scenario_id: str, model: Literal['B0', 'M1', 'M2', 'M3'] = 'M2'):
    if model in {'M1', 'M3'}: raise HTTPException(409, 'This model has no scored artifacts. Train and evaluate it before use.')
    s = scenario_or_404(scenario_id)
    return {'scenario_id': s['id'], 'model': model, 'provenance': s['provenance'], 'model_note': 'M2 is the Ridge prototype, not full LightGBM M2', 'threshold': s['threshold'], 'alarm_step': s['alarms'][model], 'data': [{'step': p['step'], 'score': p['scores'][model], 'criticality': p['criticality'][model]} for p in s['data']]}


@app.get('/alerts')
def alerts(state: str | None = None):
    rows = db.listing('alerts')
    return [r for r in rows if state is None or r['state'] == state]


@app.post('/alerts/{alert_id}/ack')
async def acknowledge(alert_id: str):
    row = db.get('alerts', alert_id)
    if row is None: raise HTTPException(404, 'Alert not found')
    row.update(state='Acknowledged', acknowledged_at=datetime.now(timezone.utc).isoformat())
    db.save('alerts', alert_id, row)
    db.save('alert_events', uuid4().hex, {'alert_id': alert_id, 'state': 'Acknowledged', 'time': row['acknowledged_at']})
    await hub.publish('alerts', {'type': 'acknowledged', **row})
    return row


@app.get('/alerts/{alert_id}/evidence')
def evidence(alert_id: str):
    row = db.get('alerts', alert_id)
    if row is None: raise HTTPException(404, 'Alert not found')
    if not row.get('scenario_id'): return {'title': 'Illustrative alert', 'provenance': 'Simulated', 'signals': [], 'note': 'No scored scenario is attached to this illustrative alert.'}
    s = scenario_or_404(row['scenario_id']); p = s['data'][min(row['step'], len(s['data']) - 1)]
    return {'title': 'Signals most associated with this deviation', 'provenance': s['provenance'], 'subsystem': 'gearbox', 'signals': [{'name': 'gearbox_temperature', 'actual': p['gearbox_temperature'], 'expected': p['expected_temperature'], 'residual': p['residual']}], 'expectation_contributors': s['expectation_contributors'], 'confidence': None, 'note': 'Association, not a root-cause diagnosis. Ridge coefficients, not SHAP or ARCANA.'}


@app.get('/compare')
def compare(scenario_a: str, scenario_b: str, signal: str = 'gearbox_temperature', window_a: str = '0,287', window_b: str = '0,287'):
    def window(sid, spec):
        s = scenario_or_404(sid)
        try:
            lo, hi = [int(v) for v in spec.split(',')]
            if not 0 <= lo <= hi < len(s['data']): raise ValueError()
            if signal not in s['data'][0] or not isinstance(s['data'][0][signal], (float, int)): raise ValueError()
        except ValueError: raise HTTPException(422, 'Use valid comma-separated step indices and a numeric signal')
        return {'scenario_id': sid, 'provenance': s['provenance'], 'data': [{'step': p['step'], 'value': p[signal], 'expected': p['expected_temperature'] if signal == 'gearbox_temperature' else None, 'residual': p['residual'] if signal == 'gearbox_temperature' else None} for p in s['data'][lo:hi + 1]]}
    return {'signal': signal, 'a': window(scenario_a, window_a), 'b': window(scenario_b, window_b)}


@app.get('/metrics/models')
def metrics(): return artifact('metrics')


@app.get('/metrics/solar')
def solar_metrics(): return artifact('metrics')['solar']


@app.get('/metrics/ir')
def ir_metrics(): return artifact('metrics')['ir']


@app.get('/assumptions')
def assumptions(): return db.get('settings', 'assumptions') or {'values': asdict(Assumptions()), 'provenance': 'Illustrative placeholders; operator validation required'}


@app.put('/assumptions')
def save_assumptions(values: AssumptionValues): return db.save('settings', 'assumptions', {'values': values.model_dump(), 'provenance': 'User-editable planning assumptions; not calibrated'})


@app.post('/loss/estimate')
def loss(request: LossRequest):
    try: return estimate_loss(Assumptions(**request.assumptions.model_dump()), request.delay_days, request.horizon_days, request.seed, request.draws)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@app.post('/schedule/optimize')
def schedule(request: PlanRequest):
    jobs = [Job(**j.model_dump()) for j in request.jobs] if request.jobs is not None else demo_jobs(request.delay_days, request.locked)
    crews = request.crews or PROFILES[request.profile][:request.crew_count]
    try: result = optimize(jobs, crews, request.horizon_days, request.previous, [w.model_dump() for w in request.weather] if request.weather is not None else None, request.max_wind_ms)
    except (ValueError, KeyError, TypeError) as exc: raise HTTPException(422, 'Invalid planning inputs: ' + str(exc)) from exc
    result['id'] = 'PLAN-' + uuid4().hex[:12]
    if request.weather is not None: result['provenance'] = 'User-supplied planning weather and assumed job costs; never joined to historical telemetry'
    db.save('schedules', result['id'], result)
    return result


@app.get('/schedules/{schedule_id}')
def get_schedule(schedule_id: str):
    value = db.get('schedules', schedule_id)
    if value is None: raise HTTPException(404, 'Schedule not found')
    return value


@app.get('/workorders', response_model=list[WorkOrder])
def workorders(): return db.listing('workorders')


@app.post('/workorders', response_model=WorkOrder, status_code=201)
def create_workorder(order: WorkOrder):
    asset(order.asset_id)
    if db.get('workorders', order.id): raise HTTPException(409, 'Work order ID already exists')
    if order.status != 'Assigned': raise HTTPException(422, 'New work orders must start as Assigned')
    return db.save('workorders', order.id, {**order.model_dump(), 'created_at': datetime.now(timezone.utc).isoformat()})


@app.patch('/workorders/{order_id}', response_model=WorkOrder)
def patch_workorder(order_id: str, patch: WorkPatch):
    value = db.get('workorders', order_id)
    if value is None: raise HTTPException(404, 'Work order not found')
    change = patch.model_dump(exclude_none=True)
    transitions = {'Assigned': {'Assigned', 'In progress'}, 'In progress': {'In progress', 'Awaiting review'}, 'Awaiting review': {'Awaiting review', 'In progress', 'Completed'}, 'Completed': {'Completed'}}
    if change.get('status', value['status']) not in transitions[value['status']]: raise HTTPException(409, 'Invalid work-order transition')
    result = {**value, **change}
    if result['status'] in {'Awaiting review', 'Completed'} and (not result['checklist'] or not all(c['done'] for c in result['checklist'])): raise HTTPException(422, 'Complete the checklist before review or completion')
    db.save('workorders', order_id, result)
    return result


@app.get('/solar/inverters')
def solar_inverters(): return artifact('solar')['inverters']


@app.get('/solar/performance')
def solar_performance(): return artifact('solar')


@app.post('/solar/ir/classify')
async def classify(file: UploadFile = File(...)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    try: return await asyncio.to_thread(screen_image, raw)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    finally: await file.close()


@app.get('/forecast')
async def forecast(latitude: float = Query(23.2, ge=-90, le=90), longitude: float = Query(69.6, ge=-180, le=180), days: int = Query(7, ge=1, le=14)):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get('https://api.open-meteo.com/v1/forecast', params={'latitude': latitude, 'longitude': longitude, 'hourly': 'wind_speed_10m,rain', 'wind_speed_unit': 'ms', 'forecast_days': days, 'timezone': 'UTC'})
            r.raise_for_status(); data = r.json()
    except (httpx.HTTPError, ValueError): raise HTTPException(503, 'Forecast unavailable. No synthetic weather has been substituted.')
    hourly = data['hourly']
    return {'source': 'Open-Meteo', 'url': 'https://open-meteo.com/', 'provenance': 'Current forecast · planning only', 'timezone': 'UTC', 'note': '10 m forecast wind is not a hub-height measurement. Apply site safety rules.', 'weather': [{'hour': i, 'time': t, 'wind_speed_ms': hourly['wind_speed_10m'][i], 'rain_mm': hourly['rain'][i]} for i, t in enumerate(hourly['time'])]}


async def notify_external(message: str):
    # Only an explicitly configured incoming webhook can send notifications.
    url = os.getenv('SLACK_WEBHOOK_URL')
    if not url: return {'delivered': False, 'reason': 'Webhook not configured'}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(url, json={'text': message}); response.raise_for_status()
        return {'delivered': True}
    except httpx.HTTPError: return {'delivered': False, 'reason': 'Webhook delivery failed'}


async def escalate(alert_id: str):
    await asyncio.sleep(float(os.getenv('ALERT_ESCALATION_SECONDS', '60')))
    row = db.get('alerts', alert_id)
    if not row or row['state'] in {'Acknowledged', 'Resolved'}: return
    row.update(severity='Critical', state='Critical', escalation=True)
    db.save('alerts', alert_id, row)
    await hub.publish('alerts', {'type': 'alert', **row})
    delivery = await notify_external(f"[SIMULATED] Escalation: {row['asset_id']} · {row['title']} · acknowledgement required")
    db.save('alert_events', uuid4().hex, {'alert_id': alert_id, 'type': 'escalation', 'delivery': delivery})


async def ingest_point(scenario_id: str, step: int):
    s = scenario_or_404(scenario_id)
    if not 0 <= step < len(s['data']): raise HTTPException(422, 'Step out of range')
    point = s['data'][step]
    event = {'type': 'telemetry', 'scenario_id': scenario_id, 'asset_id': s['asset_id'], 'provenance': s['provenance'], 'scoring_mode': 'Precomputed score aligned by relative step', 'point': point}
    db.save('telemetry', f'{scenario_id}:{step}', event)
    await hub.publish('telemetry', event)
    if s['alarms']['M2'] is not None and step == s['alarms']['M2']:
        alert_id = f'STREAM-{scenario_id}'
        if not db.get('alerts', alert_id):
            row = {'id': alert_id, 'asset_id': s['asset_id'], 'title': 'Persistent gearbox temperature deviation', 'detail': 'Ridge prototype criticality crossed the warning threshold.', 'severity': 'Warning', 'state': 'Warning', 'subsystem': 'gearbox', 'scenario_id': scenario_id, 'step': step, 'provenance': s['provenance']}
            db.save('alerts', alert_id, row)
            await hub.publish('alerts', {'type': 'alert', **row})
            delivery = await notify_external(f"[SIMULATED] Warning: {row['asset_id']} · {row['title']}")
            db.save('alert_events', uuid4().hex, {'alert_id': alert_id, 'type': 'warning', 'delivery': delivery})
            task = asyncio.create_task(escalate(alert_id)); escalations.add(task); task.add_done_callback(escalations.discard)
    return event


class IngestRequest(StrictModel):
    scenario_id: str
    step: int = Field(ge=0, le=100000)


@app.post('/ingest/replay')
async def ingest(request: IngestRequest): return await ingest_point(request.scenario_id, request.step)


async def run_replay(request: ReplayRequest):
    s = scenario_or_404(request.scenario_id)
    for step in range(request.start_step, len(s['data'])):
        await ingest_point(request.scenario_id, step)
        await asyncio.sleep(request.interval_seconds)


@app.post('/replay/start')
async def start_replay(request: ReplayRequest):
    global replay_task
    scenario_or_404(request.scenario_id)
    if replay_task and not replay_task.done(): replay_task.cancel()
    replay_task = asyncio.create_task(run_replay(request))
    return {'status': 'started', 'provenance': 'Simulated', **request.model_dump()}


@app.post('/replay/stop')
async def stop_replay():
    if replay_task and not replay_task.done(): replay_task.cancel()
    return {'status': 'stopped'}


@app.websocket('/ws/{channel}')
async def websocket(socket: WebSocket, channel: str):
    if channel not in hub.sockets: await socket.close(code=1008); return
    await socket.accept(); hub.sockets[channel].add(socket)
    try:
        await socket.send_json({'type': 'connected', 'channel': channel, 'provenance': 'Simulated'})
        while True: await socket.receive_text()
    except WebSocketDisconnect: pass
    finally: hub.sockets[channel].discard(socket)

