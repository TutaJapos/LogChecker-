"""Reads mod metadata from JARs as plain data. JARs are never executed or loaded."""
import io, json, re, zipfile, tomllib
from .safe_archive import read_zip, ArchiveError

def inspect_jar(name: str, data: bytes) -> dict:
    info = {"file": name, "mod_ids": [], "versions": {}, "packages": [], "meta_files": [], "error": None}
    try:
        ex = read_zip(data)
    except ArchiveError as e:
        info["error"] = str(e); return info
    f = ex.files
    try:
        for key in ("fabric.mod.json", "quilt.mod.json"):
            if key in f:
                j = json.loads(f[key].decode("utf-8", "replace"))
                mid = j.get("id") or j.get("quilt_loader", {}).get("id")
                ver = j.get("version") or j.get("quilt_loader", {}).get("version")
                if mid: info["mod_ids"].append(mid); info["versions"][mid] = ver; info["meta_files"].append(key)
        for key in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml"):
            if key in f:
                t = tomllib.loads(f[key].decode("utf-8", "replace"))
                for m in t.get("mods", []):
                    if m.get("modId"): info["mod_ids"].append(m["modId"]); info["versions"][m["modId"]] = m.get("version"); info["meta_files"].append(key)
    except Exception as e:
        info["error"] = f"Metadata parse error: {type(e).__name__}"
    pk = set()
    for n in f:
        if n.endswith(".class"):
            parts = n.split("/")[:-1]
            if len(parts) >= 2: pk.add(".".join(parts[:3]))
    info["packages"] = sorted(pk)[:200]
    return info
