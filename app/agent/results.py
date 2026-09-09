"""Structured, evidence-first results for JARVIS tool execution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """The result delivered to the model after a real tool invocation."""

    success: bool
    verified: bool = False
    action: str = ""
    message: str = ""
    data: Any = None
    error: str | None = None
    changed: bool = False
    target: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


def normalize_tool_result(action: str, raw: Any, arguments: dict[str, Any] | None = None) -> ToolResult:
    """Turn legacy tool outputs into an honest structured result.

    Legacy functions are intentionally retained.  Only explicit tool evidence
    (for example filesystem read-back success) is considered verification.
    """
    arguments = arguments or {}
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
    else:
        payload = None

    if isinstance(payload, dict) and "success" in payload:
        return ToolResult(
            success=bool(payload["success"]),
            verified=bool(payload.get("verified", False)),
            action=action,
            message=str(payload.get("message", "")),
            data=payload.get("data", raw),
            error=payload.get("error"),
            changed=bool(payload.get("changed", False)),
            target=payload.get("target"),
            metadata=payload.get("metadata", {}),
        )

    text = str(raw).strip()
    failed = text.lower().startswith(("error:", "failed", "blocked:", "cancelled:", "confirmation required:"))
    # A read returns the observed file content, which is direct evidence for
    # that non-mutating operation. Writes/edits retain their existing read-back
    # evidence convention; all other legacy success strings stay unverified.
    verified = (
        (action == "read_file" and not failed)
        or (action in {"write_file", "edit_file"} and text.lower().startswith("success:"))
    )
    return ToolResult(
        success=not failed,
        verified=verified,
        action=action,
        message=text,
        data=raw,
        error=text if failed else None,
        changed=action in {"write_file", "edit_file"} and not failed,
        target=arguments.get("path") or arguments.get("project_path"),
        metadata={"legacy_result": True},
    )
