#!/usr/bin/env python3
"""Add ComicVine volume numbers to existing CBZ folder and archive names.

The script reads Series and Volume from each archive's ComicInfo.xml, searches
ComicVine once per distinct series/year, and reuses that result for the folder.
It is a dry run unless --apply is provided. Successful lookups are cached so a
large library can be processed in batches and resumed without repeating calls.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from comic_processor import fetch_volume_by_id, fetch_volumes


LOGGER = logging.getLogger("refresh_comicvine_deck_names")
CACHE_PATH = Path(__file__).with_name("comicvine_deck_refresh_cache.json")


class ComicVineLookupError(RuntimeError):
    """A ComicVine lookup failed and the batch should pause for retry."""


def xml_values(xml_data):
    root = ET.fromstring(xml_data)
    values = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].casefold()
        if tag in {"series", "volume", "number", "web", "year"}:
            values[tag] = (element.text or "").strip()
    return values


def read_comic_info(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        comic_info_name = next(
            (name for name in archive.namelist() if name.casefold() == "comicinfo.xml"),
            None,
        )
        if not comic_info_name:
            raise ValueError("ComicInfo.xml is missing")
        return xml_values(archive.read(comic_info_name))


def safe_volume_name(name):
    name = name.replace("/", " - ").replace(":", " - ")
    for character in ("!", "?", ".", "'", "&"):
        name = name.replace(character, "and" if character == "&" else "")
    name = re.sub(r"\s{2,}", " ", name).strip()
    return re.sub(r'[<>"/\\|?*]', "_", name).strip(" .")


def volume_cache_key(series, year):
    return f"{series.strip().casefold()}|{year.strip()}"


def start_year_for_folder(folder, values):
    folder_year = re.search(r"\((\d{4})\)$", folder.name)
    if folder_year:
        return folder_year.group(1)
    comic_info_year = values.get("year", "")
    if re.fullmatch(r"\d{4}", comic_info_year):
        return comic_info_year
    comic_info_volume = values.get("volume", "")
    if re.fullmatch(r"\d{4}", comic_info_volume):
        return comic_info_volume
    return ""


def load_cache(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read lookup cache {path}: {error}") from error


def save_cache(path, cache):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def lookup_volume(series, year):
    try:
        results = fetch_volumes(series, limit=100)
    except Exception as error:
        raise ComicVineLookupError(
            "ComicVine volume search failed; check connectivity, credentials, and request limits"
        ) from error
    matches = [
        result
        for result in results
        if str(result.get("name", "")).strip().casefold() == series.strip().casefold()
        and str(result.get("start_year", "")).strip() == year.strip()
    ]
    if len(matches) != 1:
        return {"status": "ambiguous", "match_count": len(matches)}

    volume = matches[0]
    if not volume.get("deck"):
        try:
            detail = fetch_volume_by_id(int(volume["id"]))
        except Exception as error:
            raise ComicVineLookupError(
                "ComicVine volume detail lookup failed; check connectivity, credentials, and request limits"
            ) from error
        if detail:
            volume = detail
    deck = str(volume.get("deck") or "")
    match = re.search(r"\bVolume\s+(\d+)\b", deck, re.IGNORECASE)
    return {
        "status": "matched",
        "name": str(volume.get("name", series)).strip(),
        "year": str(volume.get("start_year", year)).strip(),
        "deck": deck,
        "volume_number": int(match.group(1)) if match else None,
    }


def unique_path(path):
    if not os.path.lexists(path):
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not os.path.lexists(candidate):
            return candidate
        index += 1


def plan_folder(folder, archive_paths, cache, cache_path):
    values_by_archive = []
    for archive_path in archive_paths:
        values = read_comic_info(archive_path)
        series = values.get("series", "")
        year = start_year_for_folder(folder, values)
        if not series or not year:
            raise ValueError(f"Missing Series or Volume in {archive_path.name}")
        values_by_archive.append((archive_path, values, series, year))

    identities = {(series.casefold(), year) for _, _, series, year in values_by_archive}
    if len(identities) != 1:
        raise ValueError("Archives in this folder do not share the same series and year")

    _, _, series, year = values_by_archive[0]
    key = volume_cache_key(series, year)
    if key not in cache:
        cache[key] = lookup_volume(series, year)
        save_cache(cache_path, cache)
        time.sleep(18)
    volume = cache[key]
    volume_number = volume.get("volume_number")
    if volume.get("status") != "matched" or not volume_number:
        return None, volume

    clean_name = safe_volume_name(volume.get("name") or series)
    destination_name = f"{clean_name} (v{volume_number})({volume.get('year') or year})"
    destination = unique_path(folder.parent / destination_name) if folder.name != destination_name else folder
    renames = []
    for archive_path, values, _, _ in values_by_archive:
        old_stem = archive_path.stem
        if old_stem.startswith(folder.name):
            tail = old_stem[len(folder.name):]
        else:
            issue = old_stem.rsplit(" - ", 1)[-1]
            tail = f" - {issue}"
        desired = destination / f"{destination.name}{tail}{archive_path.suffix}"
        if archive_path.parent == destination and archive_path.name == desired.name:
            continue
        desired = unique_path(desired) if os.path.lexists(desired) else desired
        renames.append((archive_path, desired))
    return {"source_folder": folder, "destination_folder": destination, "renames": renames}, volume


def apply_folder_plan(plan):
    source = plan["source_folder"]
    destination = plan["destination_folder"]
    if source != destination:
        if os.path.lexists(destination):
            raise FileExistsError(f"Destination appeared while processing: {destination}")
        source.rename(destination)
    for old_path, planned_path in plan["renames"]:
        new_path = destination / planned_path.name
        if old_path.parent == source and source != destination:
            old_path = destination / old_path.name
        if old_path == new_path:
            continue
        if os.path.lexists(new_path):
            new_path = unique_path(new_path)
        old_path.rename(new_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/Volumes/comics"))
    parser.add_argument("--apply", action="store_true", help="perform the planned renames")
    parser.add_argument("--max-lookups", type=int, default=450)
    parser.add_argument("--cache", type=Path, default=CACHE_PATH)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Root folder does not exist or is not a directory: {root}")
    if args.max_lookups < 1:
        parser.error("--max-lookups must be at least 1")

    cache = load_cache(args.cache)
    completed_lookups = 0
    renamed_folders = 0
    renamed_archives = 0
    skipped = 0
    errors = 0
    for folder in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda p: p.name.casefold()):
        archives = sorted(
            (path for path in folder.iterdir() if path.is_file() and path.suffix.casefold() == ".cbz"),
            key=lambda p: p.name.casefold(),
        )
        if not archives:
            continue
        try:
            first_values = read_comic_info(archives[0])
            key = volume_cache_key(
                first_values.get("series", ""), start_year_for_folder(folder, first_values)
            )
            if key not in cache:
                if completed_lookups >= args.max_lookups:
                    LOGGER.info("Reached --max-lookups=%d; rerun later to continue.", args.max_lookups)
                    break
                completed_lookups += 1
            plan, volume = plan_folder(folder, archives, cache, args.cache)
            if not plan:
                skipped += 1
                if volume.get("status") != "matched":
                    LOGGER.warning("Skipped %s: ComicVine match count %s", folder.name, volume.get("match_count"))
                continue
            if not plan["renames"] and plan["source_folder"] == plan["destination_folder"]:
                skipped += 1
                continue
            LOGGER.info("%s -> %s (%d CBZ)", folder.name, plan["destination_folder"].name, len(plan["renames"]))
            if args.apply:
                apply_folder_plan(plan)
                renamed_folders += int(plan["source_folder"] != plan["destination_folder"])
                renamed_archives += len(plan["renames"])
        except ComicVineLookupError as error:
            errors += 1
            LOGGER.error("ComicVine lookup paused at %s: %s", folder.name, error)
            break
        except Exception as error:
            errors += 1
            LOGGER.error("Could not process %s: %s", folder.name, error)

    LOGGER.info(
        "%s: %d new lookups, %d folders renamed, %d archives renamed, %d skipped, %d errors. Cache: %s",
        "Applied" if args.apply else "Dry run",
        completed_lookups,
        renamed_folders,
        renamed_archives,
        skipped,
        errors,
        args.cache,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
