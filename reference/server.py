"""Minimal stdlib HTTP transport for the reference engine.

Run:  python3 reference/server.py  [--port 8080]
Serves the demo tree at http://127.0.0.1:8080/cli
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from app import build_app  # noqa: E402
from httpcli import CliError, encode_body  # noqa: E402

APP = build_app()

# Demo auth: any non-empty bearer token whose value is a printable ASCII string.
DEMO_TOKEN = "demo-token"


class Handler(BaseHTTPRequestHandler):
    server_version = "HttpCliRef/0.1"

    def _respond(self, status: int, body: dict) -> None:
        raw = encode_body(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-HTTP-CLI-Version", "1.0.0")
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self, method: str) -> None:
        auth = self.headers.get("Authorization", "")
        if not (auth.startswith("Bearer ") and auth[len("Bearer "):].strip()):
            self._respond(401, {
                "error": {
                    "code": "unauthorized",
                    "message": "missing or invalid credential",
                    "hint": "Header: Authorization: Bearer <token>",
                }
            })
            return

        url = urlsplit(self.path)
        query = dict(parse_qsl(url.query, keep_blank_values=True))

        body = None
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            raw = self.rfile.read(length)
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            if ctype and ctype != "application/json":
                self._respond(415, {
                    "error": {
                        "code": "unsupported_media_type",
                        "message": f"unsupported content type {ctype!r}",
                        "hint": "send application/json",
                    }
                })
                return
            try:
                body = json.loads(raw.decode("utf-8") or "null")
            except (ValueError, UnicodeDecodeError):
                self._respond(400, {
                    "error": {
                        "code": "bad_body",
                        "message": "invalid JSON body",
                        "hint": "send a JSON object",
                    }
                })
                return

        status, payload = APP.dispatch(method, url.path, query, body)
        self._respond(status, payload)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_PATCH(self) -> None:
        self._handle("PATCH")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser(description="HTTP CLI reference server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"HTTP CLI demo tree at http://{args.host}:{args.port}/cli  (token: {DEMO_TOKEN})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
