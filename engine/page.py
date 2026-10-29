"""HTML pages for the web UI. Every dynamic value is escaped."""
import base64, csv, html, io
from . import reports

E = html.escape
COLORS = {"CONFIRMED MATCH": "#EF4444", "HIGH RISK": "#F59E0B", "SUSPICIOUS": "#F59E0B", "INCONCLUSIVE": "#9CA3AF",
          "CLEAN IN ANALYZED DATA": "#42D392", "ANALYSIS ERROR": "#9CA3AF"}
MESSAGE = {"CONFIRMED MATCH": "A banned item was identified with specific evidence. Review it before acting.",
           "HIGH RISK": "Strong indicators of a banned item, not fully verified.",
           "SUSPICIOUS": "Something needs a manual check. This is not proof.",
           "INCONCLUSIVE": "Not enough information in these files to decide.",
           "CLEAN IN ANALYZED DATA": "Nothing banned was found in these files. This does not guarantee the player is clean.",
           "ANALYSIS ERROR": "The files could not be analyzed reliably."}
MOD_LABEL = {"banned": ("BANNED", "red"), "unknown": ("UNKNOWN", "amber"), "allowlisted": ("ALLOWED", "green")}
PACK_LABEL = {"banned": ("ON BANNED LIST", "red"), "xray-like": ("X-RAY-LIKE", "red"), "mentioned": ("MENTIONED ONLY", "amber"),
              "unknown": ("NOT ON LIST", "grey"), "built-in": ("BUILT-IN", "grey")}
CSS = """*{box-sizing:border-box}body{margin:0;background:#0B0F14;color:#E5E7EB;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:#42D392;text-decoration:none}a:hover{text-decoration:underline}.wrap{max-width:980px;margin:0 auto;padding:0 18px 50px}
.top{border-bottom:1px solid #1f2937}.top .wrap{display:flex;align-items:center;padding:14px 18px}.logo{font-weight:700;font-size:17px}.logo b{color:#42D392}.sp{flex:1}
.btn{display:inline-block;background:#42D392;color:#0B0F14;border:0;border-radius:8px;padding:9px 16px;font-weight:600;cursor:pointer;font-size:14px}.btn:hover{text-decoration:none;filter:brightness(1.08)}.btn:disabled{opacity:.6}
.card{background:#151B23;border:1px solid #1f2937;border-radius:12px;padding:18px;margin-top:16px}h2{font-size:16px;margin:0 0 10px}.muted{color:#9CA3AF}.small{font-size:13px}
.verdict{border-left:6px solid var(--c);margin-top:20px}.verdict h1{margin:0;font-size:24px;color:var(--c)}
.tabs{display:flex;gap:6px;margin-top:20px;border-bottom:1px solid #1f2937}.tab{background:none;border:0;color:#9CA3AF;padding:10px 16px;cursor:pointer;font-size:15px;border-bottom:3px solid transparent}
.tab.on{color:#E5E7EB;border-color:#42D392}.dot{background:#EF4444;color:#fff;border-radius:999px;font-size:12px;padding:1px 7px;margin-left:6px}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700;color:#0B0F14}.red{background:#EF4444}.amber{background:#F59E0B}.green{background:#42D392}.grey{background:#6B7280;color:#fff}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:#9CA3AF;font-weight:600;padding:8px 10px;border-bottom:1px solid #263041}
td{padding:9px 10px;border-bottom:1px solid #1b2430;vertical-align:top}tr:hover td{background:#18202b}tr[hidden],.pane[hidden]{display:none}
code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}pre{background:#0B0F14;border-radius:8px;padding:10px;overflow-x:auto;margin:6px 0;white-space:pre-wrap;word-break:break-all}
details summary{cursor:pointer;color:#42D392}details ul{margin:6px 0 0;padding-left:18px;max-height:220px;overflow:auto}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 10px}.chip{background:#1b2430;color:#E5E7EB;border:0;border-radius:999px;padding:5px 14px;cursor:pointer;font-size:13px}.chip.on{background:#42D392;color:#0B0F14}
input[type=search],input[type=text]{background:#0B0F14;border:1px solid #263041;color:#E5E7EB;border-radius:8px;padding:8px 12px;font-size:14px}
.find{border-left:5px solid var(--c)}.find h3{margin:0 0 6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:17px}.lbl{color:#9CA3AF;font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-top:10px}
.dz{border:2px dashed #2b3647;border-radius:14px;padding:44px 20px;text-align:center;cursor:pointer}.dz.over{border-color:#42D392;background:#122019}.dz big{display:block;font-size:19px;margin-bottom:4px}
.fl{list-style:none;padding:0;margin:12px 0 0}.fl li{padding:3px 0;color:#cbd5e1}.hero2{padding:34px 0 4px}.hero2 h1{font-size:28px;margin:0 0 6px}.hero2 h1 b{color:#42D392}"""

