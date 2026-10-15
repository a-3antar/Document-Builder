"""Non-destructive image loading and preprocessing (Pillow)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from config.constants import OCR_MAX_EDGE_PX, SUPPORTED_IMAGE_EXTENSIONS
from core.exceptions import UnsupportedImageFormatError


@dataclass(frozen=True)
class PreprocessOptions:
    auto_orient: bool = True
    rotate_degrees: int = 0          # clockwise
    grayscale: bool = True
    autocontrast: bool = True
    denoise: bool = False
    threshold: int | None = None     # 0-255 binarization
    max_edge_px: int = OCR_MAX_EDGE_PX


class ImagePreprocessor:
    """Loads images and applies preprocessing without touching the source file."""

    def load(self, path: Path) -> Image.Image:
        """Decode an image (first frame only) or raise UnsupportedImageFormatError."""
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise UnsupportedImageFormatError(
                f"'{path.name}' is not a supported image type.",
                hint="Use PNG, JPG, BMP, TIFF or WEBP.")
        try:
            with Image.open(path) as img:
                img.load()
                return img.copy()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise UnsupportedImageFormatError(
                f"'{path.name}' could not be decoded.",
                hint="The file may be damaged; try another file.") from exc

    def process(self, image: Image.Image, opts: PreprocessOptions = PreprocessOptions()) -> Image.Image:
        """Return a processed copy of the image."""
        img = ImageOps.exif_transpose(image) if opts.auto_orient else image.copy()
        img = self._flatten(img)
        if opts.rotate_degrees % 360:
            img = img.rotate(-opts.rotate_degrees, expand=True, fillcolor="white" if img.mode == "RGB" else 255)
        if max(img.size) > opts.max_edge_px:
            img.thumbnail((opts.max_edge_px, opts.max_edge_px), Image.Resampling.LANCZOS)
        if opts.grayscale or opts.threshold is not None:
            img = img.convert("L")
        if opts.autocontrast:
            img = ImageOps.autocontrast(img, cutoff=1)
        if opts.denoise:
            img = img.filter(ImageFilter.MedianFilter(3))
        if opts.threshold is not None:
            limit = opts.threshold
            img = img.point(lambda p: 255 if p > limit else 0)
        return img

    @staticmethod
    def _flatten(img: Image.Image) -> Image.Image:
        """Composite transparency on white and normalize the mode to RGB/L."""
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, "white")
            bg.paste(rgba, mask=rgba.getchannel("A"))
            return bg
        return img if img.mode in ("RGB", "L") else img.convert("RGB")