"""HTML / JSON / PDF reports. Separates verified facts (from files) from automated inferences."""
import html, json, textwrap

def _ev(e): return " | ".join(f"{k}: {v}" for k, v in e.items() if v is not None)

def _sections(scan):
    r = scan["result"]
    S = [("Scan metadata", [f"Case: {scan.get('case') or '(none)'}", f"Scan ID: {scan.get('id')}", f"Date: {scan.get('created')}",
          f"Overall classification (automated): {scan['overall']}", f"Detection database version: {r.get('db_version')}",
          f"Policy version: {r.get('policy_version')}", r.get("note", "")]),
         ("File inventory (uploaded names)", list(scan.get("files") or ["(none)"]))]
    for p in r.get("resource_packs", []):
        S[1][1].append(f"Resource pack {p['file']} sha256={p['sha256']} pack_format={p['pack_format']}")
    for f in r["findings"]:
        L = ["VERIFIED FACTS (read directly from uploaded files):"] + ["  " + _ev(e) for e in f["evidence"]]
        L += ["AUTOMATED INFERENCE (not proof):", f"  Category: {f['category']}", f"  Classification: {f['classification']}",
              f"  Confidence: {f['confidence']}", f"  Server policy: {f.get('policy')}", f"  Explanation: {f['explanation']}",
              f"LIMITATIONS: {f['limitations']}", f"POSSIBLE FALSE POSITIVES: {f['false_positives'] or 'none recorded'}",
              f"RECOMMENDED VERIFICATION: {f['next_steps']}"]
        S.append((f"Finding: {f['product']}", L))
    S.append(("Mods", [f"Allowlisted/legitimate: {', '.join(r['legitimate_mods']) or 'none'}",
                       f"Unknown (need review): {', '.join(r['unknown_mods']) or 'none'}"]))
    S.append(("Mod locations (mod, versions, status: found in)", [
        f"{m['mod_id']} {', '.join(m['versions'])} [{m['status']}]: " + ", ".join(x["source"] + (f":{x['line']}" if x["line"] else "") for x in m["found_in"][:15])
        + (f" (+{len(m['found_in']) - 15} more)" if len(m["found_in"]) > 15 else "") for m in r.get("mod_table", [])] or ["none"]))
    S.append(("Resource pack locations (pack, status: found in)", [
        f"{m['pack']} [{m['status']}]: " + ", ".join(x["source"] + (f":{x['line']}" if x["line"] else "") for x in m["found_in"][:15])
        + (f" (+{len(m['found_in']) - 15} more)" if len(m["found_in"]) > 15 else "") for m in r.get("pack_table", [])] or ["none"]))
    S.append(("Processing issues", [f"{e['file']}: {e['error']}" for e in r["errors"]] + r["warnings"] + r["log_notes"] or ["none"]))
    S.append(("Limitations and recommended actions", [
        "This report only reflects the files supplied. Absence of findings does not prove a player is cheat-free.",
        "A mod or pack listed in a log is not proof it was active. Review all findings manually before applying penalties."]))
    return S

def to_json(scan): return json.dumps(scan, indent=2, default=str)

def to_html(scan):
    e = html.escape
    body = "".join(f"<h2>{e(h)}</h2><ul>" + "".join(f"<li>{e(str(l))}</li>" for l in L) + "</ul>" for h, L in _sections(scan))
    return ("<!doctype html><meta charset=utf-8><title>MCLA report</title><style>body{background:#0B0F14;color:#e5e7eb;font:15px system-ui;"
            "max-width:900px;margin:2rem auto;padding:0 1rem}h2{color:#42D392}li{margin:.3rem 0;white-space:pre-wrap}</style>"
            f"<h1>Minecraft Log Analyzer report</h1>{body}")

def _esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def to_pdf(scan):
    lines = []
    for h, L in _sections(scan):
        lines += ["", h.upper()] + [w for l in L for w in (textwrap.wrap(str(l), 100) or [""])]
    pages = [lines[i:i + 55] for i in range(0, len(lines), 55)] or [[]]
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for i, pg in enumerate(pages):
        kids.append(f"{4 + 2 * i} 0 R")
        s = "BT /F1 9 Tf 40 800 Td 14 TL " + " ".join(f"({_esc(l)}) Tj T*" for l in pg) + " ET"
        s = s.encode("latin-1", "replace")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(s) + s + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return bytes(out)
