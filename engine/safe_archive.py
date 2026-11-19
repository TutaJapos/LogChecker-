"""Safe reading of untrusted ZIP/RAR/GZ data. Nothing is executed. (RAR needs a brief temp file, deleted right after reading.)"""
import gzip, io, os, tempfile, zipfile, posixpath
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

def _is_dir(i):
    f = getattr(i, "is_dir", None) or getattr(i, "isdir", None)
    return bool(f()) if callable(f) else str(i.filename).endswith(("/", "\\"))

def _collect(infos, open_entry, check_ratio=True) -> Extracted:
    """Shared size/path checks for every archive format. open_entry(info) -> file-like."""
    if len(infos) > MAX_ENTRIES:
        raise ArchiveError("Too many archive entries")
    out, total = Extracted(), 0
    for i in infos:
        if _is_dir(i):
            continue
        name = safe_name(i.filename)
        if name is None:
            out.warnings.append(f"Skipped unsafe entry path: {i.filename!r}")
            continue
        if i.file_size > MAX_ENTRY_BYTES:
            out.warnings.append(f"Skipped oversized entry: {name}")
            continue
        if check_ratio and i.compress_size and i.file_size / i.compress_size > MAX_RATIO:
            raise ArchiveError("Suspicious compression ratio (possible archive bomb)")
        total += i.file_size
        if total > MAX_TOTAL_BYTES:
            raise ArchiveError("Archive exceeds total size limit")
        try:
            with open_entry(i) as fh:
                buf = fh.read(MAX_ENTRY_BYTES + 1)
        except Exception:
            out.warnings.append(f"Could not read entry: {name}")
            continue
        if len(buf) > MAX_ENTRY_BYTES:
            raise ArchiveError("Entry exceeded declared size (possible archive bomb)")
        out.files[name] = buf
    return out

def read_zip(data: bytes) -> Extracted:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ArchiveError("Malformed ZIP archive") from e
    return _collect(zf.infolist(), zf.open)

RAR_MAGIC = (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")   # RAR 4.x and RAR 5.x signatures

def is_rar(data: bytes) -> bool:
    return data[:8].startswith(RAR_MAGIC)

def _open_rar_backend(path):
    """unrar-cffi if installed (bundles libunrar); otherwise rarfile, which needs UnRAR.exe / unrar / unar / bsdtar.
    Set MCLA_UNRAR to the full path of the extractor if it is not on PATH."""
    try:
        from unrar.cffi import rarfile as rf
        return rf.RarFile(path)
    except ImportError:
        pass
    try:
        import rarfile as rf
    except ImportError:
        raise ArchiveError("RAR support is not installed on this server (pip install rarfile, and put UnRAR.exe/unrar in PATH)")
    if os.environ.get("MCLA_UNRAR"):
        rf.UNRAR_TOOL = os.environ["MCLA_UNRAR"]
    try:
        rf.tool_setup()
    except rf.RarCannotExec:
        raise ArchiveError("rarfile is installed but no RAR extractor was found: install UnRAR.exe (comes with WinRAR) / unrar / unar / bsdtar in PATH, or set MCLA_UNRAR to its full path")
    return rf.RarFile(path)

def read_rar(data: bytes) -> Extracted:
    """Read a .rar in memory-limited fashion. RAR backends need a real path, so the bytes go through a short-lived temp file."""
    if not is_rar(data):
        raise ArchiveError("Malformed RAR archive")
    fd, path = tempfile.mkstemp(suffix=".rar")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            rf = _open_rar_backend(path)
            try:
                if getattr(rf, "needs_password", lambda: False)():
                    raise ArchiveError("RAR archive is password-protected")
                # solid archives report unreliable packed sizes, so skip the ratio check; size caps still apply
                return _collect(rf.infolist(), rf.open, check_ratio=False)
            finally:
                getattr(rf, "close", lambda: None)()
        except ArchiveError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "encrypted" in msg:
                raise ArchiveError("RAR archive is password-protected") from e
            raise ArchiveError("Malformed or unsupported RAR archive") from e
    finally:
        try: os.remove(path)
        except OSError: pass

def read_gzip(data: bytes) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
            buf = g.read(MAX_ENTRY_BYTES + 1)
    except (OSError, EOFError) as e:
        raise ArchiveError("Malformed GZ file") from e
    if len(buf) > MAX_ENTRY_BYTES:
        raise ArchiveError("Decompressed GZ exceeds size limit")
    return buf
