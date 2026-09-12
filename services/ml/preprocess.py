"""R1/R2: training-only preprocessing with descriptive Avg feature selection."""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler


class TrainingPreprocessor:
    def __init__(self):
        self.columns: list[str] = []
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        self.scaler = RobustScaler()

    @staticmethod
    def clean(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.select_dtypes(include="number").replace([np.inf, -np.inf], np.nan)

    def fit(self, train: pd.DataFrame, extra_excluded: frozenset[str] = frozenset()):
        cleaned = self.clean(train)
        excluded = {"event_label", "status_type_id", "train_test", "id", "turbine_id"} | extra_excluded
        candidates = [c for c in cleaned if c not in excluded and "avg" in c.lower()]
        if not candidates: raise ValueError("No descriptive Avg features found; supply a verified feature map")
        self.columns = [c for c in candidates if cleaned[c].notna().mean() >= 0.5 and cleaned[c].nunique() > 1]
        if not self.columns: raise ValueError("No usable training features")
        self.scaler.fit(self.imputer.fit_transform(cleaned[self.columns]))
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.columns) - set(frame.columns)
        if missing: raise ValueError(f"Missing required features: {sorted(missing)}")
        return self.scaler.transform(self.imputer.transform(self.clean(frame)[self.columns]))


def angle_features(degrees: pd.Series, name: str = "pitch") -> pd.DataFrame:
    angle = np.deg2rad(degrees)
    return pd.DataFrame({f"{name}_sin": np.sin(angle), f"{name}_cos": np.cos(angle)}, index=degrees.index)
