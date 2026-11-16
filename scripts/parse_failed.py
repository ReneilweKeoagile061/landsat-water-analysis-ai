# parse_failed.py
import os, re
BASE = "https://wis.orasecom.org/data_store/other/stas/"
log_path = os.path.abspath(os.path.join("..", "..", ".system_generated", "steps", "504", "output.txt"))
# Adjust path relative to script location
script_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.normpath(os.path.join(script_dir, "..", "..", ".system_generated", "steps", "504", "output.txt"))
if not os.path.exists(log_path):
    print(f"Log file not found: {log_path}")
    raise SystemExit(1)

subfolder = None
fails = []
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        m = re.match(r"-\\> (.+)/", line)
        if m:
            subfolder = m.group(1)
            continue
        if line.startswith("FAIL:"):
            parts = line.split(" ")
            filename = parts[1]
            rel_url = f"Hydrogeology%20Database/3%20-%20Shapefiles/WSG84/{subfolder.split('/')[-1]}/" + filename.replace(" ", "%20")
            remote = BASE + rel_url
            local = os.path.join("data", "external", "orasecom_stas", subfolder, filename)
            fails.append((remote, local, line))

print(f"Failed files: {len(fails)}")
for remote, local, _ in fails:
    print(f"{remote} -> {local}")
