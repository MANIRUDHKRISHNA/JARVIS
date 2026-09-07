"""Browser-control helpers using the optional computer gateway."""

from __future__ import annotations

from urllib.parse import quote_plus

from app.tools.computer import computer_control


def open_browser() -> str:
    return computer_control("Open Google Chrome.")


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "ERROR: Only HTTP and HTTPS URLs are allowed."
    return computer_control(f"Open this URL in the browser: {url}")


def browser_search(query: str) -> str:
    if not query or not query.strip():
        return "ERROR: Search query cannot be empty."
    return open_url(f"https://www.google.com/search?q={quote_plus(query.strip())}")


def browser_action(instruction: str) -> str:
    if not instruction or not instruction.strip():
        return "ERROR: Browser instruction cannot be empty."
    return computer_control(f"Using the browser, {instruction}")
