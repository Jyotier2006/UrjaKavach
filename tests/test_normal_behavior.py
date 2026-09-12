"""R2/D008: guards for the CARE normal-behavior model. Uses synthetic frames so the suite never needs the raw dataset."""
import numpy as np
import pandas as pd
import pytest

from services.ml.care_loader import FarmSchema
from services.ml.normal_behavior import calibrate_threshold, overtemperature_flags, reject_common_mode, score_event, smooth_scores, TargetScore
from services.ml.preprocess import TrainingPreprocessor, angle_features


def _schema():
    return FarmSchema(farm="A", targets=("gear_avg",), predictors=("wind_avg", "ambient_avg"), angle_cols=("pitch_avg",))


def _event(rows=600, fault_from=None):
    rng = np.random.default_rng(0)
    wind = rng.uniform(3, 15, rows)
    ambient = rng.uniform(5, 25, rows)
    gear = 30 + 2 * wind + 0.5 * ambient + rng.normal(0, 0.5, rows)
    if fault_from is not None: gear[fault_from:] += 15
    return pd.DataFrame({
        "time_stamp": pd.date_range("2023-01-01", periods=rows, freq="10min"),
        "asset_id": 1, "id": np.arange(rows),
        "train_test": ["train"] * (rows // 2) + ["prediction"] * (rows - rows // 2),
        "status_type_id": 0,
        "wind_avg": wind, "ambient_avg": ambient, "pitch_avg": rng.uniform(0, 90, rows), "gear_avg": gear,
    })


def test_angle_features_are_named_per_column():
    frame = angle_features(pd.Series([0.0, 90.0]), name="sensor_5_avg")
    assert list(frame.columns) == ["sensor_5_avg_sin", "sensor_5_avg_cos"]
    assert frame.iloc[1]["sensor_5_avg_sin"] == pytest.approx(1.0)


def test_preprocessor_honours_extra_exclusions():
    frame = pd.DataFrame({"a_avg": [1.0, 2, 3, 4], "b_avg": [4.0, 3, 2, 1]})
    assert TrainingPreprocessor().fit(frame).columns == ["a_avg", "b_avg"]
    assert TrainingPreprocessor().fit(frame, extra_excluded=frozenset({"b_avg"})).columns == ["a_avg"]


def test_target_is_never_a_predictor():
    """D008: a normal-behavior model must not be able to read the signal it is predicting."""
    event = _event()
    scores, meta = score_event(event, _schema())
    assert meta["targets_modelled"] == 1
    assert scores[0].target == "gear_avg"
    # A leaking model would reproduce the target exactly, collapsing the residual spread to nothing.
    assert scores[0].residual_scale > 0.1


def test_sustained_overtemperature_is_scored_but_healthy_operation_is_not():
    healthy = score_event(_event(), _schema())[0]
    faulted = score_event(_event(fault_from=400), _schema())[0]
    assert float(np.max(healthy[0].z)) < 6
    assert float(np.max(faulted[0].z)) > 10


def test_flags_ignore_rows_where_the_turbine_is_not_running():
    score = TargetScore(target="gear_avg", z=np.array([9.0, 9.0, 9.0]), residual_scale=1.0)
    flags, worst = overtemperature_flags([score], np.array([0, 4, 2]), z_threshold=3.0)
    assert flags == [True, False, True]
    assert worst.tolist() == [9.0, 9.0, 9.0]


def test_threshold_calibration_uses_training_rows_only():
    """The prediction window must not influence the cut-off, or the alarm level would move with the fault."""
    worst = np.concatenate([np.zeros(99), [100.0], np.full(50, 500.0)])
    train_mask = np.concatenate([np.ones(100, dtype=bool), np.zeros(50, dtype=bool)])
    assert calibrate_threshold(worst, train_mask, target_flag_rate=0.01) < 100.0


def test_smoothing_keeps_sustained_drift_and_drops_isolated_spikes():
    steady = TargetScore(target="t", z=np.concatenate([np.zeros(50), np.full(50, 8.0)]), residual_scale=1.0)
    spiky = TargetScore(target="t", z=np.where(np.arange(100) % 25 == 0, 40.0, 0.0), residual_scale=1.0)
    observable = np.arange(100)
    assert np.nanmax(smooth_scores([steady], observable, window=12)) == pytest.approx(8.0)
    assert np.nanmax(smooth_scores([spiky], observable, window=12)) == pytest.approx(0.0)


def test_common_mode_rejection_cancels_shared_drift_but_keeps_a_localised_fault():
    """Seasonal warming lifts every sensor together; a failing component lifts one. Only the latter should survive."""
    steps = 40
    shared_drift = np.linspace(0, 9, steps)
    matrix = np.vstack([shared_drift] * 8)
    matrix[3] += 6.0  # one component additionally running hot

    cleaned = reject_common_mode(matrix)

    assert np.abs(cleaned[[0, 1, 2, 4, 5, 6, 7]]).max() == pytest.approx(0.0, abs=1e-9)
    assert cleaned[3].min() == pytest.approx(6.0)


def test_common_mode_rejection_is_skipped_when_too_few_sensors_to_vote():
    matrix = np.array([[1.0, 2.0], [5.0, 6.0]])
    assert np.array_equal(reject_common_mode(matrix), matrix)


def test_smoothing_skips_downtime_rather_than_averaging_through_it():
    """Rows where the turbine is stopped are dropped before smoothing, never blended into the trend."""
    z = np.concatenate([np.full(20, 5.0), np.full(20, -999.0), np.full(20, 5.0)])
    observable = np.concatenate([np.arange(20), np.arange(40, 60)])
    smoothed = smooth_scores([TargetScore(target="t", z=z, residual_scale=1.0)], observable, window=8)
    assert np.nanmin(smoothed) == pytest.approx(5.0)
