"""System-level helper tools."""

import platform


class SystemTools:
    def get_os(self) -> str:
        return platform.system()

    def get_version(self) -> str:
        return platform.version()
