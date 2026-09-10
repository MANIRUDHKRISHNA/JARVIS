"""Spotify Web API integration for JARVIS."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from app.agent.logging import logger


CLIENT_ID_ENV = "SPOTIFY_CLIENT_ID"
REDIRECT_URI_ENV = "SPOTIFY_REDIRECT_URI"

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

SCOPES = (
    "user-read-playback-state "
    "user-read-currently-playing "
    "user-modify-playback-state"
)

TOKEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "spotify_token.json"
)


class _CallbackHandler(BaseHTTPRequestHandler):
    """Receive the OAuth callback from Spotify."""

    code: str | None = None
    error: str | None = None
    state: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        type(self).code = params.get("code", [None])[0]
        type(self).error = params.get("error", [None])[0]
        type(self).state = params.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if self.code:
            body = """
            <html>
            <head><title>JARVIS Spotify</title></head>
            <body>
                <h2>Spotify connected to JARVIS.</h2>
                <p>You can close this browser window.</p>
            </body>
            </html>
            """
        else:
            body = """
            <html>
            <head><title>JARVIS Spotify</title></head>
            <body>
                <h2>Spotify authorization failed.</h2>
                <p>You can close this browser window.</p>
            </body>
            </html>
            """

        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


class SpotifyController:
    """Spotify Web API controller using OAuth PKCE."""

    def __init__(self) -> None:
        self.client_id = os.getenv(CLIENT_ID_ENV, "").strip()
        self.redirect_uri = (
            os.getenv(
                REDIRECT_URI_ENV,
                DEFAULT_REDIRECT_URI,
            ).strip()
        )

        self._lock = threading.RLock()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

        self._load_token()

    # --------------------------------------------------------------
    # Configuration
    # --------------------------------------------------------------

    def _require_client_id(self) -> None:
        if not self.client_id:
            raise RuntimeError(
                "SPOTIFY_CLIENT_ID is not configured."
            )

    def _load_token(self) -> None:
        try:
            if not TOKEN_PATH.exists():
                return

            data = json.loads(
                TOKEN_PATH.read_text(
                    encoding="utf-8"
                )
            )

            self._access_token = data.get(
                "access_token"
            )
            self._refresh_token = data.get(
                "refresh_token"
            )
            self._expires_at = float(
                data.get(
                    "expires_at",
                    0,
                )
            )

        except Exception as exc:
            logger.warning(
                "Could not load Spotify token: %s",
                exc,
            )

    def _save_token(self, data: dict[str, Any]) -> None:
        TOKEN_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        TOKEN_PATH.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    # --------------------------------------------------------------
    # OAuth / PKCE
    # --------------------------------------------------------------

    @staticmethod
    def _generate_code_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def _generate_code_challenge(
        verifier: str,
    ) -> str:
        digest = hashlib.sha256(
            verifier.encode("ascii")
        ).digest()

        return (
            base64.urlsafe_b64encode(digest)
            .decode("ascii")
            .rstrip("=")
        )

    def _authorize(self) -> None:
        self._require_client_id()

        parsed = urllib.parse.urlparse(
            self.redirect_uri
        )

        if parsed.hostname not in {
            "127.0.0.1",
            "::1",
        }:
            raise RuntimeError(
                "Spotify redirect URI must use a loopback "
                "IP such as 127.0.0.1."
            )

        port = parsed.port or 8888

        verifier = self._generate_code_verifier()
        challenge = self._generate_code_challenge(
            verifier
        )

        state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }

        auth_url = (
            AUTH_URL
            + "?"
            + urllib.parse.urlencode(params)
        )

        _CallbackHandler.code = None
        _CallbackHandler.error = None
        _CallbackHandler.state = None

        server = HTTPServer(
            ("127.0.0.1", port),
            _CallbackHandler,
        )

        server.timeout = 1

        logger.info(
            "Opening Spotify authorization page."
        )

        webbrowser.open(auth_url)

        deadline = time.monotonic() + 180

        try:
            while time.monotonic() < deadline:
                server.handle_request()

                if (
                    _CallbackHandler.code
                    or _CallbackHandler.error
                ):
                    break
        finally:
            server.server_close()

        if _CallbackHandler.error:
            raise RuntimeError(
                "Spotify authorization failed: "
                f"{_CallbackHandler.error}"
            )

        if not _CallbackHandler.code:
            raise RuntimeError(
                "Spotify authorization timed out."
            )

        if _CallbackHandler.state != state:
            raise RuntimeError(
                "Spotify OAuth state validation failed."
            )

        token = self._exchange_code(
            _CallbackHandler.code,
            verifier,
        )

        self._access_token = token["access_token"]
        self._refresh_token = token.get(
            "refresh_token"
        )
        self._expires_at = (
            time.time()
            + int(token.get("expires_in", 3600))
            - 60
        )

        self._save_token(
            {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
            }
        )

    def _exchange_code(
        self,
        code: str,
        verifier: str,
    ) -> dict[str, Any]:
        payload = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            TOKEN_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            raise RuntimeError(
                "Spotify authorization is required."
            )

        payload = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            TOKEN_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            token = json.loads(
                response.read().decode("utf-8")
            )

        self._access_token = token[
            "access_token"
        ]

        if token.get("refresh_token"):
            self._refresh_token = token[
                "refresh_token"
            ]

        self._expires_at = (
            time.time()
            + int(token.get("expires_in", 3600))
            - 60
        )

        self._save_token(
            {
                "access_token":
                    self._access_token,
                "refresh_token":
                    self._refresh_token,
                "expires_at":
                    self._expires_at,
            }
        )

    def _ensure_token(self) -> str:
        self._require_client_id()

        with self._lock:
            if (
                self._access_token
                and time.time() < self._expires_at
            ):
                return self._access_token

            if self._refresh_token:
                self._refresh_access_token()
                return self._access_token

            self._authorize()

            if not self._access_token:
                raise RuntimeError(
                    "Spotify authorization did not "
                    "produce an access token."
                )

            return self._access_token

    # --------------------------------------------------------------
    # HTTP API
    # --------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Make a Spotify API request with authentication and retries."""

        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                token = self._ensure_token()

                url = API_BASE + endpoint

                if params:
                    url += "?" + urllib.parse.urlencode(params)

                data = None

                if body is not None:
                    data = json.dumps(body).encode("utf-8")

                request = urllib.request.Request(
                    url,
                    data=data,
                    method=method,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )

                with urllib.request.urlopen(
                    request,
                    timeout=15,
                ) as response:
                    raw = response.read()

                    if not raw:
                        return {}

                    return json.loads(
                        raw.decode("utf-8")
                    )

            except Exception as exc:
                last_error = exc
                error_text = str(exc)

                # Expired/invalid access token.
                if "401" in error_text:
                    with self._lock:
                        self._access_token = None

                    if attempt < max_attempts - 1:
                        continue

                # Temporary Spotify/server/network failure.
                transient = any(
                    code in error_text
                    for code in (
                        "502",
                        "503",
                        "504",
                        "timed out",
                        "Timeout",
                        "Connection reset",
                        "Connection refused",
                    )
                )

                if transient and attempt < max_attempts - 1:
                    wait_seconds = 1.0 * (attempt + 1)

                    logger.warning(
                        "Spotify temporary failure (%s). "
                        "Retrying in %.1fs.",
                        error_text,
                        wait_seconds,
                    )

                    time.sleep(wait_seconds)
                    continue

                raise

        if last_error is not None:
            raise last_error

        raise RuntimeError("Spotify request failed unexpectedly.")

    # --------------------------------------------------------------
    # Spotify operations
    # --------------------------------------------------------------

    def status(self) -> str:
        try:
            data = self._request(
                "GET",
                "/me/player",
            )

            if not data:
                return (
                    "Spotify is connected, but there "
                    "is no active playback device."
                )

            item = data.get("item") or {}
            name = item.get("name", "Unknown track")

            artists = ", ".join(
                artist.get("name", "")
                for artist in item.get(
                    "artists",
                    [],
                )
            )

            state = (
                "playing"
                if data.get("is_playing")
                else "paused"
            )

            return (
                f"Spotify is {state}: "
                f"{name}"
                + (
                    f" by {artists}"
                    if artists
                    else ""
                )
            )

        except Exception as exc:
            return f"Spotify status failed: {exc}"

    def play(self, query: str) -> str:
        """Search Spotify and play the best matching track."""

        if not query or not query.strip():
            return "ERROR: Spotify search cannot be empty."

        original_query = query.strip()

        try:
            # Search several candidates instead of trusting Spotify's
            # first result. Humans have somehow made song titles ambiguous.
            results = self._request(
                "GET",
                "/search",
                params={
                    "q": original_query,
                    "type": "track",
                    "limit": 10,
                },
            )

            tracks = (
                results
                .get("tracks", {})
                .get("items", [])
            )

            if not tracks:
                return (
                    f"No Spotify track found for "
                    f"'{original_query}'."
                )

            # Normalize text for matching.
            def normalize(value: str) -> str:
                return " ".join(
                    value.lower()
                    .replace("-", " ")
                    .replace("_", " ")
                    .split()
                )

            wanted = normalize(original_query)

            # Score candidates.
            def score(track: dict[str, Any]) -> int:
                name = normalize(track.get("name", ""))

                artists = [
                    normalize(a.get("name", ""))
                    for a in track.get("artists", [])
                ]

                score_value = 0

                # Exact track-name match gets the strongest preference.
                if name == wanted:
                    score_value += 100

                # Exact artist match.
                if wanted in artists:
                    score_value += 60

                # Query contained in the track title.
                if wanted and wanted in name:
                    score_value += 40

                # Track title contained in query.
                if name and name in wanted:
                    score_value += 30

                # Artist appears in the user's query.
                for artist in artists:
                    if artist and artist in wanted:
                        score_value += 25

                # Prefer playable tracks.
                if track.get("is_playable", True):
                    score_value += 10

                return score_value

            track = max(tracks, key=score)

            track_uri = track.get("uri")
            if not track_uri:
                return (
                    f"Spotify found '{track.get('name', original_query)}' "
                    "but it has no playable URI."
                )

            artists = ", ".join(
                artist.get("name", "")
                for artist in track.get("artists", [])
            )

            # Explicitly find available playback devices.
            devices = self._request(
                "GET",
                "/me/player/devices",
            )

            device_list = devices.get("devices", [])

            if not device_list:
                return (
                    "Spotify is connected, but no playback device "
                    "is available. Open Spotify on your PC and "
                    "start playback once, then try again."
                )

            # Prefer the currently active device.
            device = next(
                (
                    d for d in device_list
                    if d.get("is_active")
                ),
                None,
            )

            # Otherwise prefer the desktop app.
            if device is None:
                device = next(
                    (
                        d for d in device_list
                        if d.get("type", "").lower() == "computer"
                    ),
                    None,
                )

            # Fall back to the first available device.
            if device is None:
                device = device_list[0]

            device_id = device.get("id")
            device_name = device.get("name", "Spotify device")

            # Explicit device selection prevents Spotify from trying
            # to guess where playback should happen.
            body = {
                "uris": [track_uri],
            }

            if device_id:
                self._request(
                    "PUT",
                    "/me/player/play",
                    params={
                        "device_id": device_id,
                    },
                    body=body,
                )
            else:
                self._request(
                    "PUT",
                    "/me/player/play",
                    body=body,
                )

            return (
                f"Playing {track.get('name', 'unknown track')}"
                + (
                    f" by {artists}"
                    if artists
                    else ""
                )
                + f" on {device_name}."
            )

        except Exception as exc:
            logger.exception(
                "Spotify play failed for query '%s'.",
                original_query,
            )

            error_text = str(exc)

            if "404" in error_text:
                return (
                    "Spotify could not start playback because the "
                    "selected playback device is no longer available. "
                    "Open Spotify, make sure the device is active, "
                    "and try again."
                )

            return f"Spotify play failed: {error_text}"

    def pause(self) -> str:
        try:
            self._request(
                "PUT",
                "/me/player/pause",
            )

            return "Spotify playback paused."

        except Exception as exc:
            return f"Spotify pause failed: {exc}"

    def resume(self) -> str:
        try:
            self._request(
                "PUT",
                "/me/player/play",
            )

            return "Spotify playback resumed."

        except Exception as exc:
            return f"Spotify resume failed: {exc}"

    def next_track(self) -> str:
        try:
            self._request(
                "POST",
                "/me/player/next",
            )

            return "Skipped to the next Spotify track."

        except Exception as exc:
            return f"Spotify next-track failed: {exc}"

    def previous_track(self) -> str:
        try:
            self._request(
                "POST",
                "/me/player/previous",
            )

            return (
                "Skipped to the previous Spotify track."
            )

        except Exception as exc:
            return (
                f"Spotify previous-track failed: {exc}"
            )


_controller = SpotifyController()


def spotify_status() -> str:
    return _controller.status()


def spotify_play(query: str) -> str:
    return _controller.play(query)


def spotify_pause() -> str:
    return _controller.pause()


def spotify_resume() -> str:
    return _controller.resume()


def spotify_next() -> str:
    return _controller.next_track()


def spotify_previous() -> str:
    return _controller.previous_track()


__all__ = [
    "spotify_status",
    "spotify_play",
    "spotify_pause",
    "spotify_resume",
    "spotify_next",
    "spotify_previous",
]