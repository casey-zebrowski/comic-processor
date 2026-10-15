#!/usr/bin/env python3
from pathlib import Path
import re


folder = Path.cwd().name
files = [
    path
    for path in Path(".").iterdir()
    if path.is_file()
    and path.suffix.lower() == ".cbz"
    and re.search(r"\(\s*\d+\)", path.name)
]
mappings = []

for source in files:
    match = re.search(r"\(\s*(\d+)\)", source.name)
    target = source.with_name(f"{folder} {match.group(1)}{source.suffix}")
    mappings.append((source, target))

targets = [target for _, target in mappings]
if len(set(targets)) != len(targets):
    raise SystemExit("Aborting: multiple files map to the same target")

conflicts = [
    target.name
    for source, target in mappings
    if target.exists() and target != source
]
if conflicts:
    raise SystemExit(f"Aborting: target files already exist: {conflicts}")

for source, target in mappings:
    source.rename(target)

print(f"Renamed {len(mappings)} files.")
