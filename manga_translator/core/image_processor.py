"""
Image processing utilities for Manga Translator.
Handles rendering translated text onto images and inpainting.
"""

from typing import List, Optional, Tuple
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from manga_translator.core.ocr import TextRegion
from manga_translator.core.translator import TranslationResult
from manga_translator.core.logger import get_logger


class ImageProcessor:
    """Processes images for translation overlay rendering."""

    def __init__(self):
        self.logger = get_logger("ImageProcessor")

    def load_image(self, path: Path, auto_rotate: bool = True, max_size: int = 4096) -> Image.Image:
        """Load an image with optional auto-rotate and downscale."""
        image = Image.open(path)

        # Apply EXIF orientation
        if auto_rotate:
            try:
                from PIL import ImageOps
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

        image.load()

        # Downscale if too large
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        return image

    def inpaint_regions(self, image: Image.Image, regions: List[TextRegion],
                        padding: int = 3) -> Image.Image:
        """Remove original text from regions by filling with surrounding color."""
        result = image.convert("RGB").copy()

        for region in regions:
            x, y, w, h = region.bbox
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(result.width - x, w + 2 * padding)
            h = min(result.height - y, h + 2 * padding)

            if w <= 0 or h <= 0:
                continue

            # Sample the surrounding background color
            bg_color = self._sample_background_color(result, (x, y, w, h))

            # Fill the region
            draw = ImageDraw.Draw(result)
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

        return result

    def _sample_background_color(self, image: Image.Image, bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
        """Sample the dominant background color around a region."""
        x, y, w, h = bbox
        img_w, img_h = image.size

        # Collect border pixels
        samples = []
        pad = 5

        # Top and bottom edges
        for px in range(max(0, x), min(img_w, x + w), 3):
            for py in (max(0, y - pad), min(img_h - 1, y + h + pad)):
                samples.append(image.getpixel((px, py)))

        # Left and right edges
        for py in range(max(0, y), min(img_h, y + h), 3):
            for px in (max(0, x - pad), min(img_w - 1, x + w + pad)):
                samples.append(image.getpixel((px, py)))

        if not samples:
            return (255, 255, 255)

        # Use the median color (accepts tuples; take per-channel median)
        arr = np.array(samples[:3] if False else samples)
        if arr.ndim == 2:
            median = tuple(int(v) for v in np.median(arr, axis=0)[:3])
        else:
            median = (255, 255, 255)
        return median

    def render_translations(self, image: Image.Image, regions: List[TextRegion],
                            translations: List[TranslationResult],
                            inpaint: bool = True,
                            font_path: Optional[str] = None,
                            text_color: Tuple[int, int, int] = (0, 0, 0),
                            bg_color: Optional[Tuple[int, int, int]] = None,
                            auto_font_size: bool = True) -> Image.Image:
        """Render translated text onto the image."""
        result = image.convert("RGB").copy()

        if inpaint:
            result = self.inpaint_regions(result, regions)

        draw = ImageDraw.Draw(result)

        for region, trans in zip(regions, translations):
            text = trans.translated_text
            if not text or text.startswith("["):
                # Skip failed translations
                if not text:
                    continue

            x, y, w, h = region.bbox
            if w <= 0 or h <= 0:
                continue

            # Determine font size
            font_size = h if auto_font_size else 14
            font = self._load_font(font_path, max(8, int(font_size * 0.8)))

            # Wrap text to fit region
            wrapped = self._wrap_text(text, font, w - 6, draw)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)

            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            # Draw background box if configured
            if bg_color:
                draw.rectangle([x, y, x + w, y + h], fill=bg_color)

            # Center the text in the region
            tx = x + max(0, (w - text_w) // 2)
            ty = y + max(0, (h - text_h) // 2)

            draw.multiline_text(
                (tx, ty), wrapped,
                fill=text_color, font=font, align="center"
            )

        return result

    def _load_font(self, font_path: Optional[str], size: int):
        """Load a font, falling back to default."""
        candidates = []
        if font_path:
            candidates.append(font_path)

        # Common system fonts
        candidates.extend([
            "C:/Windows/Fonts/msyh.ttc",   # Microsoft YaHei (CJK)
            "C:/Windows/Fonts/msgothic.ttc",  # MS Gothic (Japanese)
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])

        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue

        return ImageFont.load_default()

    def _wrap_text(self, text: str, font, max_width: int, draw) -> str:
        """Wrap text to fit within max_width."""
        words = text.split()
        if not words:
            return text

        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        return "\n".join(lines)

    def create_bilingual(self, original: Image.Image, translated: Image.Image,
                         layout: str = "side_by_side") -> Image.Image:
        """Create a bilingual comparison image."""
        if layout == "side_by_side":
            w = original.width + translated.width
            h = max(original.height, translated.height)
            result = Image.new("RGB", (w, h), (255, 255, 255))
            result.paste(original.convert("RGB"), (0, 0))
            result.paste(translated.convert("RGB"), (original.width, 0))
            return result
        elif layout == "top_bottom":
            w = max(original.width, translated.width)
            h = original.height + translated.height
            result = Image.new("RGB", (w, h), (255, 255, 255))
            result.paste(original.convert("RGB"), (0, 0))
            result.paste(translated.convert("RGB"), (0, original.height))
            return result
        else:
            return translated

    def save_image(self, image: Image.Image, path: Path, fmt: str = "png", quality: int = 90):
        """Save an image in the specified format."""
        fmt = fmt.lower()
        if fmt == "jpg" or fmt == "jpeg":
            if image.mode == "RGBA":
                image = image.convert("RGB")
            image.save(path, "JPEG", quality=quality)
        elif fmt == "png":
            image.save(path, "PNG")
        else:
            image.save(path)