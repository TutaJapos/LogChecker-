"""Resource pack inspection. Heuristics only flag packs that hide common blocks while keeping ores visible."""
import hashlib, io, json, re
try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 4096 * 4096
except ImportError:  # texture analysis is skipped, never guessed
    Image = None

HIDE = {"stone", "deepslate", "dirt", "gravel", "netherrack", "andesite", "diorite", "granite", "tuff", "cobblestone"}
ORES = {"diamond_ore", "deepslate_diamond_ore", "iron_ore", "gold_ore", "emerald_ore", "coal_ore", "redstone_ore", "lapis_ore"}
TEX = re.compile(r"^assets/minecraft/textures/block/([a-z0-9_]+)\.png$")

def parse_options(text: str):
    for line in text.splitlines():
        if line.startswith("resourcePacks:"):
            try: return json.loads(line.split(":", 1)[1])
            except ValueError: return None
    return None

def _alpha(b):
    a = Image.open(io.BytesIO(b)).convert("RGBA").getchannel("A").tobytes(); n = len(a) or 1
    return sum(x < 32 for x in a) / n, sum(x >= 200 for x in a) / n

def analyze_pack(name, data, files, sigs):
    r = {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "pack_format": None, "known": None,
         "hidden_common": [], "visible_ores": [], "limits": []}
    try:
        r["pack_format"] = json.loads(files["pack.mcmeta"].decode("utf-8-sig", "replace")).get("pack", {}).get("pack_format")
    except Exception:
        r["limits"].append("pack.mcmeta unreadable")
    for s in sigs:
        if r["sha256"] in s.get("sha256", []): r["known"] = s["name"]
    if Image is None:
        r["limits"].append("Pillow not installed: textures not analyzed"); return r
    for path, b in files.items():
        m = TEX.match(path)
        if not m or len(b) > 2_000_000: continue
        t = m[1]
        if t in HIDE or t in ORES:
            try: transp, opaque = _alpha(b)
            except Exception: r["limits"].append(f"Unreadable texture: {path}"); continue
            if t in HIDE and transp >= 0.9: r["hidden_common"].append(path)
            if t in ORES and opaque >= 0.05: r["visible_ores"].append(path)
    return r

def active_status(name, enabled):
    base = name.split("/")[-1].split("!")[0]
    if enabled is None: return "unknown: no options.txt provided; presence of a pack does not show it was enabled"
    if f"file/{base}" in enabled: return "listed as enabled in the supplied options.txt snapshot (not proof of use in a specific session)"
    return "not listed as enabled in the supplied options.txt"

def _n(s): return re.sub(r"[\s_\-]+", "", s.lower())

def pack_findings(packs, enabled, sigs, Finding, LIMITS):
    out = []
    for p in packs:
        base = p["file"].split("/")[-1].split("!")[0]
        bn = _best(base, sigs); named = next((s for s in sigs if s["name"] == bn), None)
        st = active_status(p["file"], enabled); nxt = "Review the pack manually against vanilla textures; confirm in-game with the player's consent."
        ev = [{"source": p["file"], "field": "sha256", "value": p["sha256"]}]
        ev += [{"source": p["file"], "field": "asset path", "value": x} for x in (p["hidden_common"] + p["visible_ores"])[:10]]
        if p["known"]:
            out.append(Finding(p["known"], "Known prohibited resource pack", "CONFIRMED MATCH", "high", ev,
                f"Pack hash matches a verified signature. Activity: {st}.", LIMITS, "", nxt))
        elif len(p["hidden_common"]) >= 3 and len(p["visible_ores"]) >= 2:
            out.append(Finding(named["name"] if named else "X-ray-like resource pack", "Resource pack: strong X-ray indicators", "HIGH RISK", "medium", ev,
                f"{len(p['hidden_common'])} common block textures are almost fully transparent while {len(p['visible_ores'])} ore textures remain visible. Activity: {st}.",
                LIMITS, "Some accessibility or experimental packs also hide blocks.", nxt))
        elif named:
            out.append(Finding(named["name"], "Resource pack: listed in banned.txt (filename match)", "SUSPICIOUS", "low", ev[:1],
                f"The filename matches banned pack '{named['name']}', but no pack hash is listed, so identity is not verified. Activity: {st}.",
                LIMITS, "A renamed harmless pack would match too; filenames are arbitrary.", nxt))
        elif p["hidden_common"]:
            out.append(Finding("Resource pack with transparent block textures", "Resource pack: unusual textures", "SUSPICIOUS", "low", ev,
                f"Some common blocks are transparent but the X-ray pattern is incomplete. Activity: {st}.", LIMITS,
                "Legitimate packs may alter these textures.", nxt))
        elif re.search(r"x-?ray", p["file"], re.I):
            out.append(Finding("Resource pack named like X-ray pack", "Resource pack: filename only", "SUSPICIOUS", "low", ev[:1],
                f"The filename suggests an X-ray pack but contents show no X-ray indicators (limits: {p['limits'] or 'none'}). Activity: {st}.",
                LIMITS, "Filenames are arbitrary and easily changed.", nxt))
    return out


