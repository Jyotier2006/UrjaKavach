"""R4: time-indexed CP-SAT scheduling with explicit infeasibility reasons."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from itertools import combinations
import time
from ortools.sat.python import cp_model


@dataclass
class Job:
    id: str
    asset_id: str
    title: str
    skill: str
    duration_hours: int
    risk: int
    group: str
    parts_ready_hour: int
    repair_now_inr: int
    delay_cost_per_day_inr: int
    no_action_inr: int
    min_day: int = 0
    lock_start: int | None = None
    lock_crew: int | None = None


PROFILES = {
    "balanced": [["mechanical", "electrical", "solar"], ["electrical", "solar"], ["mechanical", "solar"], ["mechanical", "electrical", "solar"]],
    "mechanical": [["mechanical"]] * 4,
    "electrical": [["electrical"]] * 4,
    "solar": [["solar"]] * 4,
}


def demo_jobs(delay: int = 0, lock: bool = False) -> list[Job]:
    return [
        Job("J-101", "T-03", "Gearbox inspection", "mechanical", 4, 91, "wind", 0, 18000, 39000, 320000, delay, 10 if lock else None, 0 if lock else None),
        Job("J-102", "S-02", "Panel cleaning", "solar", 3, 64, "solar", 0, 4500, 8500, 88000),
        Job("J-103", "T-06", "Electrical inspection", "electrical", 3, 73, "wind", 10, 12000, 18000, 188000),
        Job("J-104", "S-04", "Inverter diagnostic", "electrical", 2, 57, "solar", 24, 8000, 11000, 117000),
        Job("J-105", "T-02", "Pitch system service", "mechanical", 3, 35, "wind", 48, 14000, 4000, 51000),
        Job("J-106", "S-03", "Connector inspection", "electrical", 2, 42, "solar", 144, 6000, 5000, 65000),
    ]


def access_open(job: Job, hour: int, weather: list[dict] | None = None, max_wind: float = 12.0) -> bool:
    day, local_hour = divmod(hour, 24)
    if not 8 <= local_hour or local_hour + job.duration_hours > 17:
        return False
    if hour < job.parts_ready_hour or day < job.min_day:
        return False
    # Deterministic hypothetical access forecast; NEVER joined to historical SCADA.
    if weather is None:
        return not (job.group == "wind" and day == 1 and local_hour < 12) and not (job.skill == "solar" and day == 2)
    for h in range(hour, hour + job.duration_hours):
        forecast = next((w for w in weather if w["hour"] == h), None)
        if forecast is None: return False
        if job.group == "wind" and forecast["wind_speed_ms"] > max_wind: return False
        if job.skill == "solar" and forecast.get("rain_mm", 0) > 0: return False
    return True


def start_cost(job: Job, hour: int, crew_hourly_inr: int = 450) -> int:
    return round(job.repair_now_inr + job.delay_cost_per_day_inr * hour / 24 + job.duration_hours * crew_hourly_inr)


def _reason(job: Job, crews: list[list[str]], horizon: int, starts: list[int]) -> str:
    if job.lock_crew is not None and job.lock_crew >= len(crews): return "Locked crew is unavailable"
    if not any(job.skill in c for c in crews): return f"No crew with {job.skill} skill"
    if job.parts_ready_hour >= horizon * 24: return "Parts arrive after this planning horizon"
    if job.min_day >= horizon: return "Requested delay is outside the horizon"
    if job.lock_start is not None and job.lock_start not in starts: return "Locked time conflicts with access, delay or parts readiness"
    if not starts: return "No safe access window within the horizon"
    return "Crew capacity or a locked job prevents assignment"


def _summarize(jobs: list[Job], assignments: list[dict], crews: list[list[str]], horizon: int, starts: dict[str, list[int]]) -> dict:
    assigned = {a["job_id"] for a in assignments}
    total = sum(a["expected_loss_inr"] for a in assignments) + sum(j.no_action_inr for j in jobs if j.id not in assigned)
    baseline = sum(j.no_action_inr for j in jobs)
    risks = sum(j.risk for j in jobs)
    return {
        "items": sorted(assignments, key=lambda a: (a["crew"], a["start_hour"])),
        "unscheduled": [{"job_id": j.id, "asset_id": j.asset_id, "title": j.title, "reason": _reason(j, crews, horizon, starts[j.id])} for j in jobs if j.id not in assigned],
        "expected_loss_inr": total, "loss_avoided_inr": baseline - total,
        "risk_covered_pct": round(100 * sum(j.risk for j in jobs if j.id in assigned) / risks, 1) if risks else 0,
        "crew_utilization_pct": round(100 * sum(a["duration_hours"] for a in assignments) / (len(crews) * horizon * 9), 1),
    }


def _item(job: Job, crew: int, start: int) -> dict:
    return {"job_id": job.id, "asset_id": job.asset_id, "title": job.title, "crew": crew, "start_hour": start, "end_hour": start + job.duration_hours, "duration_hours": job.duration_hours, "skill": job.skill, "group": job.group, "risk": job.risk, "locked": job.lock_start is not None, "expected_loss_inr": start_cost(job, start)}


def greedy(jobs: list[Job], crews: list[list[str]], horizon: int, starts: dict[str, list[int]], calendar: bool = False) -> dict:
    items = []
    # Locks are respected by all policies; calendar follows the fixed input order.
    ordered = sorted(jobs, key=lambda j: (j.lock_start is None, jobs.index(j) if calendar else -j.risk))
    for job in ordered:
        found = False
        for start in starts[job.id]:
            if job.lock_start is not None and start != job.lock_start: continue
            for crew, skills in enumerate(crews):
                if job.skill not in skills or (job.lock_crew is not None and job.lock_crew != crew): continue
                if any(a["crew"] == crew and not (start >= a["end_hour"] + (a["group"] != job.group) or start + job.duration_hours + (a["group"] != job.group) <= a["start_hour"]) for a in items): continue
                items.append(_item(job, crew, start)); found = True; break
            if found: break
    return _summarize(jobs, items, crews, horizon, starts)


def optimize(jobs: list[Job], crews: list[list[str]], horizon: int = 7, previous: list[dict] | None = None, weather: list[dict] | None = None, max_wind: float = 12, limit_seconds: float = 1.2) -> dict:
    if not 1 <= len(crews) <= 8 or not 1 <= horizon <= 14 or len(jobs) > 30:
        raise ValueError("Supported demo size: 1–8 crews, 1–14 days, at most 30 jobs")
    if len({j.id for j in jobs}) != len(jobs): raise ValueError("Job IDs must be unique")
    for j in jobs:
        if not 1 <= j.duration_hours <= 9 or not 0 <= j.risk <= 100: raise ValueError("Invalid job duration or risk")
    started = time.perf_counter()
    starts = {j.id: [h for h in range(horizon * 24) if access_open(j, h, weather, max_wind)] for j in jobs}
    model = cp_model.CpModel()
    variables, crew_intervals, objectives = {}, [[] for _ in crews], []
    for job in jobs:
        valid = starts[job.id]
        eligible = [c for c, skills in enumerate(crews) if job.skill in skills and (job.lock_crew is None or c == job.lock_crew)]
        if job.lock_start is not None: valid = [h for h in valid if h == job.lock_start]
        if not valid or not eligible: continue
        start = model.new_int_var_from_domain(cp_model.Domain.from_values(valid), f"start_{job.id}")
        end = model.new_int_var(0, horizon * 24 + 9, f"end_{job.id}")
        model.add(end == start + job.duration_hours)
        scheduled = model.new_bool_var(f"scheduled_{job.id}")
        choices = {}
        for c in eligible:
            present = model.new_bool_var(f"crew_{c}_{job.id}")
            interval = model.new_optional_interval_var(start, job.duration_hours, end, present, f"interval_{c}_{job.id}")
            crew_intervals[c].append(interval); choices[c] = present
        model.add(sum(choices.values()) == scheduled)
        if job.lock_start is not None: model.add(scheduled == 1)
        table = [start_cost(job, h) for h in range(horizon * 24)]
        cost = model.new_int_var(0, max(table), f"cost_{job.id}")
        model.add_element(start, table, cost)
        effective = model.new_int_var(0, max(max(table), job.no_action_inr + job.risk * 1000), f"effective_{job.id}")
        model.add(effective == cost).only_enforce_if(scheduled)
        model.add(effective == job.no_action_inr + job.risk * 1000).only_enforce_if(scheduled.Not())
        objectives.append(effective)
        variables[job.id] = (job, start, end, scheduled, choices)
    for intervals in crew_intervals: model.add_no_overlap(intervals)
    # One-hour transfer between wind and solar groups, only if both jobs use the crew.
    for a, b in combinations(variables.values(), 2):
        if a[0].group == b[0].group: continue
        for crew in set(a[4]) & set(b[4]):
            order = model.new_bool_var(f"before_{a[0].id}_{b[0].id}_{crew}")
            model.add(a[2] + 1 <= b[1]).only_enforce_if([a[4][crew], b[4][crew], order])
            model.add(b[2] + 1 <= a[1]).only_enforce_if([a[4][crew], b[4][crew], order.Not()])
    model.minimize(sum(objectives))
    solver = cp_model.CpSolver(); solver.parameters.max_time_in_seconds = limit_seconds
    solver.parameters.num_search_workers = 1; solver.parameters.random_seed = 2026
    status = solver.solve(model)
    assignments = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for job, start, end, scheduled, choices in variables.values():
            if solver.value(scheduled):
                crew = next(c for c, present in choices.items() if solver.value(present))
                assignments.append(_item(job, crew, solver.value(start)))
    result = _summarize(jobs, assignments, crews, horizon, starts)
    old = {a["job_id"]: a for a in previous or []}
    changes = []
    for item in assignments:
        before = old.get(item["job_id"])
        if before is None: changes.append(f"{item['asset_id']} assigned to Crew {item['crew'] + 1}, day {item['start_hour'] // 24 + 1}.")
        elif before["crew"] != item["crew"] or before["start_hour"] != item["start_hour"]:
            changes.append(f"{item['asset_id']} moved from Crew {before['crew'] + 1}, day {before['start_hour'] // 24 + 1} to Crew {item['crew'] + 1}, day {item['start_hour'] // 24 + 1}.")
    for removed in set(old) - {a["job_id"] for a in assignments}: changes.append(f"{old[removed]['asset_id']} is now unscheduled.")
    result.update({"solver": "OR-Tools CP-SAT", "solver_status": solver.status_name(status), "optimal": status == cp_model.OPTIMAL, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "horizon_days": horizon, "crew_count": len(crews), "changes": changes, "jobs": [asdict(j) for j in jobs], "baselines": {"risk_first": greedy(jobs, crews, horizon, starts), "calendar": greedy(jobs, crews, horizon, starts, calendar=True)}, "kind": "estimate", "provenance": "Simulated jobs, access windows and costs"})
    return result