def nice(src): return " › ".join(str(src).split("!/"))
def _uri(mime, b): return f"data:{mime};base64," + base64.b64encode(b).decode()
def shell(body, extra=""):
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Minecraft Log Analyzer</title><style>{CSS}</style>{body}{extra}</html>'

def _csv(mods):
    out = io.StringIO(); w = csv.writer(out); w.writerow(["mod_id", "versions", "status", "log_count", "found_in"])
    safe = lambda v: "'" + v if v[:1] in ("=", "+", "-", "@") else v
    for m in mods:
        w.writerow([safe(m["mod_id"]), safe(", ".join(m["versions"])), m["status"], len(m["found_in"]),
                    safe("; ".join(x["source"] + (f":{x['line']}" if x["line"] else "") for x in m["found_in"]))])
    return out.getvalue().encode()

def render_index(info):
    body = f"""<div class="top"><div class="wrap"><div class="logo">⛏ Minecraft <b>Log Analyzer</b></div></div></div>
<div class="wrap"><div class="hero2"><h1>Check logs for <b>banned mods and packs</b></h1><p class="muted">Upload logs, a logs.zip of .log.gz files, mod JARs or resource packs.</p></div>
<form class="card" method="post" action="/scan" enctype="multipart/form-data" id="form">
<input type="text" name="case" placeholder="Case or player name (optional)" maxlength="200" style="width:100%;margin-bottom:14px">
<div class="dz" id="dz"><big>Drop files here or click to choose</big><span class="muted small">.log .gz .zip .jar .txt</span></div>
<input type="file" id="f" name="files" multiple required hidden accept=".log,.txt,.gz,.zip,.jar"><ul class="fl" id="list"></ul>
<button class="btn" id="go" style="margin-top:14px">Scan files</button></form>
<p class="muted small">Banned list: {E(info)}. Edit <code>banned.txt</code> to change it. Files are read in memory, never run, and not stored. Results are evidence for a human reviewer, not a verdict.</p></div>"""
    js = """<script>const f=document.getElementById('f'),dz=document.getElementById('dz'),ls=document.getElementById('list');
function show(){ls.replaceChildren();for(const x of f.files){const li=document.createElement('li');li.textContent=x.name+'  ('+Math.round(x.size/1024)+' KB)';ls.appendChild(li)}}
dz.onclick=()=>f.click();f.onchange=show;dz.ondragover=e=>{e.preventDefault();dz.classList.add('over')};dz.ondragleave=()=>dz.classList.remove('over');
dz.ondrop=e=>{e.preventDefault();dz.classList.remove('over');f.files=e.dataTransfer.files;show()};
document.getElementById('form').onsubmit=()=>{const b=document.getElementById('go');b.textContent='Analyzing... please wait';setTimeout(()=>b.disabled=true,0)}</script>"""
    return shell(body, js)

