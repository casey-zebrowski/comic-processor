"""Rename files in a directory to sequential page-style names."""

from __future__ import annotations

import argparse
import re
import uuid
from pathlib import Path


def natural_sort_key(path: Path) -> list[int | str]:
    """Return a case-insensitive, numeric-aware key for a filename."""
    return [
        int(part) if part.isdecimal() else part.casefold()
        for part in re.split(r"(\d+)", path.name)
    ]


def renumber_files(directory: Path) -> int:
    """Rename direct child files of *directory* from 001 onward."""
    if not directory.is_dir():
        raise NotADirectoryError(f"not a directory: {directory}")

    files = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and not path.name.startswith(".")
        ),
        key=natural_sort_key,
    )
    targets = [
        directory / f"{number:03d}{source.suffix}"
        for number, source in enumerate(files, start=1)
    ]
    directory_conflicts = [target.name for target in targets if target.is_dir()]
    if directory_conflicts:
        raise FileExistsError(
            f"cannot replace directories: {', '.join(directory_conflicts)}"
        )

    temporary_paths = [
        directory / f".{uuid.uuid4().hex}-{number}{source.suffix}"
        for number, source in enumerate(files, start=1)
    ]
    for source, temporary_path in zip(files, temporary_paths):
        source.rename(temporary_path)
    for temporary_path, target in zip(temporary_paths, targets):
        temporary_path.rename(target)

    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename direct child files to 001, 002, and so on, preserving extensions."
    )
    parser.add_argument(
        "directory", type=Path, help="directory whose files should be renamed"
    )
    arguments = parser.parse_args()

    try:
        count = renumber_files(arguments.directory)
    except (NotADirectoryError, FileExistsError) as error:
        parser.error(str(error))

    print(f"Renamed {count} file(s) in {arguments.directory}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
