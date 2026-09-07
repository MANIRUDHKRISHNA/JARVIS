import subprocess


def has_nvidia() -> bool:
    try:
        subprocess.check_output(["nvidia-smi"], stderr=subprocess.DEVNULL, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def diagnostics() -> dict:
    """Return lightweight NVIDIA availability information."""

    available = has_nvidia()
    return {
        "gpu": available,
        "cuda": available,
    }