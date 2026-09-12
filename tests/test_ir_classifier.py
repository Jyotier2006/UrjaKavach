"""R1/D007: guards for the infrared classifier and the screening fallback. Needs neither the dataset nor weights."""
from io import BytesIO

import numpy as np
import pytest
import torch
from PIL import Image

from services.api.app.domain import inspection
from services.ml.ir_classifier import CLASSES, IRNet, normalise


def _png(width=24, height=40, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    out = BytesIO()
    Image.fromarray(rng.integers(40, 200, (height, width), dtype=np.uint8), mode="L").save(out, format="PNG")
    return out.getvalue()


def test_network_maps_a_module_crop_to_twelve_class_logits():
    logits = IRNet().eval()(torch.zeros(3, 1, 40, 24))
    assert logits.shape == (3, len(CLASSES))


def test_normalisation_removes_thermal_offset_and_gain():
    """Two crops of the same module at different camera settings must look identical to the model."""
    base = np.random.default_rng(1).uniform(0, 1, (40, 24)).astype(np.float32)
    hot, cold = base * 90 + 120, base * 20 + 30
    assert np.allclose(normalise(hot), normalise(cold), atol=1e-4)


def test_screening_without_weights_never_claims_a_diagnosis(monkeypatch):
    """D007: with no trained model the response must not carry a class probability or call its map Grad-CAM."""
    monkeypatch.setattr(inspection, "_classifier", lambda: None)
    result = inspection.screen_image(_png())
    assert result["confidence"] is None and result["probabilities"] is None
    assert "not CNN" in result["method"]
    assert "not Grad-CAM" in result["heatmap_kind"]
    assert result["heatmap"].startswith("data:image/png;base64,")


def test_screening_with_a_model_reports_class_confidence_and_grad_cam(monkeypatch):
    class Stub:
        classes = CLASSES
        metrics = {"test": {"macro_f1": 0.5}}
        model = IRNet().eval()

        def predict(self, image):
            probs = np.full(len(CLASSES), 1 / len(CLASSES))
            return type("P", (), {"label": CLASSES[3], "confidence": float(probs[3]),
                                  "probabilities": {c: float(p) for c, p in zip(CLASSES, probs)}})()

    monkeypatch.setattr(inspection, "_classifier", lambda: Stub())
    result = inspection.screen_image(_png(width=120, height=200))
    assert result["label"] == CLASSES[3]
    assert result["confidence"] == pytest.approx(1 / len(CLASSES), abs=1e-4)  # the API rounds to 4 dp
    assert result["heatmap_kind"].startswith("Grad-CAM")
    assert result["heatmap"].startswith("data:image/png;base64,")
    assert "0.5" in result["method"]


def test_oversized_and_undecodable_uploads_are_rejected():
    with pytest.raises(ValueError, match="5 MB"):
        inspection.screen_image(b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="decode"):
        inspection.screen_image(b"not an image at all")
