from pathlib import Path

root = Path("backend")
bad_files = []

for path in root.rglob("*.py"):
    data = path.read_bytes()
    if b"\x00" in data:
        bad_files.append(path)

if not bad_files:
    print("No null bytes found in backend/*.py")
else:
    print("Files containing null bytes:")
    for p in bad_files:
        print(" -", p)
