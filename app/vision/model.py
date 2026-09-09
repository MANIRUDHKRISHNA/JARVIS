"""Local Ollama vision-model adapter."""

from __future__ import annotations

import base64
from pathlib import Path

from ollama import chat

from app.config.vision_config import VISION_MODEL


def analyze_local_image(path: str, question: str | None = None) -> dict:
    image_path = Path(path)
    if not image_path.is_file():
        return {"success": False, "error": f"Image does not exist: {path}"}
    try:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = question or "Describe this image and list important observations."
        response = chat(model=VISION_MODEL, messages=[{"role": "user", "content": prompt, "images": [encoded]}], think=False)
        description = (response.message.content or "").strip()
        return {"success": True, "description": description, "observations": [description] if description else [], "source": str(image_path)}
    except Exception as exc:
        return {"success": False, "error": f"Vision model unavailable: {exc}"}
