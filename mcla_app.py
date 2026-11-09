"""Minecraft Log Analyzer. Standard library only (Pillow optional for texture checks).
Local:  python mcla_app.py   -> http://127.0.0.1:8000        Vercel: see api/index.py and README.
The blacklist is the plain-text file banned.txt (edit it by hand)."""
import hashlib, html, os, re, sys, traceback
from datetime import datetime
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from engine import banned, detection, page

BASE = Path(__file__).parent
BANNED = Path(os.environ.get("MCLA_BANNED", BASE / "banned.txt"))
ALLOWED = (".log", ".txt", ".gz", ".zip", ".jar")

def max_mb(): return int(os.environ.get("MCLA_MAX_MB") or ("4" if os.environ.get("VERCEL") else "200"))  # Vercel rejects bodies over ~4.5 MB

def clean_name(n):
    return re.sub(r"[^A-Za-z0-9._ -]", "_", (n or "file").replace("\\", "/").split("/")[-1])[:120] or "file"

def parse_multipart(ctype, body):
    msg = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    fields, files = {}, {}
    for part in msg.iter_parts():
        name, fn, data = part.get_param("name", header="content-disposition"), part.get_filename(), part.get_payload(decode=True) or b""
        if fn is not None:
            if fn: files[fn] = data
        elif name: fields[name] = data.decode("utf-8", "replace")
    return fields, files

def run_scan(files, case):
    text = BANNED.read_text(encoding="utf-8")          # re-read on every scan
    mods, packs, rules, version = banned.parse_banned(text)
    detection.DB["prohibited"], detection.DB["resource_packs"], detection.DB["db_version"] = mods, packs, version
    tag = "banned.txt #" + hashlib.sha256(text.encode()).hexdigest()[:8]
    result = detection.analyze(files, {"version": tag, "rules": rules})
    return {"id": "-", "case": case, "created": datetime.now().isoformat(timespec="seconds"),
            "files": list(files), "overall": result["overall"], "result": result}

def result_page(scan): return page.render_result(scan)

def index_page():
    try: info = banned.load_banned(BANNED)[3]
    except Exception as e: info = f"banned.txt problem: {e}"
    return page.render_index(info, max_mb())

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        for k, v in (("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"), ("Cache-Control", "no-store")):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def _err(self, code, msg): self._send(code, f'<p style="font-family:sans-serif">{html.escape(msg)} <a href="/">Back</a></p>')
    def _path(self):
        p = urlsplit(self.path).path
        if p.startswith("/api/index"): p = p[len("/api/index"):]      # Vercel rewrite prefix
        return p.rstrip("/") or "/"
    def do_GET(self):
        path = self._path()
        if path == "/": return self._send(200, index_page())
        if path == "/health": return self._send(200, "ok", "text/plain; charset=utf-8")
        self._err(404, "Not found")
    def do_POST(self):
        if self._path() != "/scan": return self._err(404, "Not found")
        try:
            limit = max_mb() * 1048576; n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > limit: return self._err(413, f"Upload must be under {max_mb()} MB in total")
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"): return self._err(400, "Expected a file upload")
            fields, raw = parse_multipart(ctype, self.rfile.read(n)); files = {}
            for fn, data in raw.items():
                name = clean_name(fn)
                if not name.lower().endswith(ALLOWED): return self._err(415, f"Unsupported file type: {name}")
                files[name if name not in files else f"{len(files)}_{name}"] = data
            if not files: return self._err(400, "No files uploaded")
            self._send(200, result_page(run_scan(files, fields.get("case", "").strip()[:200])))
        except ValueError as e: self._err(400, str(e))
        except Exception: traceback.print_exc(); self._err(500, "Internal error - see the server log for details")
    def log_message(self, fmt, *a): sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))

def serve(host="127.0.0.1", port=8000):
    srv = ThreadingHTTPServer((host, port), Handler); print(f"Open http://{host}:{srv.server_address[1]}  (Ctrl+C to stop)"); return srv

if __name__ == "__main__":
    serve(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000"))).serve_forever()
