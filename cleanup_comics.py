#!/usr/bin/env python3
"""Merge w2/w3 into working and remove leading numeric filename labels."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
from pathlib import Path


PREFIX = re.compile(
    r"^(?P<number>\d{1,3}(?:\.\d+)+|\d+)"
    r"(?:(?:\.\s+)|(?:\s*-\s+)|(?:\s+))"
)
IMMUTABLE_FLAG = getattr(stat, "UF_IMMUTABLE", 0)


def clear_immutable(path: Path) -> None:
    if not IMMUTABLE_FLAG:
        return
    flags = os.stat(path, follow_symlinks=False).st_flags
    if flags & IMMUTABLE_FLAG:
        os.chflags(path, flags & ~IMMUTABLE_FLAG, follow_symlinks=False)


def merge_sources(base: Path, apply: bool) -> tuple[int, int, int]:
    working = base / "working"
    moved = replaced = kept = 0

    for source_name in ("w2", "w3"):
        source_root = base / source_name
        if not source_root.is_dir():
            print(f"{source_name}: not present; skipping")
            continue

        for source in sorted(source_root.rglob("*")):
            if source.is_symlink() or not source.is_file():
                continue

            destination = working / source.relative_to(source_root)
            if destination.exists() and not destination.is_file():
                raise RuntimeError(f"File/directory conflict: {source} -> {destination}")

            if not destination.exists():
                action = "move"
                moved += 1
            elif source.stat().st_size > destination.stat().st_size:
                action = "replace"
                replaced += 1
            else:
                action = "discard duplicate"
                kept += 1

            if not apply:
                print(f"  {action}: {source} -> {destination}")
                continue

            if action == "move":
                destination.parent.mkdir(parents=True, exist_ok=True)
                clear_immutable(source)
                shutil.move(str(source), str(destination))
            elif action == "replace":
                destination.parent.mkdir(parents=True, exist_ok=True)
                clear_immutable(source)
                clear_immutable(destination)
                os.replace(source, destination)
            else:
                clear_immutable(source)
                source.unlink()

        if apply:
            for directory in sorted(
                (p for p in source_root.rglob("*") if p.is_dir()),
                key=lambda p: len(p.parts),
                reverse=True,
            ):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                source_root.rmdir()
            except OSError:
                pass

    return moved, replaced, kept


def rename_plan(working: Path) -> list[tuple[Path, Path]]:
    paths = list(working.rglob("*"))
    plans: dict[Path, Path] = {}
    projected: dict[Path, list[Path]] = {}

    for path in paths:
        relative = path.relative_to(working)
        new_parts = []
        for part in relative.parts:
            match = PREFIX.match(part)
            new_parts.append(part[match.end() :] if match else part)
        destination = working.joinpath(*new_parts)
        plans[path] = destination
        projected.setdefault(destination, []).append(path)

    for destination, sources in list(projected.items()):
        if len(sources) < 2:
            continue
        if not all(source.is_file() and PREFIX.match(source.name) for source in sources):
            raise RuntimeError(
                f"Cannot safely resolve rename collision at {destination}: "
                + ", ".join(str(source) for source in sources)
            )

        projected.pop(destination)
        for source in sources:
            match = PREFIX.match(source.name)
            assert match is not None
            number = match.group("number")
            base_destination = plans[source]
            candidate = base_destination.with_name(
                f"{base_destination.stem} (issue-{number}){base_destination.suffix}"
            )
            suffix = 2
            while candidate in projected or candidate.exists():
                candidate = base_destination.with_name(
                    f"{base_destination.stem} (issue-{number}-{suffix})"
                    f"{base_destination.suffix}"
                )
                suffix += 1
            plans[source] = candidate
            projected[candidate] = [source]

    for destination, sources in projected.items():
        if destination.exists() and destination not in sources:
            raise RuntimeError(f"Rename destination already exists: {destination}")

    return [(source, destination) for source, destination in plans.items() if source != destination]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform changes; without this option, only show the plan",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="directory containing w2, w3, and working (default: script directory)",
    )
    args = parser.parse_args()
    base = args.base_dir.expanduser().resolve()
    working = base / "working"

    if not working.is_dir():
        raise SystemExit(f"Working directory not found: {working}")

    if args.apply:
        print("Applying cleanup.")
    else:
        print("Dry run only. Re-run with --apply to make changes.")

    moved, replaced, kept = merge_sources(base, args.apply)
    renames = rename_plan(working)
    for source, destination in renames:
        print(f"  rename: {source} -> {destination}")
        if args.apply:
            source.rename(destination)

    print(
        f"Merge: {moved} moved, {replaced} replaced by larger sources, "
        f"{kept} existing copies kept."
    )
    print(f"Filename/folder prefixes to remove: {len(renames)}")
    if not args.apply:
        print("Source files moved during apply will also be checked for numeric prefixes.")


if __name__ == "__main__":
    main()
