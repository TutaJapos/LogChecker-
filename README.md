# Minecraft Log Analyzer (simple)
The blacklist is the plain-text file `banned.txt`. Edit it by hand; there is no database, login or admin page.

## Run locally
    python mcla_app.py                      # Python 3.10+, open http://127.0.0.1:8000
    pip install pillow                      # optional: X-ray texture check for uploaded packs
    pip install rarfile                     # needed for .rar uploads, plus UnRAR.exe (Windows, ships with WinRAR) or unrar/unar/bsdtar in PATH
Tests: `python -m unittest discover -s tests`. `banned.txt` is re-read on every scan.

## Update the blacklist (on Vercel)
On GitHub open `banned.txt`, click the pencil icon, add or remove lines, then **Commit changes**. Vercel redeploys automatically in about a minute.
Format: `key | Display Name` under `[mods]` (mod ID) or `[resourcepacks]` (text in the pack's .zip name, or `sha256:<hash>` for an exact match).

## Deploy to Vercel
1. Put the folder's contents at the top level of a GitHub repo (`vercel.json`, `public/`, `api/`, `engine/`, `mcla_app.py`, `requirements.txt`, `banned.txt`).
2. In Vercel: **Add New > Project**, import the repo, leave Framework = Other and Output Directory empty, then **Deploy**.
3. Open the site; `/health` should print `ok`. No environment variables are needed.
Limits: uploads are limited to about 4.5 MB per scan (the app enforces 4 MB); function time limit 60 s. Scanning is public to anyone with the URL.
Keep the repo private if you do not want the banned list to be readable.

## Reading results
- Banned mod ID in a log's mod list or JAR metadata -> CONFIRMED MATCH; similar filename only -> SUSPICIOUS.
- Pack name in the game's `Reloading ResourceManager:` line -> HIGH RISK (enabled; identity by name only); sha256 listed -> CONFIRMED.
- "CLEAN IN ANALYZED DATA" never guarantees a player is cheat-free. Files are analyzed in memory, never run or stored (a `.rar` is the one exception: it is written to a temp file for a moment because the RAR library needs a path, then deleted).

## RAR support
`.rar` (RAR4 and RAR5) works like `.zip`: log/jar/resource-pack files inside are scanned, and `.rar` is also detected by its file signature if the extension is wrong. Password-protected or multi-volume archives are reported as an error.
Setup: `pip install rarfile`, and an extractor must be available: `UnRAR.exe` on Windows (installed with WinRAR, folder usually `C:\\Program Files\\WinRAR`), or `unrar`/`unar`/`bsdtar` on Linux/macOS. If it is not on PATH, set `MCLA_UNRAR` to its full path.
`unrar-cffi` is also supported (tried first if installed), but it has no Windows wheels and needs a C compiler there.
On Vercel there is no extractor binary, so .rar relies on `unrar-cffi` (listed in `requirements.txt` for Linux only). Untested on Vercel: check the build log after deploying. If that build fails, delete the `unrar-cffi` line; everything else keeps working and .rar shows a clear error.
