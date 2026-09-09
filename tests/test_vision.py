from app.vision.analyzer import analyze_image
from app.vision.capture import capture_active_window, capture_screen


def test_missing_image_is_reported():
    result = analyze_image("missing-image.png")
    assert result["success"] is False


def test_capture_functions_fail_gracefully_without_pillow():
    assert isinstance(capture_screen(), str)
    assert isinstance(capture_active_window(), str)
