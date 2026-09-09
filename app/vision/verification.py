"""Visual verification helpers."""

from __future__ import annotations

from app.vision.analyzer import analyze_image


def verify_screen(path: str, expected: str) -> dict:
    result = analyze_image(path, f"Is this expected state visible? {expected}. Answer yes or no and explain.")
    if not result.get("success"):
        return result
    description = result.get("description", "")
    return {"success": True, "verified": "yes" in description.lower(), "description": description, "source": path}
