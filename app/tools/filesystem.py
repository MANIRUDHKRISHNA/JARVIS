"""Filesystem helper tools."""

from pathlib import Path


class FilesystemTools:
    def read_text(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> str:
        Path(path).write_text(content, encoding="utf-8")
        return f"Wrote content to {path}"
