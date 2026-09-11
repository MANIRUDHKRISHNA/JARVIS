"""Browser and Google Search helpers using the optional computer gateway."""

from __future__ import annotations

from urllib.parse import quote_plus

from app.tools.computer import computer_control


def open_browser() -> str:
    """Open Google Chrome through the local computer gateway."""
    return computer_control("Open Google Chrome.")


def open_url(url: str) -> str:
    """Open an HTTP or HTTPS URL through the local computer gateway."""
    if not url.startswith(("http://", "https://")):
        return "ERROR: Only HTTP and HTTPS URLs are allowed."
    return computer_control(f"Open this URL in the browser: {url}")


def browser_search(query: str, max_results: int = 5) -> str:
    """Search Google and return structured organic search evidence for JARVIS to reason over."""
    if not query or not query.strip():
        return "ERROR: Search query cannot be empty."

    if not 1 <= max_results <= 10:
        return "ERROR: max_results must be between 1 and 10."

    search_query = query.strip()[:500]

    instruction = f"""
Use Google Search in the browser to search for this exact query:

{search_query}

Return ONLY the search evidence. Do not answer or summarize the user's
underlying question.

Return up to {max_results} relevant ORGANIC results using exactly this shape:

RESULT 1
TITLE: <page title>
URL: <full result URL>
SNIPPET: <short visible search-result snippet>

RESULT 2
TITLE: <page title>
URL: <full result URL>
SNIPPET: <short visible search-result snippet>

Continue until you have up to {max_results} useful organic results.

Rules:
- Use Google Search, not another search engine.
- Do not click advertisements.
- Do not invent URLs, titles, or snippets.
- Only report information visible in the Google results or a page you opened
  specifically to verify a result.
- If Google returns no useful results, say exactly: NO_RESULTS
- If the browser cannot perform the search, return an ERROR message.
""".strip()

    result = computer_control(instruction)
    return result.strip() if result else "ERROR: Google Search returned no result."
