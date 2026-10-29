"""Minecraft Log Analyzer - simple version. Standard library only (Pillow optional for texture checks).
Run:  python app.py      then open http://127.0.0.1:8000"""
import html, os, re, sys, traceback
from datetime import datetime
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from engine import detection, page
from engine.banned import load_banned

BASE = Path(__file__).parent
BANNED = Path(os.environ.get("MCLA_BANNED", BASE / "banned.txt"))
MAX_BODY = int(os.environ.get("MCLA_MAX_MB", "200")) * 1024 * 1024
ALLOWED = (".log", ".txt", ".gz", ".zip", ".jar")

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
    mods, packs, rules, version = load_banned(BANNED)
    detection.DB["prohibited"], detection.DB["resource_packs"], detection.DB["db_version"] = mods, packs, version
    stamp = datetime.fromtimestamp(BANNED.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    result = detection.analyze(files, {"version": f"banned.txt saved {stamp}", "rules": rules})
    return {"id": "-", "case": case, "created": datetime.now().isoformat(timespec="seconds"),
            "files": list(files), "overall": result["overall"], "result": result}

def result_page(scan): return page.render_result(scan)

def index_page():
    try: info = load_banned(BANNED)[3]
    except Exception as e: info = f"banned.txt problem: {e}"
    return page.render_index(info)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(b)
    def _err(self, code, msg): self._send(code, f'<p style="font-family:sans-serif">{html.escape(msg)} <a href="/">Back</a></p>')
    def do_GET(self):
        if self.path == "/": self._send(200, index_page())
        else: self._err(404, "Not found")
    def do_POST(self):
        if self.path != "/scan": return self._err(404, "Not found")
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY: return self._err(413, f"Upload must be under {MAX_BODY // 1048576} MB in total")
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"): return self._err(400, "Expected a file upload")
            fields, raw = parse_multipart(ctype, self.rfile.read(n))
            files = {}
            for fn, data in raw.items():
                name = clean_name(fn)
                if not name.lower().endswith(ALLOWED): return self._err(415, f"Unsupported file type: {name}")
                files[name if name not in files else f"{len(files)}_{name}"] = data
            if not files: return self._err(400, "No files uploaded")
            self._send(200, result_page(run_scan(files, fields.get("case", "").strip()[:200])))
        except ValueError as e: self._err(400, str(e))
        except Exception:
            traceback.print_exc(); self._err(500, "Internal error - see the console for details")
    def log_message(self, fmt, *a): sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))

def serve(host="127.0.0.1", port=8000):
    srv = ThreadingHTTPServer((host, port), Handler); print(f"Open http://{host}:{srv.server_address[1]}  (Ctrl+C to stop)"); return srv

if __name__ == "__main__":
    serve(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000"))).serve_forever()
