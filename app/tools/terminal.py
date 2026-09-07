"""Terminal command tools."""

import subprocess


class TerminalTools:
    def run(self, command: str) -> str:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr or "Command executed successfully."
