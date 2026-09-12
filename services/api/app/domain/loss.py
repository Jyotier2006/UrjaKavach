"""R5: reproducible scenario estimates. No fitted failure probability is claimed."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Assumptions:
    capacity_mw: float = 2.1
    capacity_factor: float = 0.30
    tariff_inr_kwh: float = 3.0
    daily_hazard: float = 0.08
    hazard_shape: float = 1.35
    alarm_age_days: float = 1.0
    planned_downtime_hours: float = 6.0
    reactive_downtime_days: float = 5.0
    planned_repair_inr: float = 18000.0
    reactive_repair_inr: float = 250000.0
    derating_fraction: float = 0.08
    maintenance_window_factor: float = 0.65
    uncertainty_fraction: float = 0.20

    def validate(self) -> None:
        values = asdict(self)
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError("All assumptions must be finite")
        if any(v < 0 for v in values.values()):
            raise ValueError("Assumptions cannot be negative")
        for key in ["capacity_factor", "derating_fraction", "maintenance_window_factor", "uncertainty_fraction"]:
            if values[key] > 1:
                raise ValueError(f"{key} must be between zero and one")
        if self.capacity_mw > 1000 or self.tariff_inr_kwh > 100 or self.daily_hazard > 1:
            raise ValueError("Assumption exceeds supported scenario range")


def probability_of_failure(delay_days: float, a: Assumptions) -> float:
    """Conditional future probability given survival to the current alarm age."""
    a.validate()
    if not math.isfinite(delay_days) or delay_days < 0:
        raise ValueError("Delay must be finite and nonnegative")
    increment = (a.alarm_age_days + delay_days) ** a.hazard_shape - a.alarm_age_days ** a.hazard_shape
    return -math.expm1(-a.daily_hazard * increment)


def expected_daily_energy_kwh(a: Assumptions) -> float:
    a.validate()
    return a.capacity_mw * 1000 * 24 * a.capacity_factor


def _quantiles(samples: np.ndarray) -> dict:
    q = np.quantile(samples, [0.1, 0.5, 0.9])
    return {"p10": round(float(q[0]), 2), "p50": round(float(q[1]), 2), "p90": round(float(q[2]), 2)}


def estimate_loss(a: Assumptions, delay_days: int = 3, horizon_days: int = 14, seed: int = 2026, draws: int = 1000) -> dict:
    a.validate()
    if not 0 <= delay_days <= horizon_days <= 90 or not 100 <= draws <= 10000:
        raise ValueError("Use 0 ≤ delay ≤ horizon ≤ 90 and 100–10000 draws")
    rng = np.random.default_rng(seed)
    # Common random draws make all scenario comparisons internally consistent.
    spread = a.uncertainty_fraction
    multipliers = rng.lognormal(-0.5 * spread**2, spread, size=(5, draws))
    daily = expected_daily_energy_kwh(a) * multipliers[0]
    tariff = a.tariff_inr_kwh * multipliers[1]
    planned_repair = a.planned_repair_inr * multipliers[2]
    reactive_repair = a.reactive_repair_inr * multipliers[3]
    hazard = a.daily_hazard * multipliers[4]
    reactive = a.reactive_downtime_days * daily * tariff + reactive_repair
    planned_energy = daily / 24 * a.planned_downtime_hours * a.maintenance_window_factor
    planned = planned_energy * tariff + planned_repair
    curve, distributions = [], []
    for delay in range(horizon_days + 1):
        increment = (a.alarm_age_days + delay) ** a.hazard_shape - a.alarm_age_days ** a.hazard_shape
        fail = -np.expm1(-hazard * increment)
        # Conservative derating until repair; the convention is exposed in the UI.
        derating = delay * daily * tariff * a.derating_fraction
        loss = fail * reactive + (1 - fail) * planned + derating
        distributions.append(loss)
        curve.append({"day": delay, **_quantiles(loss), "failure_probability": round(probability_of_failure(delay, a), 5)})
    increment = (a.alarm_age_days + horizon_days) ** a.hazard_shape - a.alarm_age_days ** a.hazard_shape
    fail_horizon = -np.expm1(-hazard * increment)
    no_action = fail_horizon * reactive + horizon_days * daily * tariff * a.derating_fraction
    return {
        "kind": "estimate", "provenance": "Simulated assumptions; not calibrated on CARE",
        "assumptions": asdict(a), "delay_days": delay_days, "horizon_days": horizon_days,
        "daily_energy_kwh": round(expected_daily_energy_kwh(a), 2),
        "repair_now": _quantiles(distributions[0]), "repair_delayed": _quantiles(distributions[delay_days]),
        "no_action": _quantiles(no_action), "avoided_loss": _quantiles(no_action - distributions[0]),
        "delay_penalty": _quantiles(distributions[delay_days] - distributions[0]),
        "curve": curve, "seed": seed, "draws": draws,
        "formula": "P_fail(d) × (reactive downtime × daily energy × tariff + reactive repair) + (1 − P_fail(d)) × (planned window energy × tariff + planned repair) + derating loss",
        "uncertainty": "P10/P50/P90 quantify the stated assumption distribution; they are not calibrated predictive confidence bounds.",
    }
