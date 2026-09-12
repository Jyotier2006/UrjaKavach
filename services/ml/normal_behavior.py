"""R2/D008/D009: LightGBM temperature normal-behavior models (M2) for real CARE events.

A model is fit per monitored component temperature, predicting it from operating conditions only
(wind speed, power, rotational speed, ambient temperature, pitch angle). A developing thermal fault shows up
as the measured temperature running hotter than the model expects, so scoring is one-sided.

Target leakage guards (D008): the predictor set contains no component temperatures and no counters, scaling is
fit on training rows only, and the residual spread is calibrated on a chronological hold-out slice of the
training section that the regressor never saw.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from services.ml.care_loader import FarmSchema, NORMAL_STATUS_IDS
from services.ml.preprocess import TrainingPreprocessor, angle_features

MIN_TRAIN_ROWS = 200
MIN_CALIBRATION_ROWS = 20
LAG_WINDOWS = (6, 36, 144)  # 1 hour, 6 hours and 24 hours at 10-minute resolution


@dataclass
class TargetScore:
    target: str
    z: np.ndarray
    residual_scale: float


def _predictor_frame(frame: pd.DataFrame, schema: FarmSchema) -> pd.DataFrame:
    """Operating-condition predictors only, with angles as sin/cos pairs and trailing means for thermal inertia.

    A component's temperature answers to the recent history of wind and power, not just the current reading:
    a turbine that has been at full load for an hour is hotter than one that just ramped up. Without those
    trailing means the regressor cannot express the lag, and the unexplained variance inflates the residual
    spread that a developing fault has to stand out from. The windows only ever look backwards.
    """
    available = [c for c in schema.predictors if c in frame.columns]
    out = frame[available].copy()
    for col in schema.angle_cols:
        if col not in frame.columns: continue
        feats = angle_features(frame[col], name=col)
        out[feats.columns[0]], out[feats.columns[1]] = feats.iloc[:, 0], feats.iloc[:, 1]
    for col in available:
        series = frame[col]
        for window in LAG_WINDOWS:
            out[f"{col}_mean{window}"] = series.rolling(window, min_periods=1).mean()
    return out


def score_event(event: pd.DataFrame, schema: FarmSchema, calibration_fraction: float = 0.2, random_state: int = 0) -> tuple[list[TargetScore], dict]:
    """Fit one normal-behavior model per component temperature and score the whole event timeline."""
    normal_train = event[(event["train_test"] == "train") & (event["status_type_id"].isin(NORMAL_STATUS_IDS))].sort_values("time_stamp")
    if len(normal_train) < MIN_TRAIN_ROWS: raise ValueError(f"Only {len(normal_train)} normal training rows")
    split = int(len(normal_train) * (1 - calibration_fraction))
    fit_rows, calib_rows = normal_train.iloc[:split], normal_train.iloc[split:]
    if len(calib_rows) < MIN_CALIBRATION_ROWS: raise ValueError("Too few rows for residual calibration")

    # Built once over the whole time-ordered event so the trailing means are continuous, then sliced by row.
    # Slicing first would roll across the gaps left by downtime and quietly mix unrelated periods.
    full_x_frame = _predictor_frame(event, schema)
    fit_x_frame, calib_x_frame = full_x_frame.loc[fit_rows.index], full_x_frame.loc[calib_rows.index]
    pre = TrainingPreprocessor().fit(fit_x_frame)
    fit_x, calib_x, full_x = (pre.transform(f) for f in (fit_x_frame, calib_x_frame, full_x_frame))

    scores, skipped = [], []
    for target in schema.targets:
        if target not in event.columns: continue
        y_fit = pd.to_numeric(fit_rows[target], errors="coerce")
        y_calib = pd.to_numeric(calib_rows[target], errors="coerce")
        if y_fit.notna().mean() < 0.5 or y_fit.nunique() <= 1 or y_calib.notna().mean() < 0.5:
            skipped.append(target)
            continue
        model = LGBMRegressor(n_estimators=150, num_leaves=31, learning_rate=0.05, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, min_child_samples=40, random_state=random_state, verbosity=-1, n_jobs=2)
        model.fit(fit_x[y_fit.notna().to_numpy()], y_fit.dropna().to_numpy())
        scale = float(np.std(y_calib.to_numpy() - model.predict(calib_x)))
        if not np.isfinite(scale) or scale <= 1e-6:
            skipped.append(target)
            continue
        residual = pd.to_numeric(event[target], errors="coerce").to_numpy() - model.predict(full_x)
        scores.append(TargetScore(target=target, z=np.nan_to_num(residual / scale, nan=0.0, posinf=0.0, neginf=0.0), residual_scale=scale))
    if not scores: raise ValueError("No usable temperature targets")
    return scores, {"fit_rows": len(fit_rows), "calibration_rows": len(calib_rows), "targets_modelled": len(scores), "targets_skipped": len(skipped)}


def score_matrix(scores: list[TargetScore], observable: np.ndarray) -> np.ndarray:
    """Stack the per-target z scores over running hours only, as a (targets x observable) matrix."""
    return np.vstack([s.z[observable] for s in scores])


def reject_common_mode(matrix: np.ndarray) -> np.ndarray:
    """Subtract the across-sensor median at each step, leaving only deviation peculiar to one component.

    A hot summer, a drifting ambient reference or a turbine simply ageing pushes every temperature up together.
    A failing gearbox pushes the gearbox up and nothing else. Removing what the sensors are doing in unison
    therefore strips the seasonal and ageing drift that otherwise persists exactly the way a slow fault does,
    while leaving a localised fault intact. Needs enough sensors for a median to mean anything, so it is
    skipped on very small arrays.
    """
    if matrix.shape[0] < 5: return matrix
    return matrix - np.median(matrix, axis=0)


def smooth_matrix(matrix: np.ndarray, window: int) -> np.ndarray:
    """Trailing median of each target's score.

    A failing component drifts hot and stays hot, while measurement noise does not, so judging the trend rather
    than the individual reading separates the two. The median ignores isolated spikes. Downtime rows have
    already been dropped, so an outage cannot smear across the window.
    """
    return np.vstack([pd.Series(row).rolling(window, min_periods=max(2, window // 4)).median().to_numpy() for row in matrix])


def smooth_scores(scores: list[TargetScore], observable: np.ndarray, window: int) -> np.ndarray:
    return smooth_matrix(score_matrix(scores, observable), window)


def overtemperature_flags(scores: list[TargetScore], status: np.ndarray, z_threshold: float) -> tuple[list[bool], np.ndarray]:
    """A row is flagged when any monitored temperature runs hotter than expected. Non-normal statuses are never flagged."""
    stacked = np.vstack([s.z for s in scores])
    worst = stacked.max(axis=0)
    normal = np.isin(status, list(NORMAL_STATUS_IDS))
    return ((worst > z_threshold) & normal).tolist(), worst


def calibrate_threshold(values: np.ndarray, train_mask: np.ndarray, target_flag_rate: float) -> float:
    """Pick the cut-off from known-normal training rows so the baseline flag rate is fixed. Uses no event labels.

    Must be given the same statistic that will later be thresholded: a cut-off calibrated on raw scores would
    sit far too high for smoothed ones, because smoothing strips the spikes that set the raw quantile.
    """
    baseline = values[train_mask]
    baseline = baseline[np.isfinite(baseline)]
    if baseline.size == 0: raise ValueError("No baseline rows for threshold calibration")
    return float(np.quantile(baseline, 1 - target_flag_rate))
