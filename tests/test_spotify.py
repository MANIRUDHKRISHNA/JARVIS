from app.tools.spotify import spotify_next, spotify_pause, spotify_play, spotify_previous


def test_spotify_play_requires_query():
    assert spotify_play("").startswith("ERROR:")


def test_spotify_controls():
    assert "pause" in spotify_pause().lower()
    assert "next" in spotify_next().lower()
    assert "previous" in spotify_previous().lower()
