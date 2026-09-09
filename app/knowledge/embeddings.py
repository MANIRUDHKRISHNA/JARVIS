"""Optional local embedding adapter with deterministic fallback."""

from __future__ import annotations

import hashlib
import math


def embed(text: str, dimensions: int = 64) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [(digest[index % len(digest)] / 255.0) * 2 - 1 for index in range(dimensions)]
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / length for value in values]
