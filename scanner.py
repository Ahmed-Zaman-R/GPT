"""Local document enhancement and PDF output; no network services required."""
from pathlib import Path
import os
import tempfile

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def load_image(path):
    with Image.open(path) as image:
        image.seek(0)
        return ImageOps.exif_transpose(image).convert('RGB')


def enhance(image, mode='Clean gray', strength=75):
    if mode == 'Original':
        return image.convert('RGB').copy()
    gray = ImageOps.grayscale(image)
    # Estimate broad illumination on a small copy, then remove shadows by division.
    small = gray.copy()
    small.thumbnail((700, 700))
    background = small.filter(ImageFilter.GaussianBlur(25)).resize(gray.size, Image.Resampling.BILINEAR)
    pixels = np.asarray(gray, dtype=np.float32)
    illumination = np.maximum(np.asarray(background, dtype=np.float32), 1)
    corrected = np.clip(pixels / illumination * 245, 0, 255)
    amount = max(0, min(100, strength)) / 100
    cleaned = pixels * (1 - amount) + corrected * amount
    cleaned = np.clip((cleaned - 18) * 255 / 222, 0, 255).astype('uint8')
    if mode == 'Black & white':
        cleaned = np.where(cleaned > 165, 255, 0).astype('uint8')
    return Image.fromarray(cleaned).convert('RGB')


def export_pdf(images, destination, paper='A4'):
    """Write atomically so a failed export cannot destroy an existing PDF."""
    if not images:
        raise ValueError('Import at least one page before exporting.')
    pages = []
    try:
        for image in images:
            if paper == 'Image size':
                pages.append(image.convert('RGB'))
            else:
                size = (2480, 3508) if paper == 'A4' else (2550, 3300)
                sheet = Image.new('RGB', size, 'white')
                fitted = ImageOps.contain(image, (size[0] - 160, size[1] - 160))
                sheet.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
                pages.append(sheet)
        target = Path(destination)
        fd, temporary = tempfile.mkstemp(suffix='.pdf', dir=target.parent)
        os.close(fd)
        try:
            pages[0].save(temporary, 'PDF', save_all=True, append_images=pages[1:], resolution=300)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    finally:
        for page in pages:
            page.close()
