"""R1/R6/D007: infrared module screening.

Two modes, and the response always says which one produced it.

With trained weights present, a CNN classifies the crop into the twelve Raptor Maps classes and the returned
heatmap is a real Grad-CAM over the layer the prediction came from. Without them, this falls back to a
grayscale contrast check that reports image quality only, carries no class probability, and returns a plain
intensity map that is explicitly not Grad-CAM. The fallback must never be dressed up as a diagnosis.
"""
import base64
from io import BytesIO
import warnings

import numpy as np
from PIL import Image, UnidentifiedImageError

_model = None


def _classifier():
    """Loaded once on first use. Missing weights, or a torch-less install, both mean the fallback path rather
    than a failed request, so the import happens here and not at module load."""
    global _model
    if _model is not None:
        return _model
    try:
        from services.ml import ir_classifier
    except ImportError:
        return None
    if not ir_classifier.available():
        return None
    try:
        _model = ir_classifier.IRClassifier()
    except Exception:
        return None
    return _model


def _decode(raw: bytes) -> tuple[np.ndarray, int, int]:
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('Image must be smaller than 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                if original.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ValueError('Only PNG, JPEG and WebP images are supported')
                if original.width * original.height > 16_000_000:
                    raise ValueError('Image exceeds the 16 megapixel limit')
                width, height = original.size
                grey = original.convert('L')
                grey.thumbnail((240, 400))
                return np.asarray(grey, dtype=float), width, height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Could not decode a supported image') from exc


def _as_png(array: np.ndarray) -> str:
    out = BytesIO()
    Image.fromarray((np.clip(array, 0, 1) * 255).astype('uint8')).save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


def _intensity_map(pixels: np.ndarray) -> str:
    intensity = pixels / 255
    colour = np.stack([np.minimum(1, intensity * 2), np.clip(intensity * 2 - .5, 0, 1), np.clip(.65 - intensity, 0, 1)], axis=-1)
    return _as_png(colour)


def _grad_cam(model, tensor, target: int, shape: tuple[int, int]) -> str:
    """Grad-CAM over the last convolutional block: activations weighted by the gradient of the winning class."""
    import torch
    activations, gradients = {}, {}
    layer = model.model.features[-1][-2]  # final ReLU before the last pool
    handles = [
        layer.register_forward_hook(lambda _m, _i, o: activations.__setitem__('v', o.detach())),
        layer.register_full_backward_hook(lambda _m, _gi, go: gradients.__setitem__('v', go[0].detach())),
    ]
    try:
        model.model.zero_grad()
        logits = model.model(tensor)
        logits[0, target].backward()
        weights = gradients['v'].mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * activations['v']).sum(dim=1, keepdim=True))
        cam = torch.nn.functional.interpolate(cam, size=shape, mode='bilinear', align_corners=False)[0, 0]
        cam = cam - cam.min()
        cam = (cam / cam.max()).cpu().numpy() if float(cam.max()) > 0 else cam.cpu().numpy()
    finally:
        for handle in handles:
            handle.remove()
    colour = np.stack([np.minimum(1, cam * 2), np.clip(cam * 2 - .5, 0, 1), np.clip(.65 - cam, 0, 1)], axis=-1)
    return _as_png(colour)


def screen_image(raw: bytes) -> dict:
    pixels, width, height = _decode(raw)
    spread = float(np.percentile(pixels, 95) - np.percentile(pixels, 5))
    model = _classifier()

    if model is None:
        return {
            'label': 'Low image contrast' if spread < 20 else 'Image ready for manual review',
            'confidence': None, 'probabilities': None,
            'action': 'Review the original thermal image and acquisition conditions with a qualified technician. Pixel brightness alone cannot determine a defect.',
            'provenance': 'User-submitted image · unvalidated image-quality screening',
            'method': 'Grayscale contrast check; not CNN classification',
            'heatmap': _intensity_map(pixels), 'heatmap_kind': 'Pixel intensity map, not Grad-CAM',
            'width': width, 'height': height, 'contrast_p95_p05': round(spread, 2), 'stored': False,
        }

    import torch
    from services.ml import ir_classifier
    # The model was trained on 24x40 single-module crops, so anything else is resized to match.
    crop = np.asarray(Image.fromarray(pixels.astype('uint8')).resize((24, 40), Image.BILINEAR), dtype=np.float32)
    tensor = torch.from_numpy(ir_classifier.normalise(crop))[None, None]
    prediction = model.predict(crop)
    macro_f1 = (model.metrics.get('test') or {}).get('macro_f1')
    return {
        'label': prediction.label,
        'confidence': round(prediction.confidence, 4),
        'probabilities': prediction.probabilities,
        'action': ('No anomaly predicted. Keep the image with the inspection record.' if prediction.label == 'No-Anomaly'
                   else f'Predicted {prediction.label}. Confirm against the original thermal image with a qualified technician before acting.'),
        'provenance': 'User-submitted image · IRNet CNN trained on Raptor Maps Infrared Solar Modules',
        'method': f'12-class CNN classification (held-out test macro-F1 {macro_f1})' if macro_f1 else '12-class CNN classification',
        'heatmap': _grad_cam(model, tensor, list(model.classes).index(prediction.label), crop.shape),
        'heatmap_kind': 'Grad-CAM over the final convolutional block',
        'width': width, 'height': height, 'contrast_p95_p05': round(spread, 2), 'stored': False,
    }
