"""Image validation and local analysis."""

from __future__ import annotations

from pathlib import Path

from app.config.vision_config import MAX_IMAGE_SIZE
from app.vision.model import analyze_local_image


def analyze_image(path: str, question: str | None = None) -> dict:
    image_path = Path(path)
    if not image_path.is_file():
        return {"success": False, "error": f"Image does not exist: {path}"}
    if image_path.stat().st_size > MAX_IMAGE_SIZE:
        return {"success": False, "error": "Image exceeds the configured size limit."}
    if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return {"success": False, "error": "Unsupported image format."}
    return analyze_local_image(str(image_path), question)
