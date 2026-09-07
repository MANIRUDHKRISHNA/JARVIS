"""Security and permission checks for JARVIS."""

from enum import Enum
import re


class PermissionLevel(Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    BLOCK = "block"


class SecurityManager:
    """Central security manager for JARVIS actions."""

    BLOCKED_COMMAND_PATTERNS = [
        r"(?i)\bformat\b",
        r"(?i)\bdiskpart\b",
        r"(?i)\bshutdown\b",
        r"(?i)\brestart-computer\b",
        r"(?i)\bstop-computer\b",
        r"(?i)\brmdir\s+/s\b",
        r"(?i)\brd\s+/s\b",
        r"(?i)\bdel\s+/s\b",
        r"(?i)\bdel\s+/q\b",
        r"(?i)\bicacls\b",
        r"(?i)\btakeown\b",
        r"(?i)\bcacls\.exe\b",
    ]

    CONFIRM_COMMAND_PATTERNS = [
        r"(?i)\bpip\s+install\b",
        r"(?i)\bpython\s+-m\s+pip\s+install\b",
        r"(?i)\bgit\s+push\b",
        r"(?i)\bgit\s+commit\b",
        r"(?i)\bgit\s+reset\b",
        r"(?i)\bmkdir\b",
        r"(?i)\bnew-item\b",
        r"(?i)\bremove-item\b",
        r"(?i)\bmove\b",
        r"(?i)\bcopy\b",
    ]

    SENSITIVE_PATH_PATTERNS = [
        r"(?i)(^|[\\/])\.env($|[.\\/])",
        r"(?i)(^|[\\/])id_rsa($|[.])",
        r"(?i)(^|[\\/])id_ed25519($|[.])",
        r"(?i)(^|[\\/])secrets([\\/]|$)",
        r"(?i)(^|[\\/])credentials([\\/]|$)",
        r"(?i)(^|[\\/])passwords([\\/]|$)",
    ]

    def check_command(self, command: str) -> PermissionLevel:
        """Determine whether a terminal command is safe."""

        if not command:
            return PermissionLevel.SAFE

        for pattern in self.BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, command):
                return PermissionLevel.BLOCK

        for pattern in self.CONFIRM_COMMAND_PATTERNS:
            if re.search(pattern, command):
                return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_file_write(self, path: str) -> PermissionLevel:
        """Determine whether writing a file requires confirmation."""

        if self._is_sensitive_path(path):
            return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_file_edit(self, path: str) -> PermissionLevel:
        """Determine whether editing a file requires confirmation."""

        if self._is_sensitive_path(path):
            return PermissionLevel.CONFIRM

        return PermissionLevel.SAFE

    def check_git_commit(self) -> PermissionLevel:
        """Require confirmation before creating a Git commit."""

        return PermissionLevel.CONFIRM

    def check_git_add(self) -> PermissionLevel:
        """Require confirmation before staging Git files."""

        return PermissionLevel.CONFIRM

    def check_git_push(self) -> PermissionLevel:
        """Require confirmation before pushing Git changes."""

        return PermissionLevel.CONFIRM

    def _is_sensitive_path(self, path: str) -> bool:
        """Return True when a path looks like it contains secrets."""

        if not path:
            return False

        normalized = str(path).replace("\\", "/")

        for pattern in self.SENSITIVE_PATH_PATTERNS:
            if re.search(pattern, normalized):
                return True

        return False


# Backwards-compatible alias.
Security = SecurityManager


# Backwards-compatible standalone helper functions.
# These allow older router.py / brain.py versions to continue working.

_default_security = SecurityManager()


def check_command(command: str) -> PermissionLevel:
    return _default_security.check_command(command)


def check_file_write(path: str) -> PermissionLevel:
    return _default_security.check_file_write(path)


def check_file_edit(path: str) -> PermissionLevel:
    return _default_security.check_file_edit(path)