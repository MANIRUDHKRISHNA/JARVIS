"""Spotify control abstraction for JARVIS."""

from __future__ import annotations

from app.agent.logging import logger


class SpotifyController:
    """Honest placeholder until the external Spotify connector is wired."""

    def status(self) -> str:
        return "Spotify integration is available through the configured Spotify connection."

    def play(self, query: str) -> str:
        if not query or not query.strip():
            return "ERROR: Spotify search cannot be empty."
        logger.info("Spotify play request: %s", query)
        return f"Spotify playback requested for: {query}"

    def pause(self) -> str:
        return "Spotify pause requested."

    def next_track(self) -> str:
        return "Spotify next-track requested."

    def previous_track(self) -> str:
        return "Spotify previous-track requested."


_controller = SpotifyController()


def spotify_status() -> str:
    return _controller.status()


def spotify_play(query: str) -> str:
    return _controller.play(query)


def spotify_pause() -> str:
    return _controller.pause()


def spotify_next() -> str:
    return _controller.next_track()


def spotify_previous() -> str:
    return _controller.previous_track()
