"""Reads banned.txt: plain-text list of banned mods and resource packs. Re-read on every scan."""
import re
from pathlib import Path

def _loose(key):  # "meteor-client" / "Meteor Client" / "meteor_client" all match each other in filenames
    parts = [re.escape(x) for x in re.split(r"[\s_\-]+", key.strip()) if x]
    return "(?i).*" + "[-_ ]?".join(parts) + ".*"

def load_banned(path):
    path = Path(path)
    mods, packs, section = [], [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line: continue
        if line.startswith("["):
            section = line.strip("[]").strip().lower(); continue
        key, _, disp = (x.strip() for x in line.partition("|"))
        disp = disp or key
        if not key: continue
        if section == "mods":
            ids = sorted({key.lower(), re.sub(r"[\s_]+", "-", key.lower())})
            mods.append({"name": disp, "category": "Banned mod (banned.txt)", "risk": "high", "aliases": [disp.lower(), key.lower()],
                         "mod_ids": ids, "packages": [], "filename_patterns": [_loose(key)],
                         "false_positives": "Mod IDs can collide with unrelated mods; confirm the JAR before acting.", "verified": ""})
        elif section in ("resourcepacks", "resource_packs"):
            if key.lower().startswith("sha256:"):
                h = key.split(":", 1)[1].strip().lower()
                packs.append({"name": disp, "sha256": [h], "names": []})
            else:
                packs.append({"name": disp, "sha256": [], "names": [key]})
        else:
            raise ValueError(f"banned.txt: line outside a [mods] or [resourcepacks] section: {raw[:60]!r}")
    version = f"banned.txt ({len(mods)} mods, {len(packs)} packs)"
    rules = {m["name"]: "prohibited" for m in mods} | {p["name"]: "prohibited" for p in packs}
    return mods, packs, rules, version