def _best(text, sigs):
    """Most specific banned-pack entry whose name appears in text (longest normalized match wins)."""
    best = None
    for s in sigs:
        for nm in s.get("names", []):
            k = _n(nm)
            if k and k in _n(text) and (best is None or len(k) > best[0]): best = (len(k), s["name"])
    return best[1] if best else None

def _log_hits(logs, sigs):
    res = {}
    for lg in logs:
        rl_lines = {r["ev"].line for r in lg.reloads}
        for r in lg.reloads:
            for b in {_best(p, sigs) for p in r["packs"]} - {None}: res.setdefault(b, ([], []))[0].append(r["ev"])
        for e in lg.pack_events:
            b = _best(e.text, sigs)
            if b and e.line not in rl_lines: res.setdefault(b, ([], []))[1].append(e)
    return res

def _evd(e): return {"source": e.source, "line": e.line, "timestamp": e.timestamp, "text": e.text}

def log_pack_findings(logs, sigs, Finding, LIMITS):
    out = []
    for name, (rel, men) in _log_hits(logs, sigs).items():
        if rel:
            seen, first = set(), []
            for e in rel:
                if e.source not in seen: seen.add(e.source); first.append(e)
            out.append(Finding(name, "Resource pack: listed as enabled in game log", "HIGH RISK", "medium", [_evd(e) for e in first[:10]],
                f"The game's own 'Reloading ResourceManager' line lists a pack whose name matches banned entry '{name}' in {len(seen)} log file(s) ({len(rel)} reload event(s)). "
                "That shows a pack with this name was enabled at those reloads. The match is by name only; the pack contents were not inspected.",
                LIMITS, "A harmless pack renamed to match would also appear; names are arbitrary.",
                "Ask for the pack file (or its SHA-256) and compare its textures with vanilla; check the player's resourcepacks folder."))
        else:
            out.append(Finding(name, "Resource pack: mentioned in log", "SUSPICIOUS", "low", [_evd(e) for e in men[:10]],
                f"A resource-pack log message mentions a name matching banned entry '{name}', but no resource reload line shows it was enabled.",
                LIMITS, "A mention (an error, a folder scan) does not prove the pack was active.",
                "Look for a 'Reloading ResourceManager' line in nearby logs and request the pack file."))
    return out

def build_pack_table(logs, packs, sigs):
    idx = {}
    row = lambda key, user: idx.setdefault(key, {"user": user, "rel": {}, "extra": [], "up": None, "mention": False})
    for lg in logs:
        for r in lg.reloads:
            for nm in r["packs"]:
                key = nm[5:] if nm.startswith("file/") else nm
                d = row(key, nm.startswith("file/")); s = d["rel"].setdefault(lg.source, [r["ev"].line, 0]); s[1] += 1
    for p in packs:
        d = row(p["file"].split("/")[-1].split("!")[0], True)
        d["extra"].append({"source": p["file"], "line": None, "how": "uploaded pack file"}); d["up"] = p
    for name, (rel, men) in _log_hits(logs, sigs).items():
        if not rel and men:
            d = row(name, True); d["mention"] = True
            d["extra"] += [{"source": e.source, "line": e.line, "how": "mentioned in a log message (not shown enabled)"} for e in men[:50]]
    out = []
    for key, d in idx.items():
        up = d["up"]
        if d["mention"]: st = "mentioned"
        elif _best(key, sigs) or (up and up["known"]): st = "banned"
        elif up and len(up["hidden_common"]) >= 3 and len(up["visible_ores"]) >= 2: st = "xray-like"
        else: st = "unknown" if d["user"] else "built-in"
        fi = [{"source": s, "line": v[0], "how": "enabled at game resource reload" + (f" (x{v[1]})" if v[1] > 1 else "")} for s, v in d["rel"].items()] + d["extra"]
        note = f"{len(up['hidden_common'])} common blocks hidden, {len(up['visible_ores'])} ores visible; sha256 {up['sha256'][:12]}" if up else ""
        out.append({"pack": key, "status": st, "found_in": sorted(fi, key=lambda x: x["source"]), "note": note})
    out = [x for x in out if x["pack"].lower().endswith(".zip")]   # table lists .zip packs only (no vanilla / mod resource entries)
    order = ["banned", "xray-like", "mentioned", "unknown", "built-in"]
    return sorted(out, key=lambda x: (order.index(x["status"]), x["pack"].lower()))
