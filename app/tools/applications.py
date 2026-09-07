"""Windows application tools."""

import subprocess


def open_application(application: str) -> str:
    """
    Open a Windows application.

    Args:
        application: Name or command of the Windows application.

    Returns:
        A message describing the result.
    """

    try:
        process = subprocess.Popen(
            ["cmd", "/c", "start", "", application],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return (
            f"Successfully launched {application}. "
            f"Process ID: {process.pid}"
        )

    except Exception as exc:
        return f"Failed to open {application}: {exc}"