import re
import os

source_path = r"C:\Users\ISSAH\.gemini\antigravity\brain\446f9075-1740-4d8e-b526-91c4417a0c79\.system_generated\steps\336\content.md"
dest_dir = r"c:\Users\ISSAH\Desktop\Projects\DIT\fyp2026_backend\apps\listings\data"
dest_file = os.path.join(dest_dir, "tz_areas.py")

os.makedirs(dest_dir, exist_ok=True)

with open(source_path, "r", encoding="utf-8") as f:
    content = f.read()

# Regex to capture the structure: (id, 'name', parent_id/NULL, 'level'
pattern = re.compile(r"\(\s*(\d+)\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*(NULL|\d+)\s*,\s*'([^']+)'")

records = []
for match in pattern.finditer(content):
    id_val = int(match.group(1))
    name_val = match.group(2).replace("\\'", "'")  # decode escaped quotes if any
    parent_val = match.group(3)
    parent_id = None if parent_val == "NULL" else int(parent_val)
    level_val = match.group(4)
    records.append({
        "id": id_val,
        "name": name_val,
        "parent_id": parent_id,
        "level": level_val
    })

with open(dest_file, "w", encoding="utf-8") as f:
    f.write("# Tanzania Administrative Areas Data (Region, District, Ward)\n")
    f.write("# Parsed offline from SQL dump\n\n")
    f.write("TZ_AREAS = [\n")
    for r in records:
        f.write(f"    {r},\n")
    f.write("]\n")

print(f"Successfully wrote {len(records)} records to {dest_file}")
