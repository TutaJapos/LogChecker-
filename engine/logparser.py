import re
from dataclasses import dataclass, field

LINE = re.compile(r"^\[(?P<ts>\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*\[(?P<thread>[^/\]]+)/(?P<level>[A-Z]+)\](?:\s*\[(?P<logger>[^\]]*)\])?:?\s*(?P<msg>.*)$")
MC = re.compile(r"(?:Minecraft Version:|Loading Minecraft)\s*(\d+\.\d+(?:\.\d+)?)", re.I)
JAVA = re.compile(r"Java(?: Version:| is| runtime version)?\s*(\d+(?:\.\d+)*[\w.+-]*)", re.I)
LOADER = re.compile(r"(Fabric Loader|Quilt Loader|NeoForge|Forge)[\s:/]+v?(\d[\w.+-]*)", re.I)
MODCOUNT = re.compile(r"Loading \d+ mods?:")
MODITEM = re.compile(r"^\s*-\s+([a-z0-9_.\-]+)\s+(\S+)")
FAIL = re.compile(r"(failed to (?:load|initiali[sz]e)|exception|could not (?:load|initiali[sz]e))", re.I)
RELOAD = re.compile(r"Reloading ResourceManager:\s*(.*)$")
PACK = re.compile(r"(?:resource ?pack|Reloading ResourceManager)", re.I)

@dataclass
class Ev:
    source: str; line: int; text: str; timestamp: str = None

@dataclass
class ParsedLog:
    source: str
    minecraft: str = None
    java: str = None
    loader: str = None
    loader_version: str = None
    mods: dict = field(default_factory=dict)       # id -> (version, Ev) listed by loader
    loggers: dict = field(default_factory=dict)    # logger name -> first Ev (referenced)
    failures: list = field(default_factory=list)
    pack_events: list = field(default_factory=list)
    reloads: list = field(default_factory=list)   # packs the game itself lists as enabled at each resource reload
    line_count: int = 0
    complete: bool = False
    notes: list = field(default_factory=list)

def parse_log(text: str, source: str) -> ParsedLog:
    p, in_mods, last_ts = ParsedLog(source), False, None
    lines = text.splitlines()
    p.line_count = len(lines)
    for n, raw in enumerate(lines, 1):
        m = LINE.match(raw)
        if m:
            last_ts, msg = m["ts"], m["msg"]
            if m["logger"] and m["logger"] not in p.loggers:
                p.loggers[m["logger"]] = Ev(source, n, raw[:300], m["ts"])
            in_mods = bool(MODCOUNT.search(msg))
        else:
            msg = raw
            mi = MODITEM.match(raw) if in_mods else None
            if mi and mi[1] not in p.mods:
                p.mods[mi[1]] = (mi[2], Ev(source, n, raw.strip()[:300], last_ts))
                continue
            if not raw.startswith((" ", "\t")):
                in_mods = False
        if not p.minecraft and (x := MC.search(msg)): p.minecraft = x[1]
        if not p.java and "java" in msg.lower() and (x := JAVA.search(msg)): p.java = x[1]
        if not p.loader and (x := LOADER.search(msg)): p.loader, p.loader_version = x[1], x[2]
        if FAIL.search(msg) and m: p.failures.append(Ev(source, n, raw[:300], last_ts))
        if (x := RELOAD.search(msg)):
            p.reloads.append({"packs": [t.strip() for t in x[1].split(",") if t.strip()], "ev": Ev(source, n, raw[:300], last_ts)})
        if PACK.search(msg): p.pack_events.append(Ev(source, n, raw[:300], last_ts))
    p.complete = bool(p.mods) or "Stopping!" in text or "Stopping server" in text
    if not p.mods: p.notes.append("No loader mod list found; mod inventory may be incomplete.")
    if not p.minecraft: p.notes.append("Minecraft version not found.")
    return p
