from app.tools.browser import open_url


def test_open_url_rejects_invalid_protocol():
    assert open_url("file:///C:/Windows/System32").startswith("ERROR:")
