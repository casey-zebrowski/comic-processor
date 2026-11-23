#!/usr/bin/env python3
"""Safely replace identically named files in a CBZ (ZIP) archive."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def replace(archive: Path, pages: list[Path]) -> list[str]:
    if archive.suffix.lower() != ".cbz":
        raise ValueError("The archive must have a .cbz extension.")
    if not archive.is_file():
        raise ValueError(f"Archive not found: {archive}")
    if not pages:
        raise ValueError("Choose at least one replacement file.")
    if any(not page.is_file() for page in pages):
        raise ValueError("Every replacement must be a regular file.")

    with zipfile.ZipFile(archive, "r") as source:
        infos = source.infolist()
        by_basename: dict[str, list[zipfile.ZipInfo]] = {}
        for info in infos:
            if not info.is_dir():
                by_basename.setdefault(Path(info.filename).name, []).append(info)

        chosen: dict[str, Path] = {}
        for page in pages:
            matches = by_basename.get(page.name, [])
            if not matches:
                raise ValueError(f"{page.name} is not present in the archive; nothing was changed.")
            if len(matches) != 1:
                raise ValueError(f"{page.name} appears more than once in the archive; nothing was changed.")
            entry = matches[0].filename
            if entry in chosen:
                raise ValueError(f"More than one replacement was supplied for {page.name}.")
            chosen[entry] = page

        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{archive.stem}-", suffix=".cbz", dir=archive.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w") as rebuilt:
                rebuilt.comment = source.comment
                for info in infos:
                    if info.is_dir():
                        rebuilt.writestr(info, b"")
                    elif info.filename in chosen:
                        rebuilt.write(chosen[info.filename], arcname=info.filename, compress_type=zipfile.ZIP_DEFLATED)
                    else:
                        rebuilt.writestr(info, source.read(info))
            with zipfile.ZipFile(temporary, "r") as check:
                bad_file = check.testzip()
                if bad_file:
                    raise ValueError(f"Rebuilt archive failed validation at {bad_file}.")
            shutil.copystat(archive, temporary)
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    return [page.name for page in pages]


if __name__ == "__main__":
    try:
        archive_argument = Path(sys.argv[1])
        replacements = [Path(argument) for argument in sys.argv[2:]]
        print("Replaced: " + ", ".join(replace(archive_argument, replacements)))
    except (IndexError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
