import re

html = open("frontend/index.html", "r", encoding="utf-8").read()
dom_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_\-]+)["\']', html))

script_start = html.find("<script>")
script = html[script_start:]

# Find all $('#...') usages
used_ids = re.findall(r'\$\([\'\"]#([a-zA-Z0-9_\-]+)[\'\"]\)', script)
missing_ids = [uid for uid in set(used_ids) if uid not in dom_ids]

print("DOM IDs count:", len(dom_ids))
print("Used IDs count:", len(set(used_ids)))
print("MISSING IDs referenced in JS:", missing_ids)

for line in script.splitlines():
    for mid in missing_ids:
        if f"'#{mid}'" in line or f'"#{mid}"' in line:
            print(f"CRASH RISK on #{mid}: {line.strip()}")
