import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# A deterministic binary payload used by download/resume tests.
BODY = (b"%PDF-1.4\n" + bytes(range(256)) * 50)[:12000]
assert len(BODY) == 12000

HTML_PAGE = b"""<!doctype html>
<html><head><title>Test Library</title></head>
<body>
  <h1>Sample Library</h1>
  <a href="/file" download="book.pdf">Download PDF</a>
  <a href="https://drive.google.com/file/d/ABC123/view">Drive Book</a>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, body, status=200, content_type="application/octet-stream", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        range_header = self.headers.get("Range", "")
        self.server.seen_ranges.append((path, range_header))

        if path == "/html":
            self._send(HTML_PAGE, content_type="text/html; charset=utf-8")
            return
        if path == "/html_file":
            self._send(b"<html><body>error page</body></html>", content_type="text/html")
            return
        if path == "/empty":
            self._send(b"", content_type="application/octet-stream")
            return
        if path == "/file":
            start = self._range_start(range_header)
            if start is None:
                self._send(BODY)
                return
            if start >= len(BODY):
                self._send(
                    b"",
                    status=416,
                    extra={"Content-Range": f"bytes */{len(BODY)}"},
                )
                return
            self._send(
                BODY[start:],
                status=206,
                extra={"Content-Range": f"bytes {start}-{len(BODY) - 1}/{len(BODY)}"},
            )
            return
        if path == "/norange":
            # Deliberately ignores Range and sends the full file.
            self._send(BODY)
            return
        if path == "/complete":
            start = self._range_start(range_header)
            if start is not None:
                self._send(
                    b"",
                    status=416,
                    extra={"Content-Range": f"bytes */{len(BODY)}"},
                )
                return
            self._send(BODY)
            return
        self._send(b"not found", status=404, content_type="text/plain")

    @staticmethod
    def _range_start(range_header):
        if not range_header.startswith("bytes="):
            return None
        try:
            return int(range_header[6:].split("-")[0])
        except (ValueError, IndexError):
            return None


@pytest.fixture()
def local_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.seen_ranges = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base, server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def body():
    return BODY
