import io, json, sys, threading, unittest, urllib.request, urllib.error, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import app
from engine.resourcepack import Image

LOG = ("[10:00:00] [main/INFO]: Loading Minecraft 1.20.1 with Fabric Loader 0.15.0\n"
       "[10:00:01] [main/INFO]: Loading 2 mods:\n\t- sodium 0.5\n\t- %s 1.0\n")
def scan(files): return app.run_scan(files, "t")
def zipb(d):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in d.items(): z.writestr(k, v)
    return b.getvalue()

class Engine(unittest.TestCase):
    def test_banned_mod_id_confirmed(self):
        r = scan({"latest.log": (LOG % "meteor-client").encode()})["result"]
        self.assertEqual(r["overall"], "CONFIRMED MATCH"); self.assertEqual(r["findings"][0]["product"], "Meteor Client")
    def test_legit_mods_clean(self):
        self.assertEqual(scan({"latest.log": (LOG % "lithium").encode()})["overall"], "CLEAN IN ANALYZED DATA")
    def test_name_in_chat_not_enough(self):
        log = LOG % "lithium" + "[10:00:05] [Render thread/INFO]: [CHAT] wurst is a cheat\n"
        self.assertEqual(scan({"latest.log": log.encode()})["overall"], "CLEAN IN ANALYZED DATA")
    def test_renamed_jar_filename_only_suspicious(self):
        j = zipb({"fabric.mod.json": json.dumps({"id": "innocent"})})
        self.assertEqual(scan({"Meteor_Client-1.0.jar": j})["overall"], "SUSPICIOUS")
    def test_jar_metadata_confirms(self):
        self.assertEqual(scan({"x.jar": zipb({"fabric.mod.json": json.dumps({"id": "wurst"})})})["overall"], "CONFIRMED MATCH")
    def test_banned_pack_name_suspicious_not_confirmed(self):
        pk = zipb({"pack.mcmeta": json.dumps({"pack": {"pack_format": 15}})})
        r = scan({"Xray Ultimate 1.20.zip": pk})
        self.assertEqual(r["overall"], "SUSPICIOUS"); self.assertIn("not verified", r["result"]["findings"][0]["explanation"])
    def test_pack_hash_confirmed(self):
        import hashlib, tempfile, os
        pk = zipb({"pack.mcmeta": json.dumps({"pack": {"pack_format": 15}})})
        f = Path(tempfile.mkdtemp()) / "b.txt"; f.write_text(f"[resourcepacks]\nsha256:{hashlib.sha256(pk).hexdigest()} | Bad Pack\n")
        old = app.BANNED; app.BANNED = f
        try: self.assertEqual(scan({"whatever.zip": pk})["overall"], "CONFIRMED MATCH")
        finally: app.BANNED = old
    @unittest.skipIf(Image is None, "Pillow missing")
    def test_xray_textures_high_risk(self):
        def png(fn):
            im = Image.new("RGBA", (16, 16)); im.putdata([(1, 1, 1, fn(i)) for i in range(256)]); b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()
        clear, ore = png(lambda i: 0), png(lambda i: 255 if i < 40 else 0)
        t = {f"assets/minecraft/textures/block/{k}.png": clear for k in ("stone", "dirt", "gravel", "andesite")}
        t |= {f"assets/minecraft/textures/block/{k}.png": ore for k in ("diamond_ore", "iron_ore")}
        t["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 15}})
        self.assertEqual(scan({"cool.zip": zipb(t)})["overall"], "HIGH RISK")
    def test_unsafe_inputs(self):
        self.assertEqual(scan({"bad.zip": b"nope"})["overall"], "ANALYSIS ERROR")
        from engine.safe_archive import read_zip
        ex = read_zip(zipb({"../evil": "x", "ok.txt": "y"})); self.assertIn("ok.txt", ex.files); self.assertNotIn("../evil", ex.files)
    def test_bad_banned_file_rejected(self):
        from engine.banned import load_banned
        import tempfile; f = Path(tempfile.mkdtemp()) / "b.txt"; f.write_text("meteor-client\n")
        with self.assertRaises(ValueError): load_banned(f)

class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.serve(port=0); cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()
    def post(self, name, data, case="c"):
        bd = b"XBOUNDX"; body = (b"--" + bd + b'\r\nContent-Disposition: form-data; name="case"\r\n\r\n' + case.encode() +
              b"\r\n--" + bd + b'\r\nContent-Disposition: form-data; name="files"; filename="' + name.encode() + b'"\r\nContent-Type: application/octet-stream\r\n\r\n' + data + b"\r\n--" + bd + b"--\r\n")
        rq = urllib.request.Request(self.url + "/scan", body, {"Content-Type": "multipart/form-data; boundary=XBOUNDX"})
        try:
            with urllib.request.urlopen(rq) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    def test_index_and_scan(self):
        with urllib.request.urlopen(self.url + "/") as r: self.assertIn("Banned list", r.read().decode())
        code, page = self.post("latest.log", (LOG % "meteor-client").encode(), "<b>x</b>")
        self.assertEqual(code, 200); self.assertIn("CONFIRMED MATCH", page); self.assertIn("&lt;b&gt;x", page); self.assertNotIn("<b>x</b>", page)
        self.assertIn("data:application/pdf;base64", page)
    def test_rejects_exe(self): self.assertEqual(self.post("evil.exe", b"MZ")[0], 415)
    def test_hostile_filename_escaped(self):
        code, page = self.post('<script>alert(1)</script>.log', (LOG % "lithium").encode())
        self.assertEqual(code, 200); self.assertNotIn("<script>alert", page)

if __name__ == "__main__": unittest.main()

class LogsZip(unittest.TestCase):
    def test_mod_found_in_each_log_gz_inside_zip(self):
        import gzip
        a = gzip.compress((LOG % "lithium").encode()); b = gzip.compress((LOG % "meteor-client").encode())
        z = zipb({"2026-01-01-1.log.gz": a, "logs/2026-01-02-1.log.gz": b})
        r = scan({"logs.zip": z})["result"]
        self.assertEqual(r["overall"], "CONFIRMED MATCH"); self.assertEqual(len(r["log_table"]), 2)
        mods = {m["mod_id"]: m for m in r["mod_table"]}
        self.assertEqual([x["source"] for x in mods["sodium"]["found_in"]], ["logs.zip!/2026-01-01-1.log.gz", "logs.zip!/logs/2026-01-02-1.log.gz"])
        self.assertEqual([x["source"] for x in mods["meteor-client"]["found_in"]], ["logs.zip!/logs/2026-01-02-1.log.gz"])
        self.assertEqual(mods["meteor-client"]["status"], "banned"); self.assertEqual(r["mod_table"][0]["mod_id"], "meteor-client")
    def test_page_lists_mod_and_log_names_escaped(self):
        import gzip
        z = zipb({"a.log.gz": gzip.compress((LOG % "meteor-client").encode())})
        html_ = app.result_page(scan({"logs.zip": z}))
        self.assertIn("logs.zip › a.log.gz", html_); self.assertIn("meteor-client", html_); self.assertIn("Mods CSV", html_)

def pack_log(line, mods="lithium"):
    return ((LOG % mods) + line + "\n").encode()
RELOAD = "[10:05:00] [Render thread/INFO]: Reloading ResourceManager: vanilla, Fabric Mods, file/%s"

class LogPacks(unittest.TestCase):
    def test_pack_in_reload_line_detected(self):
        r = scan({"latest.log": pack_log(RELOAD % "Xray_Ultimate_1.20.zip")})["result"]
        self.assertEqual(r["overall"], "HIGH RISK"); f = r["findings"][0]
        self.assertEqual(f["product"], "Xray Ultimate"); self.assertEqual(f["evidence"][0]["line"], 5)
        self.assertEqual(len(r["findings"]), 1)                       # no duplicate 'xray' finding
        self.assertEqual(r["pack_table"][0]["status"], "banned")
    def test_forge_style_line_and_generic_xray_name(self):
        line = "[12Jan2024 10:00:00.000] [Render thread/INFO] [net.minecraft.client.resources.ReloadableResourceManager/]: Reloading ResourceManager: vanilla, file/X-Ray 2.zip"
        r = scan({"latest.log": line.encode()})["result"]
        self.assertEqual(r["overall"], "HIGH RISK"); self.assertEqual(r["findings"][0]["product"], "X-ray pack (name)")
    def test_pack_across_logs_gz_in_zip(self):
        import gzip
        z = zipb({"a.log.gz": gzip.compress(pack_log(RELOAD % "xray.zip")), "b.log.gz": gzip.compress(pack_log(RELOAD % "xray.zip")), "c.log.gz": gzip.compress(pack_log(RELOAD % "Faithful.zip"))})
        r = scan({"logs.zip": z})["result"]; t = {p["pack"]: p for p in r["pack_table"]}
        self.assertEqual([x["source"] for x in t["xray.zip"]["found_in"]], ["logs.zip!/a.log.gz", "logs.zip!/b.log.gz"])
        self.assertEqual(t["Faithful.zip"]["status"], "unknown"); self.assertNotIn("vanilla", t); self.assertNotIn("Fabric Mods", t)
    def test_mention_only_is_suspicious(self):
        r = scan({"latest.log": pack_log("[10:05:00] [Render thread/WARN]: Resource pack Xray Ultimate had errors")})["result"]
        self.assertEqual(r["overall"], "SUSPICIOUS"); self.assertEqual(r["findings"][0]["product"], "Xray Ultimate"); self.assertEqual(r["pack_table"], [])
    def test_harmless_pack_is_clean(self):
        self.assertEqual(scan({"latest.log": pack_log(RELOAD % "Faithful 32x.zip")})["overall"], "CLEAN IN ANALYZED DATA")
    def test_page_has_separate_tabs(self):
        h = app.result_page(scan({"latest.log": pack_log(RELOAD % "xray.zip")}))
        for t in ('data-t="mods"', 'data-t="packs"', 'id="t-packs"', "ON BANNED LIST"): self.assertIn(t, h)
        self.assertNotIn('data-t="summary"', h); self.assertNotIn("t-summary", h)
        self.assertLess(h.index('id="t-packs"'), h.index("Xray Ultimate") if "Xray Ultimate" in h else 10**9)   # pack finding sits in the packs tab
    def test_pack_table_only_zip_files(self):
        line = RELOAD % "Faithful.zip" + ", file/FolderPack, sodium, iris, mod_resources"
        names = [x["pack"] for x in scan({"latest.log": pack_log(line)})["result"]["pack_table"]]
        self.assertEqual(names, ["Faithful.zip"])
