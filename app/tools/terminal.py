"""Terminal tools for JARVIS."""

import subprocess


def run_command(command: str) -> str:
    """
    Execute a Windows command.

    Permission checking is handled by the JARVIS agent
    before this function is called.

    Args:
        command: The command to execute.

    Returns:
        Command output or an error message.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if output and error:
            return (
                f"STDOUT:\n{output}\n\n"
                f"STDERR:\n{error}\n"
                f"Exit code: {result.returncode}"
            )

        if output:
            return output

        if error:
            return (
                f"STDERR:\n{error}\n"
                f"Exit code: {result.returncode}"
            )

        return (
            f"Command completed with exit code "
            f"{result.returncode}."
        )

    except subprocess.TimeoutExpired:
        return "Command timed out after 60 seconds."

    except Exception as exc:
        return f"Failed to execute command: {exc}"