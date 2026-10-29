import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

class Deploy(unittest.TestCase):
    def test_static_front_page_posts_to_scan(self):
        h = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        for t in ('action="/scan"', 'enctype="multipart/form-data"', "const MAXMB=4;",): self.assertIn(t, h)
        self.assertNotIn("/admin", h)
    def test_vercel_config(self):
        v = json.loads((ROOT / "vercel.json").read_text())
        self.assertEqual(v["rewrites"][0]["destination"], "/api/index"); self.assertIn("api/index.py", v["functions"])
    def test_entry_imports_and_has_handler(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("entry", ROOT / "api" / "index.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        from http.server import BaseHTTPRequestHandler
        self.assertTrue(issubclass(m.handler, BaseHTTPRequestHandler))
    def test_no_conflicting_entrypoint_names(self):
        for n in ("app.py", "server.py", "main.py", "index.py", "wsgi.py", "asgi.py"): self.assertFalse((ROOT / n).exists(), n)
    def test_admin_routes_are_gone(self):
        import http.client, threading, mcla_app
        srv = mcla_app.serve(port=0); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for m, path in (("GET", "/admin"), ("POST", "/admin/login"), ("POST", "/admin/add")):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1]); c.request(m, path, "" if m == "POST" else None); self.assertEqual(c.getresponse().status, 404)
        finally: srv.shutdown()
    def test_no_admin_code_left(self):
        for f in ("auth.py", "store.py"): self.assertFalse((ROOT / "engine" / f).exists())
        self.assertNotIn("ADMIN_PASSWORD", (ROOT / "mcla_app.py").read_text())
if __name__ == "__main__": unittest.main()
