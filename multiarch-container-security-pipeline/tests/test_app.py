import json
import threading
import urllib.error
import urllib.request

from app.main import create_server


def test_health_and_version_routes(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-version")
    monkeypatch.setenv("APP_REVISION", "abc123")
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/health", timeout=2) as response:
            assert json.load(response) == {"status": "ok"}
        with urllib.request.urlopen(base + "/version", timeout=2) as response:
            assert json.load(response) == {"version": "test-version", "revision": "abc123"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unknown_route_returns_404():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/missing", timeout=2)
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("unknown endpoint must return 404")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
