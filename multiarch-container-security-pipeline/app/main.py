"""Small dependency-free HTTP service with health and build-version endpoints."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    server_version = "sample-container-app"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        routes = {
            "/health": {"status": "ok"},
            "/version": {
                "version": os.getenv("APP_VERSION", "dev"),
                "revision": os.getenv("APP_REVISION", "unknown"),
            },
        }
        payload = routes.get(self.path)
        if payload is None:
            self.send_error(404, "Not Found")
            return
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(
        (host if host is not None else os.getenv("APP_HOST", "0.0.0.0"),
         port if port is not None else int(os.getenv("APP_PORT", "8080"))),
        Handler,
    )


def main() -> None:
    server = create_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
