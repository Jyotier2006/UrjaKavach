"""R2: CARE-style persistence, independent for every event file."""
from __future__ import annotations


def criticality_counter(predicted: list[bool], status: list[int] | None = None, farm: str = "A", threshold: int = 72) -> dict:
    if threshold < 1: raise ValueError("Threshold must be positive")
    if status is not None and len(status) != len(predicted): raise ValueError("Status and score lengths differ")
    count, counts, first_alarm, crossings = 0, [], None, []
    for i, is_anomaly in enumerate(predicted):
        old = count
        countable = farm == "A" or status is None or status[i] == 0
        if countable: count = max(0, count + (1 if is_anomaly else -1))
        counts.append(count)
        if countable and old < threshold <= count:
            crossings.append(i)
            if first_alarm is None: first_alarm = i
    return {"criticality": counts, "alarm_index": first_alarm, "crossings": crossings, "threshold": threshold}
