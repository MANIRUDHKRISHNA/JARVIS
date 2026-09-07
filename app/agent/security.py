"""Security and permission management for JARVIS."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class PermissionLevel(str, Enum):
    """Permission level required for an operation."""

    SAFE = "safe"
    CONFIRM = "confirm"
    BLOCK = "block"


class SecurityManager:
    """Central security policy for JARVIS actions."""

    DANGEROUS_COMMAND_PATTERNS = (
        r"\bformat\b",
        r"\bdiskpart\b",
        r"\bshutdown\b",
        r"\brestart-computer\b",
        r"\bstop-computer\b",
        r"\brmdir\s+/s\b",
        r"\brd\s+/s\b",
        r"\bdel\s+/s\b",
        r"\bdel\s+/q\b",
        r"\bicacls\b",
        r"\btakeown\b",
        r"\bcacls\.exe\b",
    )

    CONFIRM_COMMAND_PATTERNS = (
        r"\bpip\s+install\b",
        r"\bpython(?:\.exe)?\s+-m\s+pip\s+install\b",
        r"\bgit\s+push\b",
        r"\bgit\s+commit\b",
        r"\bgit\s+reset\b",
        r"\bgit\s+checkout\b",
        r"\bgit\s+clean\b",
        r"\bmkdir\b",
        r"\bnew-item\b",
        r"\bremove-item\b",
        r"\bmove\b",
        r"\bcopy\b",
    )

    SENSITIVE_PATH_PATTERNS = (
        r"(^|[\\/])\.env(?:\..*)?$",
        r"(^|[\\/])id_rsa$",
        r"(^|[\\/])id_ed25519$",
        r"(^|[\\/])secrets?([\\/]|$)",
        r"(^|[\\/])credentials?([\\/]|$)",
        r"(^|[\\/])passwords?([\\/]|$)",
    )

    BLOCKED_COMPUTER_PATTERNS = (
        r"\bdisable\s+(windows\s+)?defender\b",
        r"\bdisable\s+(the\s+)?firewall\b",
        r"\bdisable\s+antivirus\b",
        r"\bturn\s+off\s+defender\b",
        r"\bbypass\s+security\b",
        r"\bsteal\s+(credentials|passwords|tokens)\b",
        r"\bdump\s+(credentials|passwords|hashes)\b",
        r"\bdelete\s+system32\b",
        r"\bformat\s+(the\s+)?drive\b",
    )

    CONFIRM_COMPUTER_PATTERNS = (
        r"\bdelete\b",
        r"\buninstall\b",
        r"\binstall\b",
        r"\bpurchase\b",
        r"\bbuy\b",
        r"\bsend\s+email\b",
        r"\bsend\s+message\b",
        r"\bsubmit\b",
        r"\bupload\b",
        r"\bdownload\b",
        r"\bchange\s+settings?\b",
        r"\bexecute\b",
    )

    def check_command(
        self,
        command: str,
    ) -> PermissionLevel:
        """Check whether a terminal command is safe."""
        if not command:
            return PermissionLevel.BLOCK

        normalized = command.strip().lower()

        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):
                return PermissionLevel.BLOCK

        for pattern in self.CONFIRM_COMMAND_PATTERNS:
            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):
                return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_file_write(
        self,
        path: str,
    ) -> PermissionLevel:
        """Check permission for creating/writing a file."""
        if not path:
            return PermissionLevel.BLOCK

        normalized = str(
            Path(path)
        ).replace("\\", "/")

        if self._is_sensitive_path(normalized):
            return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_file_edit(
        self,
        path: str,
    ) -> PermissionLevel:
        """Check permission for editing a file."""
        if not path:
            return PermissionLevel.BLOCK

        normalized = str(
            Path(path)
        ).replace("\\", "/")

        if self._is_sensitive_path(normalized):
            return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_git_add(
        self,
    ) -> PermissionLevel:
        """Adding files to a Git commit requires confirmation."""
        return PermissionLevel.CONFIRM

    def check_git_commit(
        self,
    ) -> PermissionLevel:
        """Creating a Git commit requires confirmation."""
        return PermissionLevel.CONFIRM

    def check_git_push(
        self,
    ) -> PermissionLevel:
        """Pushing to a remote requires confirmation."""
        return PermissionLevel.CONFIRM

    def check_git_checkpoint(
        self,
        operation: str = "",
    ) -> PermissionLevel:
        """
        Check Git checkpoint/snapshot operations.

        Creating, restoring, or deleting a checkpoint changes repository
        state and therefore requires confirmation.
        """
        normalized = str(
            operation
        ).strip().lower()

        if normalized in {
            "git_create_checkpoint",
            "git_restore_checkpoint",
            "git_delete_checkpoint",
            "create_checkpoint",
            "restore_checkpoint",
            "delete_checkpoint",
        }:
            return PermissionLevel.CONFIRM

        if normalized in {
            "git_add",
            "git_commit",
            "git_push",
            "add",
            "commit",
            "push",
        }:
            return PermissionLevel.CONFIRM

        return PermissionLevel.CONFIRM

    def check_computer_control(
        self,
        instruction: str,
    ) -> PermissionLevel:
        """Check a computer-control instruction."""
        if not instruction:
            return PermissionLevel.BLOCK

        normalized = instruction.strip().lower()

        for pattern in self.BLOCKED_COMPUTER_PATTERNS:
            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):
                return PermissionLevel.BLOCK

        for pattern in self.CONFIRM_COMPUTER_PATTERNS:
            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):
                return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def _is_sensitive_path(
        self,
        path: str,
    ) -> bool:
        normalized = path.replace(
            "\\",
            "/",
        )

        for pattern in self.SENSITIVE_PATH_PATTERNS:
            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):
                return True

        return False


# Backward-compatible alias.
Security = SecurityManager


# Standalone helper functions used by Brain.


def check_command(
    command: str,
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_command(
        command
    )


def check_file_write(
    path: str,
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_file_write(
        path
    )


def check_file_edit(
    path: str,
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_file_edit(
        path
    )


def check_git_add(
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_git_add()


def check_git_commit(
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_git_commit()


def check_git_push(
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_git_push()


def check_git_checkpoint(
    operation: str = "",
    security: SecurityManager | None = None,
) -> PermissionLevel:
    manager = security or SecurityManager()

    return manager.check_git_checkpoint(
        operation
    )


__all__ = [
    "PermissionLevel",
    "SecurityManager",
    "Security",
    "check_command",
    "check_file_write",
    "check_file_edit",
    "check_git_add",
    "check_git_commit",
    "check_git_push",
    "check_git_checkpoint",
]