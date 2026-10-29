# Minecraft Log Analyzer (simple)
No database, no accounts. The banned list is the plain-text file `banned.txt`.

## Run
    python app.py            # needs Python 3.10+; open http://127.0.0.1:8000
    pip install pillow       # optional: enables the X-ray texture check for resource packs
Edit `banned.txt` any time; changes apply on the next scan. Test: `python -m unittest discover -s tests`

## Reading logs.zip
Upload a `logs.zip` containing `.log` / `.log.gz` files (or the files directly). The result page lists every mod with the log files it appears in
(searchable, sortable, filter by Banned / Unknown / Allowlisted) and can export that table as CSV.

## Resource packs
The analyzer reads the game's own `Reloading ResourceManager: ...` log line (the packs enabled at that moment) and matches pack names against `banned.txt`,
in plain logs and inside logs.zip / .log.gz. Uploaded pack .zip files are also checked (hash, name, X-ray textures). The Resource packs tab lists every pack and the files it appears in.
Name matches are not proof of contents: a pack is only CONFIRMED by a SHA-256 you list.

## How results are decided
- Banned mod ID found in the loaded-mod list or JAR metadata -> CONFIRMED MATCH
- Only a similar JAR/pack filename -> SUSPICIOUS (filenames can be renamed)
- Pack SHA-256 listed in banned.txt -> CONFIRMED MATCH; pack hiding stone/dirt but showing ores -> HIGH RISK
- Names in chat/errors are not evidence. "CLEAN IN ANALYZED DATA" never guarantees a player is cheat-free.
Files are analyzed in memory, never executed or stored. The server listens on 127.0.0.1 only and has no login: do not expose it to the internet.
