"""R1/D007: infrared module defect classifier over the Raptor Maps Infrared Solar Modules dataset.

The images are 24x40 single-module crops in 12 classes, and the collection is severely imbalanced: half of it
is No-Anomaly while Diode-Multi holds 175 of 20,000. Accuracy is therefore a misleading headline here, because
predicting No-Anomaly for everything already scores 50 percent. Macro-F1 and per-class recall are what this
model is judged on.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

import numpy as np
import torch
from torch import nn

DATA_ROOT = Path(__file__).resolve().parents[2] / "data/raw/InfraredSolarModules"
WEIGHTS = Path(__file__).resolve().parents[2] / "artifacts/models/ir_classifier.pt"
IMAGE_SIZE = (40, 24)  # height, width, as stored

CLASSES = ("Cell", "Cell-Multi", "Cracking", "Diode", "Diode-Multi", "Hot-Spot", "Hot-Spot-Multi",
           "No-Anomaly", "Offline-Module", "Shadowing", "Soiling", "Vegetation")


class IRNet(nn.Module):
    """Small convolutional net sized for 24x40 inputs.

    Deliberately shallow: three downsampling stages already reduce a 40-pixel axis to 5, and the rarest class
    has 175 examples, so extra capacity buys overfitting rather than accuracy.
    """

    def __init__(self, num_classes: int = len(CLASSES)):
        super().__init__()
        def block(cin: int, cout: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1, bias=False),
                nn.BatchNorm2d(cout),
                nn.ReLU(),  # not in-place: Grad-CAM hooks the activation, and an in-place op would corrupt the hook
                nn.Conv2d(cout, cout, 3, padding=1, bias=False),
                nn.BatchNorm2d(cout),
                nn.ReLU(),  # not in-place: Grad-CAM hooks the activation, and an in-place op would corrupt the hook
                nn.MaxPool2d(2),
            )
        self.features = nn.Sequential(block(1, 32), block(32, 64), block(64, 128))
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


@dataclass
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def normalise(array: np.ndarray) -> np.ndarray:
    """Per-image standardisation. Infrared crops carry an arbitrary thermal offset and gain, so absolute
    pixel values say more about the camera setting than the module."""
    array = array.astype(np.float32)
    return (array - array.mean()) / (array.std() + 1e-6)


class IRClassifier:
    """Loads trained weights and classifies a single module crop."""

    def __init__(self, weights: Path = WEIGHTS, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = IRNet().to(self.device).eval()
        bundle = torch.load(weights, map_location=self.device, weights_only=True)
        self.model.load_state_dict(bundle["state_dict"])
        self.classes = tuple(bundle.get("classes", CLASSES))
        self.metrics = bundle.get("metrics", {})

    @torch.no_grad()
    def predict(self, image: np.ndarray) -> Prediction:
        tensor = torch.from_numpy(normalise(image))[None, None].to(self.device)
        probs = torch.softmax(self.model(tensor), dim=1)[0].cpu().numpy()
        index = int(probs.argmax())
        return Prediction(
            label=self.classes[index],
            confidence=float(probs[index]),
            probabilities={c: round(float(p), 4) for c, p in zip(self.classes, probs)},
        )


def available(weights: Path = WEIGHTS) -> bool:
    return weights.exists()


def load_metadata(root: Path = DATA_ROOT) -> list[tuple[Path, str]]:
    records = json.loads((root / "module_metadata.json").read_text())
    return [(root / v["image_filepath"], v["anomaly_class"]) for v in records.values()]