def _finding(f):
    c = COLORS.get(f["classification"], "#9CA3AF")
    ev = "".join(f"<pre>{E(' | '.join(f'{k}: {nice(v) if k == 'source' else v}' for k, v in e.items() if v is not None))}</pre>" for e in f["evidence"]) or '<p class="muted">No direct evidence recorded.</p>'
    return (f'<div class="card find" style="--c:{c}"><h3>{E(f["product"])} <span class="pill" style="background:{c}">{E(f["classification"])}</span></h3>'
            f'<div class="muted small">{E(f["category"])} · confidence {E(f["confidence"])}</div>'
            f'<div class="lbl">Verified facts from the files</div>{ev}<div class="lbl">Automated inference (not proof)</div><div>{E(f["explanation"])}</div>'
            f'<details style="margin-top:10px"><summary>Limitations and what to verify</summary><p><b>Limitations:</b> {E(f["limitations"])}</p>'
            f'<p><b>Possible false positives:</b> {E(f["false_positives"] or "none recorded")}</p><p><b>Verify:</b> {E(f["next_steps"])}</p></details></div>')

def _table(tid, qid, head, rows, chips, empty):
    chip = "".join(f'<button class="chip{" on" if i == 0 else ""}" data-for="{tid}" data-s="{s}">{E(l)}</button>' for i, (s, l) in enumerate(chips))
    return (f'<div class="bar"><input type="search" id="{qid}" placeholder="Search..." style="flex:1;min-width:180px">{chip}</div><div class="tw"><table id="{tid}"><thead><tr>'
            + "".join(f"<th>{E(h)}</th>" for h in head) + f'</tr></thead><tbody>{rows or f"<tr><td colspan={len(head)} class=muted>{E(empty)}</td></tr>"}</tbody></table></div>')

def _where(items):
    n = len(items)
    return (f'<details><summary>{n} file{"s" if n != 1 else ""}</summary><ul>' + "".join(
        f'<li>{E(nice(x["source"]))}' + (f' <span class="muted">line {x["line"]}</span>' if x.get("line") else "") + (f' <span class="muted">· {E(x["how"])}</span>' if x.get("how") else "") + "</li>" for x in items) + "</ul></details>")

