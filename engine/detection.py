import json, re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from .logparser import parse_log, ParsedLog
from .metadata import inspect_jar
from .safe_archive import read_zip, read_gzip, ArchiveError
from .resourcepack import analyze_pack, pack_findings, parse_options, log_pack_findings, build_pack_table

DB = json.loads((Path(__file__).parent / "signatures.json").read_text())
ORDER = ["CONFIRMED MATCH", "HIGH RISK", "SUSPICIOUS", "INCONCLUSIVE", "CLEAN IN ANALYZED DATA"]

@dataclass
class Finding:
    product: str; category: str; classification: str; confidence: str
    evidence: list; explanation: str; limitations: str; false_positives: str; next_steps: str; policy: str = None

LIMITS = ("Does not establish which features were used, whether this occurred in a specific session, "
          "or that the files represent the full client installation.")

def _finding(sig, cls, conf, ev, why, nxt):
    return Finding(sig["name"], sig["category"], cls, conf, ev, why, LIMITS, sig.get("false_positives", ""), nxt)

def match_signatures(logs, jars, policy=None):
    findings = []
    for sig in DB["prohibited"]:
        ids = set(sig["mod_ids"]); ev = []; cls = None
        for j in jars:
            hit = ids & set(j["mod_ids"])
            if hit:
                ev.append({"source": j["file"], "field": "mod id in " + ",".join(j["meta_files"]), "value": sorted(hit)[0]}); cls = "CONFIRMED MATCH"
        for lg in logs:
            for mid, (ver, e) in lg.mods.items():
                if mid in ids:
                    ev.append({"source": e.source, "line": e.line, "timestamp": e.timestamp, "text": e.text}); cls = "CONFIRMED MATCH"
        if cls:
            findings.append(_finding(sig, cls, "high", ev, "A mod ID belonging to this known product was found in loader-reported or JAR metadata.",
                                     "Verify the identifier and file hashes before applying penalties.")); continue
        pk = []
        for j in jars:
            for p in j["packages"]:
                if any(p.startswith(s) or s.startswith(p) for s in sig["packages"]):
                    pk.append({"source": j["file"], "field": "class package", "value": p})
        refs = []
        for lg in logs:
            for name, e in lg.loggers.items():
                if name.lower().replace(" ", "-") in ids or name.lower() in sig["aliases"]:
                    refs.append({"source": e.source, "line": e.line, "timestamp": e.timestamp, "text": e.text})
        if pk or refs:
            findings.append(_finding(sig, "HIGH RISK" if (pk and refs) else "SUSPICIOUS", "medium", (pk + refs)[:10],
                                     "Indicators (package names and/or log references) point to this product, but no verified mod ID was found.",
                                     "Request the actual mod JAR or full mods folder for verification."))
            continue
        fn = [{"source": j["file"], "field": "filename", "value": j["file"]} for j in jars
              if any(re.match(p, j["file"].split("/")[-1], re.I) for p in sig["filename_patterns"])]
        if fn:
            findings.append(_finding(sig, "SUSPICIOUS", "low", fn, "Filename resembles this product. Filenames are trivially renamed and are weak evidence.",
                                     "Inspect JAR metadata."))
    return findings

def _merge(findings):
    best = {}
    for f in findings:
        o = best.get(f.product)
        if o is None: best[f.product] = f; continue
        a, b = (f, o) if ORDER.index(f.classification) < ORDER.index(o.classification) else (o, f)
        a.evidence = (a.evidence + b.evidence)[:20]; a.explanation += " Additional indicator: " + b.explanation
        best[f.product] = a
    return list(best.values())

DEFAULT_POLICY = {"version": "default-1", "rules": {}}

