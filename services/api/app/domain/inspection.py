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

# Every image in the Raptor Maps collection is true single-channel thermal data: measured over 400 of them, the
# mean per-pixel spread between RGB channels is exactly 0.00. An ordinary colour photograph measures in the
# hundreds. Ten is therefore a wide margin that still tolerates JPEG chroma noise.
COLOUR_LIMIT = 10.0
# Twelve classes put chance at 8.3 percent. Below this the softmax is not meaningfully above guessing, so the
# response reports the shape of the doubt instead of dressing a coin flip up as a class.
LOW_CONFIDENCE = 0.30

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


def _decode(raw: bytes) -> tuple[np.ndarray, int, int, float]:
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
                colour = original.convert('RGB')
                colour.thumbnail((240, 400))
                channels = np.asarray(colour, dtype=np.float32)
                spread = float(np.mean(channels.max(axis=2) - channels.min(axis=2)))
                grey = original.convert('L')
                grey.thumbnail((240, 400))
                return np.asarray(grey, dtype=float), width, height, spread
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
    pixels, width, height, colourfulness = _decode(raw)
    spread = float(np.percentile(pixels, 95) - np.percentile(pixels, 5))
    model = _classifier()

    # A colour photograph is not thermal data. The classifier has no "not a module" class and would otherwise be
    # forced to name one of twelve, so refuse here rather than return a fabricated class for unrelated input.
    if colourfulness > COLOUR_LIMIT:
        return {
            'label': 'Not an infrared module crop',
            'confidence': None, 'probabilities': None,
            'action': 'This looks like a colour photograph rather than single-channel thermal data. Upload an infrared crop of one module, as produced by a thermal camera. The classifier is not run on unrelated images.',
            'provenance': 'User-submitted image · rejected before classification',
            'method': f'Input check: mean RGB channel spread {colourfulness:.1f}, above the {COLOUR_LIMIT:.0f} limit for thermal data',
            'heatmap': None, 'heatmap_kind': None,
            'width': width, 'height': height, 'contrast_p95_p05': round(spread, 2), 'stored': False,
        }

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
    runners = sorted(prediction.probabilities.items(), key=lambda kv: -kv[1])[:3]
    uncertain = prediction.confidence < LOW_CONFIDENCE
    if uncertain:
        action = ('The model is close to guessing on this image: ' +
                  ', '.join(f'{name} {share:.0%}' for name, share in runners) +
                  '. Treat it as unclassified and rely on your own observation.')
    elif prediction.label == 'No-Anomaly':
        action = 'No anomaly predicted. Keep the image with the inspection record.'
    else:
        action = f'Predicted {prediction.label}. Confirm against the original thermal image with a qualified technician before acting.'
    return {
        'label': f'{prediction.label} (low confidence)' if uncertain else prediction.label,
        'confidence': round(prediction.confidence, 4),
        'probabilities': prediction.probabilities,
        'uncertain': uncertain,
        'action': action,
        'provenance': 'User-submitted image · IRNet CNN trained on Raptor Maps Infrared Solar Modules',
        'method': f'12-class CNN classification (held-out test macro-F1 {macro_f1})' if macro_f1 else '12-class CNN classification',
        'heatmap': _grad_cam(model, tensor, list(model.classes).index(prediction.label), crop.shape),
        'heatmap_kind': 'Grad-CAM over the final convolutional block',
        'width': width, 'height': height, 'contrast_p95_p05': round(spread, 2), 'stored': False,
    }
