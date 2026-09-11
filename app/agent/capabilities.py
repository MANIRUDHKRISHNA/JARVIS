"""Authoritative, local capability registry for existing JARVIS tools."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import platform
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

from app.agent.results import ToolResult
from app.agent.security import PermissionLevel, SecurityManager, check_command, check_file_edit, check_file_write


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"
    VERIFICATION_FAILED = "verification_failed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    category: str
    version: str = "1.0"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    confirmation_required: bool = False
    platform: str | None = None
    dependencies: tuple[str, ...] = ()
    verification_strategy: str = "tool-result"


@dataclass
class CapabilityResult:
    tool: str
    operation: str
    status: ToolStatus
    message: str = ""
    data: Any = None
    error: str | None = None
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def from_tool_result(cls, tool: str, result: ToolResult) -> "CapabilityResult":
        status = ToolStatus.SUCCESS if result.success and result.verified else ToolStatus.VERIFICATION_FAILED if result.success else ToolStatus.FAILED
        return cls(tool, result.action or tool, status, result.message, result.data, result.error, result.verified, result.metadata)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class ToolRegistry:
    """Metadata/discovery layer; execution remains in Brain/ExecutionEngine."""

    def __init__(self, security: SecurityManager | None = None, approved_roots: tuple[str | Path, ...] | None = None):
        self.security = security or SecurityManager()
        self.approved_roots = tuple(
            Path(root).resolve()
            for root in (
                approved_roots
                or (
                    Path("C:\\"),
                    Path("D:\\"),
                )
            )
        )
        self._tools: dict[str, tuple[Callable[..., Any], ToolMetadata, Callable[[], tuple[bool, str]] | None]] = {}

    @staticmethod
    def _schema(tool: Callable[..., Any]) -> dict[str, Any]:
        return {name: {"required": parameter.default is inspect.Parameter.empty, "annotation": str(parameter.annotation)} for name, parameter in inspect.signature(tool).parameters.items()}

    def register(self, tool: Callable[..., Any], metadata: ToolMetadata, availability: Callable[[], tuple[bool, str]] | None = None) -> None:
        if metadata.name in self._tools:
            raise ValueError(f"Tool already registered: {metadata.name}")
        if tool.__name__ != metadata.name:
            raise ValueError("Tool metadata name must match the existing tool function name.")
        if not metadata.input_schema:
            metadata = ToolMetadata(**{**asdict(metadata), "input_schema": self._schema(tool)})
        self._tools[metadata.name] = (tool, metadata, availability)

    def get(self, name: str) -> Callable[..., Any] | None:
        item = self._tools.get(name)
        return item[0] if item else None

    def metadata(self, name: str) -> ToolMetadata | None:
        item = self._tools.get(name)
        return item[1] if item else None

    def availability(self, name: str) -> tuple[bool, str]:
        item = self._tools.get(name)
        if not item:
            return False, "Tool is not registered."
        _, metadata, checker = item
        if metadata.platform == "windows" and platform.system().lower() != "windows":
            return False, "This capability requires Windows."
        try:
            return checker() if checker else (True, "Available.")
        except Exception as exc:
            return False, f"Availability check failed: {exc}"

    def inventory(self) -> list[dict[str, Any]]:
        return [{**asdict(metadata), "risk_level": metadata.risk_level.value, "available": available, "availability_reason": reason} for name, (_, metadata, _) in sorted(self._tools.items()) for available, reason in [self.availability(name)]]

    def validate(self, name: str, arguments: dict[str, Any]) -> str | None:
        metadata = self.metadata(name)
        if not metadata:
            return "Unknown tool."
        for argument, schema in metadata.input_schema.items():
            if schema.get("required") and argument not in arguments:
                return f"Missing required argument: {argument}"
        if name in {"read_file", "write_file", "edit_file", "list_directory", "search_files"}:
            path = arguments.get("path")
            if not isinstance(path, str) or not path.strip():
                return "A filesystem path is required."
            try:
                target = Path(path).resolve()
                if not any(target.is_relative_to(root) for root in self.approved_roots):
                    return "Path is outside approved JARVIS roots."
            except OSError:
                return "Path could not be resolved safely."
        return None

    def permission(self, name: str, arguments: dict[str, Any]) -> PermissionLevel:
        metadata = self.metadata(name)
        if not metadata:
            return PermissionLevel.BLOCK
        if name == "run_command":
            return check_command(str(arguments.get("command", "")), self.security)
        if name == "write_file":
            return check_file_write(str(arguments.get("path", "")), self.security)
        if name == "edit_file":
            return check_file_edit(str(arguments.get("path", "")), self.security)
        if name == "git_add": return self.security.check_git_add()
        if name == "git_commit": return self.security.check_git_commit()
        if name == "git_push": return self.security.check_git_push()
        if name in {"computer_control", "browser_action"}:
            return self.security.check_computer_control(str(arguments.get("instruction", arguments.get("action", ""))))
        if name in {"open_application", "open_browser", "open_url", "browser_search"}:
            detail = arguments.get("application") or arguments.get("url") or arguments.get("query") or name
            # These tools can cause an external UI action even when their
            # implementation delegates to the computer gateway internally.
            return self.security.check_computer_control(f"execute {name}: {detail}")
        # Metadata can request confirmation, never waive SecurityManager rules.
        if metadata.confirmation_required:
            return PermissionLevel.CONFIRM
        return PermissionLevel.SAFE

    def dispatch(self, name: str, arguments: dict[str, Any], confirmation_granted: bool = False) -> str:
        """The security-enforced boundary for all registered tool invocation."""
        started = time.perf_counter()
        error = self.validate(name, arguments)
        available, reason = self.availability(name)
        if error:
            return ToolResult(False, action=name, error=error, metadata={"status": ToolStatus.FAILED.value}).to_json()
        if not available:
            return ToolResult(False, action=name, error=reason, metadata={"status": ToolStatus.UNAVAILABLE.value}).to_json()
        permission = self.permission(name, arguments)
        if permission is PermissionLevel.BLOCK:
            return ToolResult(False, action=name, error="Blocked by SecurityManager.", metadata={"status": ToolStatus.BLOCKED.value}).to_json()
        if permission is PermissionLevel.CONFIRM and not confirmation_granted:
            return ToolResult(False, action=name, error="Confirmation required.", metadata={"status": ToolStatus.BLOCKED.value, "confirmation_required": True}).to_json()
        tool = self.get(name)
        try:
            raw = tool(**arguments) if tool else None
            if isinstance(raw, str):
                try: raw = json.loads(raw)
                except json.JSONDecodeError: pass
            from app.agent.results import normalize_tool_result
            result = normalize_tool_result(name, raw, arguments)
            result.metadata = {**result.metadata, "duration_seconds": round(time.perf_counter() - started, 3)}
            return result.to_json()
        except Exception as exc:
            return ToolResult(False, action=name, error=str(exc), metadata={"status": ToolStatus.FAILED.value, "duration_seconds": round(time.perf_counter() - started, 3)}).to_json()