def analyze(files: dict, policy: dict = None) -> dict:
    policy = policy or DEFAULT_POLICY
    logs, jars, warnings, errors, packs, opts = [], [], [], [], [], []
    def handle(name, data, depth=0, disp=None):
        low = name.lower()
        try:
            if low.endswith(".gz"):
                handle(name[:-3], read_gzip(data), depth, disp or name)
            elif low.endswith(".jar"):
                jars.append(inspect_jar(name, data))
            elif low.endswith(".zip") and depth < 2:
                ex = read_zip(data); warnings.extend(ex.warnings)
                if "pack.mcmeta" in ex.files:
                    packs.append(analyze_pack(name, data, ex.files, DB.get("resource_packs", [])))
                else:
                    for n, d in ex.files.items(): handle(f"{name}!/{n}", d, depth + 1)
            elif low.endswith("options.txt"):
                opts.append(parse_options(data.decode("utf-8", "replace")))
            elif low.endswith((".log", ".txt")):
                logs.append(parse_log(data.decode("utf-8", "replace"), disp or name))
        except ArchiveError as e:
            errors.append({"file": name, "error": str(e)})
    for n, d in files.items(): handle(n, d)
    findings = match_signatures(logs, jars)
    enabled = next((o for o in opts if o is not None), None)
    findings += pack_findings(packs, enabled, DB.get("resource_packs", []), Finding, LIMITS)
    findings += log_pack_findings(logs, DB.get("resource_packs", []), Finding, LIMITS)
    findings = _merge(findings)
    rules = {k.lower(): v for k, v in policy.get("rules", {}).items()}
    for f in findings: f.policy = rules.get(f.product.lower(), "requires_review")
    relevant = [f for f in findings if f.policy not in ("allowed", "not_applicable")]
    known = {i for s in DB["prohibited"] for i in s["mod_ids"]}
    allow = set(DB["allowlist"])
    seen = {m: v[0] for lg in logs for m, v in lg.mods.items()}
    for j in jars:
        for m in j["mod_ids"]: seen.setdefault(m, j["versions"].get(m))
    legit = sorted(m for m in seen if m in allow)
    unknown = sorted(m for m in seen if m not in allow and m not in known and not m.startswith(("fabric-", "fabric_")))
    banned_ids = {i for sg in DB["prohibited"] for i in sg["mod_ids"]}
    idx = {}
    for lg in logs:
        for m, (ver, e) in lg.mods.items():
            d = idx.setdefault(m, {"versions": set(), "found_in": []})
            d["versions"].add(str(ver or "?")); d["found_in"].append({"source": lg.source, "line": e.line})
    for j in jars:
        for m in j["mod_ids"]:
            d = idx.setdefault(m, {"versions": set(), "found_in": []})
            d["versions"].add(str(j["versions"].get(m) or "?")); d["found_in"].append({"source": j["file"], "line": None})
    def mstatus(m): return "banned" if m in banned_ids else "allowlisted" if (m in allow or m.startswith(("fabric-", "fabric_"))) else "unknown"
    mod_table = sorted(({"mod_id": m, "versions": sorted(d["versions"]), "status": mstatus(m),
                         "found_in": sorted(d["found_in"], key=lambda x: x["source"])} for m, d in idx.items()),
                       key=lambda x: (["banned", "unknown", "allowlisted"].index(x["status"]), x["mod_id"]))
    log_table = sorted(({"source": lg.source, "minecraft": lg.minecraft, "java": lg.java, "loader": lg.loader, "loader_version": lg.loader_version,
                         "mods": len(lg.mods), "lines": lg.line_count, "notes": lg.notes} for lg in logs), key=lambda x: x["source"])
    pack_table = build_pack_table(logs, packs, DB.get("resource_packs", []))
    if relevant:
        overall = min((f.classification for f in relevant), key=ORDER.index)
    elif errors and not logs and not jars:
        overall = "ANALYSIS ERROR"
    elif not seen and not packs:
        overall = "INCONCLUSIVE"
    else:
        overall = "CLEAN IN ANALYZED DATA"
    return {"overall": overall, "db_version": DB["db_version"], "policy_version": policy.get("version"),
            "resource_packs": packs, "mod_table": mod_table, "pack_table": pack_table, "log_table": log_table, "findings": [asdict(f) for f in findings],
            "legitimate_mods": legit, "unknown_mods": unknown, "errors": errors, "warnings": warnings,
            "log_notes": [n for lg in logs for n in lg.notes],
            "note": "'CLEAN IN ANALYZED DATA' never guarantees the player is cheat-free."}
