"""Dependency-light local document loaders."""

from __future__ import annotations

import csv
import json
from pathlib import Path

SUPPORTED_EXTENSIONS = {".py", ".txt", ".md", ".json", ".csv", ".docx", ".pdf"}


def load_text(path: str | Path) -> str:
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return ""
    if extension == ".csv":
        with file_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            return "\n".join(", ".join(row) for row in csv.reader(handle))
    if extension == ".json":
        return json.dumps(json.loads(file_path.read_text(encoding="utf-8")), indent=2)
    if extension == ".docx":
        try:
            from docx import Document
            return "\n".join(paragraph.text for paragraph in Document(file_path).paragraphs)
        except (ImportError, OSError):
            return ""
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(file_path)).pages)
        except (ImportError, OSError):
            return ""
    return file_path.read_text(encoding="utf-8", errors="replace")
