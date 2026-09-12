"""R2: loaders and per-farm schema inference for the real CARE To Compare dataset.

Every event file is independent; anonymized timestamps are never joined across events.
Column roles are inferred from each farm's own feature_description.csv, never hardcoded by sensor number,
because the anonymized numbering differs between farms.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

CARE_ROOT = Path(__file__).resolve().parents[2] / "data/raw/CARE_To_Compare"
NORMAL_STATUS_IDS = {0, 2}


@dataclass(frozen=True)
class FarmSchema:
    """Column roles for one wind farm. `targets` are monitored component temperatures; `predictors` are operating conditions."""
    farm: str
    targets: tuple[str, ...]
    predictors: tuple[str, ...]
    angle_cols: tuple[str, ...]

    def describe(self) -> str:
        return f"farm {self.farm}: {len(self.targets)} temperature targets, {len(self.predictors)} operating predictors, {len(self.angle_cols)} angle sensors"


def load_event_info(farm: str) -> pd.DataFrame:
    path = CARE_ROOT / f"Wind Farm {farm}" / "event_info.csv"
    return pd.read_csv(path, sep=";", parse_dates=["event_start", "event_end"])


def load_feature_description(farm: str) -> pd.DataFrame:
    frame = pd.read_csv(CARE_ROOT / f"Wind Farm {farm}" / "feature_description.csv", sep=";")
    frame["description"] = frame["description"].fillna("")
    return frame


def infer_schema(farm: str) -> FarmSchema:
    """Targets: component temperatures. Predictors: wind speed, power, rotational speed, ambient temperature, pitch angle.

    Other temperatures are deliberately kept out of the predictor set so a developing thermal fault cannot be
    explained away by a co-drifting neighbour sensor. Counters are excluded because they grow monotonically and
    would act as a proxy for time.
    """
    desc = load_feature_description(farm)
    desc = desc[desc["statistics_type"].fillna("").str.contains("average")]
    text = desc["description"].str.lower()
    name = desc["sensor_name"]

    is_counter = desc["is_counter"] == True
    is_angle = desc["is_angle"] == True
    is_ambient = text.str.contains("ambient")
    is_temperature = (text.str.contains("temperature") | (desc["unit"].fillna("").str.contains("C", case=True))) & ~is_ambient
    is_wind = name.str.startswith("wind_speed")
    is_power = name.str.startswith("power_")
    is_speed = desc["unit"].fillna("").str.lower().str.contains("rpm")

    def cols(mask) -> tuple[str, ...]:
        return tuple(f"{n}_avg" for n in name[mask & ~is_counter])

    targets = cols(is_temperature & ~is_angle)
    predictors = cols((is_wind | is_power | is_speed | is_ambient) & ~is_temperature)
    angle_cols = cols(is_angle)
    if not targets: raise ValueError(f"Farm {farm}: no component temperature targets found")
    if not predictors: raise ValueError(f"Farm {farm}: no operating-condition predictors found")
    return FarmSchema(farm=farm, targets=targets, predictors=predictors, angle_cols=angle_cols)


def event_ids(farm: str) -> list[int]:
    return sorted(int(f.stem) for f in (CARE_ROOT / f"Wind Farm {farm}" / "datasets").glob("*.csv"))


def load_event(farm: str, event_id: int) -> pd.DataFrame:
    path = CARE_ROOT / f"Wind Farm {farm}" / "datasets" / f"{event_id}.csv"
    return pd.read_csv(path, sep=";", parse_dates=["time_stamp"]).sort_values("time_stamp").reset_index(drop=True)