def render_result(scan):
    r, ov = scan["result"], scan["overall"]; c = COLORS.get(ov, "#9CA3AF"); mods, packs = r["mod_table"], r["pack_table"]
    nb_m = sum(m["status"] == "banned" for m in mods); nb_p = 0
    dl = " · ".join(f'<a download="{n}" href="{u}">{l}</a>' for n, u, l in [
        ("report.html", _uri("text/html", reports.to_html(scan).encode()), "HTML"), ("report.pdf", _uri("application/pdf", reports.to_pdf(scan)), "PDF"),
        ("report.json", _uri("application/json", reports.to_json(scan).encode()), "JSON"), ("mods.csv", _uri("text/csv", _csv(mods)), "Mods CSV")])
    mrows = "".join(
        f'<tr data-s="{E(m["status"])}" data-q="{E((m["mod_id"] + " " + " ".join(m["versions"]) + " " + " ".join(x["source"] for x in m["found_in"])).lower())}">'
        f'<td><b>{E(m["mod_id"])}</b></td><td>{E(", ".join(m["versions"]))}</td><td><span class="pill {MOD_LABEL[m["status"]][1]}">{MOD_LABEL[m["status"]][0]}</span></td><td>{_where(m["found_in"])}</td></tr>' for m in mods)
    prows = "".join(
        f'<tr data-s="{"flagged" if p["status"] in ("banned", "xray-like", "mentioned") else "other"}" data-q="{E((p["pack"] + " " + " ".join(x["source"] for x in p["found_in"])).lower())}">'
        f'<td><b>{E(p["pack"])}</b><div class="muted small">{E(p["note"])}</div></td><td><span class="pill {PACK_LABEL[p["status"]][1]}">{PACK_LABEL[p["status"]][0]}</span></td><td>{_where(p["found_in"])}</td></tr>' for p in packs)
    logs = "".join(f'<tr><td>{E(nice(l["source"]))}</td><td>{E(l["minecraft"] or "?")}</td><td>{E(((l["loader"] or "?") + " " + (l["loader_version"] or "")).strip())}</td><td>{l["mods"]}</td></tr>' for l in r["log_table"])
    issues = [f'{e["file"]}: {e["error"]}' for e in r["errors"]] + r["warnings"]
    pf = [f for f in r["findings"] if f["category"].startswith("Resource pack")]; mf = [f for f in r["findings"] if not f["category"].startswith("Resource pack")]
    cards = lambda fs: "".join(_finding(f) for f in fs)
    dot = lambda n: f'<span class="dot">{n}</span>' if n else ""
    logs_card = (f'<div class="card"><details><summary>{len(r["log_table"])} log file(s) analyzed</summary><div class="tw"><table><thead><tr><th>File</th><th>Minecraft</th><th>Loader</th><th>Mods listed</th></tr></thead><tbody>{logs}</tbody></table></div></details></div>' if logs else "")
    problems = (f'<details style="margin-top:8px"><summary>{len(issues)} problem(s) reading files</summary><ul>{"".join(f"<li>{E(i)}</li>" for i in issues)}</ul></details>' if issues else "")
    body = f"""<div class="top"><div class="wrap"><div class="logo">⛏ Minecraft <b>Log Analyzer</b></div><div class="sp"></div><a class="btn" href="/">New scan</a></div></div><div class="wrap">
<div class="card verdict" style="--c:{c}"><h1>{E(ov)}</h1><div>{E(MESSAGE.get(ov, ""))}</div>
<div class="muted small" style="margin-top:6px">{E(scan.get("case") or "No case name")} · {E(scan["created"])} · Download: {dl}</div>{problems}</div>
<div class="tabs"><button class="tab on" data-t="mods">Mods ({len(mods)}){dot(len(mf))}</button><button class="tab" data-t="packs">Resource packs ({len(packs)}){dot(len(pf))}</button></div>
<div class="pane" id="t-mods">{cards(mf)}<div class="card"><h2>Mods and the files they appear in</h2>{_table("mods", "mq", ["Mod", "Version", "Status", "Found in"], mrows, [("all", f"All {len(mods)}"), ("banned", f"Banned {nb_m}"), ("unknown", "Unknown"), ("allowlisted", "Allowed")], "No mod list was found in these files.")}
<p class="muted small">From the loader's mod list in each log and from JAR metadata. A mod missing from one log may simply not be listed there.</p></div>{logs_card}</div>
<div class="pane" id="t-packs" hidden>{cards(pf)}<div class="card"><h2>Resource packs (.zip) and the files they appear in</h2>{_table("packs", "pq", ["Pack", "Status", "Found in"], prows, [("all", f"All {len(packs)}"), ("flagged", "Flagged"), ("other", "Other")], "No .zip resource packs were found in these files.")}
<p class="muted small">Only .zip packs are listed. Sources: the game's "Reloading ResourceManager" lines (packs enabled at that moment) and uploaded pack files. A flagged pack that is not a .zip (for example a folder) still shows as a finding above the table.</p></div></div>
<p class="muted small" style="margin-top:20px">{E(r["note"])}</p></div>"""
    js = """<script>function tbl(id,q){const rows=[...document.querySelectorAll('#'+id+' tbody tr[data-s]')],cs=[...document.querySelectorAll('[data-for="'+id+'"]')];let st='all',t='';
const ap=()=>rows.forEach(r=>r.hidden=!((st==='all'||r.dataset.s===st)&&r.dataset.q.includes(t)));
cs.forEach(c=>c.onclick=()=>{st=c.dataset.s;cs.forEach(x=>x.classList.toggle('on',x===c));ap()});document.getElementById(q).oninput=e=>{t=e.target.value.toLowerCase();ap()}}
tbl('mods','mq');tbl('packs','pq');
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));document.querySelectorAll('.pane').forEach(p=>p.hidden=p.id!=='t-'+b.dataset.t)})</script>"""
    return shell(body, js)
