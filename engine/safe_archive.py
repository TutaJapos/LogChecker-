"""Safe reading of untrusted ZIP/GZ data. Nothing is executed or written to disk."""
import gzip, io, zipfile, posixpath
from dataclasses import dataclass, field

MAX_ENTRIES = 5000
MAX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 300 * 1024 * 1024
MAX_RATIO = 200

class ArchiveError(Exception):
    pass

@dataclass
class Extracted:
    files: dict = field(default_factory=dict)      # safe name -> bytes
    warnings: list = field(default_factory=list)

def safe_name(name: str):
    n = name.replace("\\", "/")
    if n.startswith("/") or (len(n) > 1 and n[1] == ":") or "\x00" in n:
        return None
    norm = posixpath.normpath(n)
    if norm.startswith("..") or norm == ".":
        return None
    return norm

def read_zip(data: bytes) -> Extracted:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ArchiveError("Malformed ZIP archive") from e
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ArchiveError("Too many archive entries")
    out, total = Extracted(), 0
    for i in infos:
        if i.is_dir():
            continue
        name = safe_name(i.filename)
        if name is None:
            out.warnings.append(f"Skipped unsafe entry path: {i.filename!r}")
            continue
        if i.file_size > MAX_ENTRY_BYTES:
            out.warnings.append(f"Skipped oversized entry: {name}")
            continue
        if i.compress_size and i.file_size / i.compress_size > MAX_RATIO:
            raise ArchiveError("Suspicious compression ratio (possible archive bomb)")
        total += i.file_size
        if total > MAX_TOTAL_BYTES:
            raise ArchiveError("Archive exceeds total size limit")
        try:
            with zf.open(i) as fh:
                buf = fh.read(MAX_ENTRY_BYTES + 1)
        except Exception:
            out.warnings.append(f"Could not read entry: {name}")
            continue
        if len(buf) > MAX_ENTRY_BYTES:
            raise ArchiveError("Entry exceeded declared size (possible archive bomb)")
        out.files[name] = buf
    return out

def read_gzip(data: bytes) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
            buf = g.read(MAX_ENTRY_BYTES + 1)
    except (OSError, EOFError) as e:
        raise ArchiveError("Malformed GZ file") from e
    if len(buf) > MAX_ENTRY_BYTES:
        raise ArchiveError("Decompressed GZ exceeds size limit")
    return buf
