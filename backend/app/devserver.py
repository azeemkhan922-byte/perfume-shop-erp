"""Zero-dependency local server (Python standard library only):  python -m app.devserver [port]
Serves the same API as production plus the built React app. Fine for one user on your own PC and for tests;
use uvicorn (app.main) for the cloud."""
import mimetypes, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from app import config
from app.api import dispatch
from app.bootstrap import ensure_owner_from_env
from app.db import connect
from app.schema import create_schema


class Handler(BaseHTTPRequestHandler):
    server_version = "AzeemERP"

    def _send(self, status, headers, content):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _handle(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path.startswith("/api/"):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            self._send(*dispatch(self.command, path, dict(parse_qsl(url.query)), body, self.headers.get("Authorization", "")))
            return
        root = Path(config.FRONTEND_DIST).resolve()
        target = (root / path.lstrip("/")).resolve()
        if root not in target.parents and target != root or not target.is_file():
            target = root / "index.html"          # single-page app: unknown paths show the app
        if not target.is_file():
            self._send(404, {"Content-Type": "text/plain"}, b"frontend not built: run npm run build in the frontend folder")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, {"Content-Type": ctype}, target.read_bytes())

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _handle

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)


def main(port=8000):
    if len(config.SECRET_KEY) < 32:
        sys.exit("Set SECRET_KEY (at least 32 characters) first, e.g.  set SECRET_KEY=your-long-random-text-here")
    db = connect(config.DATABASE_URL)
    create_schema(db)
    ensure_owner_from_env(db)
    db.conn.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AZEEM FRAGRANCES ERP running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
