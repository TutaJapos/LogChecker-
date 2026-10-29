# Minecraft Log Analyzer (simple)
The blacklist is the plain-text file `banned.txt`. Edit it by hand; there is no database, login or admin page.

## Run locally
    python mcla_app.py                      # Python 3.10+, open http://127.0.0.1:8000
    pip install pillow                      # optional: X-ray texture check for uploaded packs
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
- "CLEAN IN ANALYZED DATA" never guarantees a player is cheat-free. Files are analyzed in memory, never run or stored.
