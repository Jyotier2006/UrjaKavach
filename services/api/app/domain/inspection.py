"""R1/R6: image quality screening; deliberately NOT a trained IR classifier."""
import base64
from io import BytesIO
import warnings
import numpy as np
from PIL import Image, UnidentifiedImageError


def screen_image(raw: bytes) -> dict:
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
                grey = original.convert('L'); grey.thumbnail((240, 400))
                pixels = np.asarray(grey, dtype=float)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Could not decode a supported image') from exc
    spread = float(np.percentile(pixels, 95) - np.percentile(pixels, 5))
    label = 'Low image contrast' if spread < 20 else 'Image ready for manual review'
    intensity = pixels / 255
    color = np.stack([np.minimum(1, intensity * 2), np.clip(intensity * 2 - .5, 0, 1), np.clip(.65 - intensity, 0, 1)], axis=-1)
    out = BytesIO(); Image.fromarray((color * 255).astype('uint8')).save(out, format='PNG')
    return {'label': label, 'confidence': None, 'probabilities': None, 'action': 'Review the original thermal image and acquisition conditions with a qualified technician. Pixel brightness alone cannot determine a defect.', 'provenance': 'User-submitted image · unvalidated image-quality screening', 'method': 'Grayscale contrast check; not CNN classification', 'heatmap': 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode(), 'heatmap_kind': 'Pixel intensity map, not Grad-CAM', 'width': width, 'height': height, 'contrast_p95_p05': round(spread, 2), 'stored': False}

