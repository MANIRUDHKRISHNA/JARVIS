"""Filesystem tools for JARVIS."""

from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


def list_directory(path: str) -> str:
    """List files and directories at a path."""

    target = Path(path)

    if not target.exists():
        return f"ERROR: Path does not exist: {path}"

    if not target.is_dir():
        return f"ERROR: Path is not a directory: {path}"

    try:
        entries = []

        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in IGNORED_DIRECTORIES:
                continue

            kind = "DIR" if item.is_dir() else "FILE"
            entries.append(f"{kind}: {item.name}")

        if not entries:
            return f"Directory is empty: {path}"

        return "\n".join(entries)

    except PermissionError:
        return f"ERROR: Permission denied while listing: {path}"
    except Exception as exc:
        return f"ERROR: Could not list directory: {exc}"


def search_files(path: str, query: str) -> str:
    """Recursively search text files for a query."""

    root = Path(path)

    if not root.exists():
        return f"ERROR: Path does not exist: {path}"

    if not root.is_dir():
        return f"ERROR: Search root is not a directory: {path}"

    query_lower = query.lower()
    matches = []
    max_matches = 100
    max_file_size = 2 * 1024 * 1024

    try:
        for file_path in root.rglob("*"):

            if len(matches) >= max_matches:
                break

            if not file_path.is_file():
                continue

            if any(part in IGNORED_DIRECTORIES for part in file_path.parts):
                continue

            try:
                if file_path.stat().st_size > max_file_size:
                    continue

                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

                for line_number, line in enumerate(
                    content.splitlines(),
                    start=1,
                ):
                    if query_lower in line.lower():
                        matches.append(
                            f"{file_path}:{line_number}: {line.strip()}"
                        )

                        if len(matches) >= max_matches:
                            break

            except (PermissionError, OSError):
                continue

        if not matches:
            return f"No matches found for '{query}' in {path}"

        result = "\n".join(matches)

        if len(matches) >= max_matches:
            result += "\n... result limit reached."

        return result

    except Exception as exc:
        return f"ERROR: Could not search files: {exc}"


def read_file(path: str) -> str:
    """Read a text file."""

    target = Path(path)

    if not target.exists():
        return f"ERROR: File does not exist: {path}"

    if not target.is_file():
        return f"ERROR: Path is not a file: {path}"

    try:
        return target.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except PermissionError:
        return f"ERROR: Permission denied while reading: {path}"

    except Exception as exc:
        return f"ERROR: Could not read file: {exc}"


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file."""

    target = Path(path)

    try:
        if target.exists() and target.is_dir():
            return f"ERROR: Cannot write to a directory: {path}"

        target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(
            content,
            encoding="utf-8",
        )

        if not target.exists():
            return f"ERROR: File write reported success but file does not exist: {path}"

        return f"SUCCESS: File written: {path}"

    except PermissionError:
        return f"ERROR: Permission denied while writing: {path}"

    except Exception as exc:
        return f"ERROR: Could not write file: {exc}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """
    Replace one exact section of an existing file.

    The old text must exist exactly once.
    A backup is created before modifying the file.
    """

    target = Path(path)

    if not target.exists():
        return f"ERROR: File does not exist: {path}"

    if not target.is_file():
        return f"ERROR: Path is not a file: {path}"

    if not old_text:
        return "ERROR: old_text cannot be empty."

    try:
        content = target.read_text(
            encoding="utf-8",
            errors="replace",
        )

        occurrences = content.count(old_text)

        if occurrences == 0:
            return (
                "ERROR: The requested old_text was not found in the file. "
                "The file was not changed."
            )

        if occurrences > 1:
            return (
                f"ERROR: old_text occurs {occurrences} times. "
                "The edit was refused because the target is ambiguous."
            )

        backup = target.with_suffix(target.suffix + ".bak")

        backup.write_text(
            content,
            encoding="utf-8",
        )

        updated = content.replace(
            old_text,
            new_text,
            1,
        )

        target.write_text(
            updated,
            encoding="utf-8",
        )

        # Verify the final file.
        final_content = target.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if new_text not in final_content:
            # Restore backup if verification failed.
            target.write_text(
                content,
                encoding="utf-8",
            )

            return (
                "ERROR: Edit verification failed. "
                "The original file was restored."
            )

        return (
            f"SUCCESS: File edited: {path}\n"
            f"BACKUP: {backup}"
        )

    except PermissionError:
        return f"ERROR: Permission denied while editing: {path}"

    except Exception as exc:
        return f"ERROR: Could not edit file: {exc}"