"""In-process selftest: boot the reference server on an ephemeral port and
run the black-box conformance suite against it. No external process needed.
"""

from __future__ import annotations

import os
import sys
import threading
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "reference"))
sys.path.insert(0, os.path.join(ROOT, "conformance"))

import run as conformance  # noqa: E402
from server import Handler  # noqa: E402


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/cli"
    print(f"selftest server at {base}")
    try:
        client = conformance.Client(base, "demo-token")
        result = conformance.run_suite(client, strict=False)
    finally:
        srv.shutdown()

    counts = {"PASS": 0, "FAIL": 0, "WARN": 0}
    for level, name, detail in result.checks:
        counts[level] = counts.get(level, 0) + 1
        line = f"  [{level}] {name}"
        if detail and level != "PASS":
            line += f" — {detail}"
        print(line)
    print()
    print(f"Summary: {counts['PASS']} passed, {counts['FAIL']} failed, {counts['WARN']} warnings")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
