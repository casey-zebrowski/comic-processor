import fnmatch
import html
import json
import logging
import os
import re
import shutil
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import cv2
import numpy as np
import zxingcpp
from PIL import Image, ImageDraw, UnidentifiedImageError

from comic_processor import (
    extract_archive,
    fetch_comic_by_id,
    fetch_issues_by_volume_and_number,
    fetch_volume_by_id,
    fetch_volumes,
    capture_comicvine_calls,
)

logger = logging.getLogger(__name__)

JUNK_FILES_PATH = Path(__file__).with_name("junk_files.txt")

TRASH_DIR_NAME = "step0_trash"
JUNK_FILES_DIR_NAME = "step0.1_junk_files"
CONVERT_DIR_NAME = "step1_convert"
CONVERT_FAILED_DIR_NAME = "step1.1_convert_failed"
PROCESS_DIR_NAME = "step2_process"
PROCESS_REMOVE_BORDER_DIR_NAME = "step2.1_process_remove_border"
PROCESS_REMOVE_BARCODE_DIR_NAME = "step2.2_process_remove_barcode"
MANUAL_CLEANUP_DIR_NAME = "step2.3_process_manual_cleanup"
PROCESS_COVERS_DIR_NAME = "step2.4_process_covers"
COMPLETED_DIR_NAME = "step3_completed"
DONE_DIR_NAME = "step4_done"


def create_required_folders(base_dir):
    folders = [
        TRASH_DIR_NAME,
        JUNK_FILES_DIR_NAME,
        CONVERT_DIR_NAME,
        CONVERT_FAILED_DIR_NAME,
        PROCESS_DIR_NAME,
        PROCESS_REMOVE_BORDER_DIR_NAME,
        PROCESS_REMOVE_BARCODE_DIR_NAME,
        MANUAL_CLEANUP_DIR_NAME,
        PROCESS_COVERS_DIR_NAME,
        COMPLETED_DIR_NAME,
        DONE_DIR_NAME,
    ]

    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.info(f"Created folder: {folder_path}")


def get_unique_destination_folder(parent_dir, folder_name):
    """Return a folder path that won't overwrite an existing destination."""
    destination = os.path.join(parent_dir, folder_name)
    duplicate_number = 1
    while os.path.lexists(destination):
        destination = os.path.join(parent_dir, f"{folder_name} ({duplicate_number})")
        duplicate_number += 1
    return destination


def extract_issue_number(filename):
    """Extract a comic issue token, removing leading zeroes from its number."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    match = re.search(r"(?<![\w])(\d+[A-Za-z]*)\s+\((?:18|19|20)\d{2}\)", stem)
    if not match:
        title = re.split(r"\s+\(", stem, maxsplit=1)[0]
        issue_tokens = re.findall(r"(?<![\w])\d+[A-Za-z]*", title)
        if not issue_tokens:
            raise ValueError(f"Could not find an issue number in filename: {filename}")
        issue_token = issue_tokens[-1]
    else:
        issue_token = match.group(1)

    number_and_suffix = re.fullmatch(r"0*(\d+)([A-Za-z]*)", issue_token)
    if number_and_suffix:
        return f"{int(number_and_suffix.group(1))}{number_and_suffix.group(2)}"
    return issue_token


def read_junk_patterns():
    if not JUNK_FILES_PATH.exists():
        return []
    return [
        line.strip().casefold()
        for line in JUNK_FILES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_junk_file():
    if not JUNK_FILES_PATH.exists():
        return
    patterns = [
        line.strip().lower()
        for line in JUNK_FILES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    JUNK_FILES_PATH.write_text(
        "".join(f"{pattern}\n" for pattern in sorted(patterns)), encoding="utf-8"
    )


def move_junk_files(folder_path, junk_root):
    patterns = read_junk_patterns()
    if not patterns:
        return

    junk_destination = os.path.join(junk_root, os.path.basename(folder_path))
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and any(
            fnmatch.fnmatchcase(file_name.casefold(), pattern) for pattern in patterns
        ):
            os.makedirs(junk_destination, exist_ok=True)
            destination_path = os.path.join(junk_destination, file_name)
            if os.path.lexists(destination_path):
                name, extension = os.path.splitext(file_name)
                duplicate_number = 1
                while os.path.lexists(destination_path):
                    destination_path = os.path.join(
                        junk_destination, f"{name} ({duplicate_number}){extension}"
                    )
                    duplicate_number += 1
            shutil.move(file_path, destination_path)
            logger.debug(f"Moved junk file: {file_path} -> {destination_path}")


def unique_file_path(directory, file_name):
    destination = os.path.join(directory, file_name)
    if not os.path.lexists(destination):
        return destination

    stem, extension = os.path.splitext(file_name)
    duplicate_number = 1
    while True:
        destination = os.path.join(directory, f"{stem} ({duplicate_number}){extension}")
        if not os.path.lexists(destination):
            return destination
        duplicate_number += 1


def convert_images_to_jpg(folder_path, convert_failed_dir):
    """Convert readable image files to JPEG and quarantine non-images."""
    os.makedirs(convert_failed_dir, exist_ok=True)
    for file_name in sorted(os.listdir(folder_path)):
        source_path = os.path.join(folder_path, file_name)
        if not os.path.isfile(source_path):
            continue

        target_name = f"{os.path.splitext(file_name)[0]}.jpg"
        target_path = os.path.join(folder_path, target_name)
        try:
            with Image.open(source_path) as image:
                image.load()
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba_image = image.convert("RGBA")
                    rgb_image = Image.new("RGB", rgba_image.size, "white")
                    rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
                else:
                    rgb_image = image.convert("RGB")

                same_path = (
                    os.path.abspath(target_path).casefold()
                    == os.path.abspath(source_path).casefold()
                )
                if not same_path:
                    target_path = unique_file_path(folder_path, target_name)
                temporary_path = os.path.join(
                    folder_path, f".__converting_{uuid.uuid4().hex}.jpg"
                )
                try:
                    rgb_image.save(temporary_path, format="JPEG", quality=95)
                    os.replace(temporary_path, target_path)
                finally:
                    if os.path.exists(temporary_path):
                        os.remove(temporary_path)

            if not same_path:
                os.remove(source_path)
            logger.debug(f"Converted image to JPEG: {target_path}")
        except (UnidentifiedImageError, OSError, ValueError):
            failed_path = unique_file_path(convert_failed_dir, file_name)
            shutil.move(source_path, failed_path)
            logger.debug(f"Moved non-image file to {failed_path}")


def natural_sort_key(file_name):
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", file_name)
    )


def rename_completed_images(folder_path):
    image_files = [
        os.path.join(folder_path, file_name)
        for file_name in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, file_name))
        and file_name.lower().endswith(".jpg")
    ]
    image_files.sort(key=lambda path: natural_sort_key(os.path.basename(path)))

    rename_plan = []
    page_number = 1
    for source_path in image_files:
        with Image.open(source_path) as image:
            width, height = image.size
        if width > height:
            target_name = f"{page_number:03d}-{page_number + 1:03d}.jpg"
            page_number += 2
        else:
            target_name = f"{page_number:03d}.jpg"
            page_number += 1
        rename_plan.append((source_path, os.path.join(folder_path, target_name)))

    temporary_paths = []
    for source_path, _ in rename_plan:
        temporary_path = os.path.join(
            folder_path, f".__renaming_{uuid.uuid4().hex}.tmp"
        )
        os.replace(source_path, temporary_path)
        temporary_paths.append(temporary_path)

    for temporary_path, (_, target_path) in zip(temporary_paths, rename_plan):
        os.replace(temporary_path, target_path)


def find_barcode_rectangle(image):
    """Find a barcode panel or a solid dark placeholder in the lower half."""
    width, height = image.size
    lower_half_top = height // 2
    lower_half = image.crop((0, lower_half_top, width, height)).convert("RGB")
    crop_area = width * (height - lower_half_top)
    barcodes = zxingcpp.read_barcodes(lower_half)
    barcode_bounds = []
    for barcode in barcodes:
        points = (
            barcode.position.top_left,
            barcode.position.top_right,
            barcode.position.bottom_left,
            barcode.position.bottom_right,
        )
        left = max(0, min(point.x for point in points))
        top = max(0, min(point.y for point in points))
        right = min(width - 1, max(point.x for point in points))
        bottom = min(height - lower_half_top - 1, max(point.y for point in points))
        area = max(1, (right - left) * (bottom - top))
        barcode_bounds.append((left, top, right, bottom, area))

    # Find four-sided regions around decoded bars, and also look for the solid
    # dark rectangles sometimes used to obscure a barcode entirely.
    gray = cv2.cvtColor(np.asarray(lower_half), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    close_width = max(3, width // 250)
    close_height = max(3, height // 250)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_width, close_height))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # Include any earlier green fill as a seed so rerunning the workflow can
    # expand a previous tight barcode hit to its surrounding printed panel.
    green_mask = cv2.inRange(
        np.asarray(lower_half),
        np.array((0, 180, 0), dtype=np.uint8),
        np.array((80, 255, 80), dtype=np.uint8),
    )
    green_contours, _ = cv2.findContours(
        green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    seed_bounds = list(barcode_bounds)
    for contour in green_contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        box_area = box_width * box_height
        if box_area >= crop_area * 0.001:
            seed_bounds.append((x, y, x + box_width - 1, y + box_height - 1, box_area))

    panel_candidates = []
    solid_box_candidates = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        x, y, box_width, box_height = cv2.boundingRect(polygon)
        right = x + box_width - 1
        bottom = y + box_height - 1
        box_area = box_width * box_height
        if (
            box_width < max(40, int(width * 0.035))
            or box_height < max(30, int(height * 0.025))
            or box_area < crop_area * 0.003
            or box_area > crop_area * 0.25
            or not 0.35 <= box_width / box_height <= 6
            or cv2.contourArea(polygon) / box_area < 0.8
        ):
            continue

        for barcode_left, barcode_top, barcode_right, barcode_bottom, barcode_area in seed_bounds:
            if (
                x <= barcode_left
                and y <= barcode_top
                and right >= barcode_right
                and bottom >= barcode_bottom
                and 1.05 <= box_area / barcode_area <= 35
            ):
                panel_candidates.append(
                    (box_area, (x, y, right, bottom + lower_half_top))
                )

        inset = max(2, min(box_width, box_height) // 20)
        inside = gray[y + inset : bottom - inset + 1, x + inset : right - inset + 1]
        if inside.size:
            average_brightness = float(np.mean(inside))
            brightness_spread = float(np.std(inside))
            if average_brightness < 105 and brightness_spread < 22:
                solid_box_candidates.append(
                    (box_area, (x, y, right, bottom + lower_half_top))
                )

    if panel_candidates:
        return min(panel_candidates, key=lambda candidate: candidate[0])[1]

    if solid_box_candidates:
        return min(solid_box_candidates, key=lambda candidate: candidate[0])[1]

    if not barcode_bounds:
        return None

    # When there is no clear panel border, leave enough margin to cover the
    # barcode's label area as well as the bars themselves.
    barcode_left, barcode_top, barcode_right, barcode_bottom, _ = max(
        barcode_bounds, key=lambda bounds: bounds[4]
    )
    margin_x = max(12, int((barcode_right - barcode_left) * 0.35))
    margin_y = max(12, int((barcode_bottom - barcode_top) * 0.25))

    return (
        max(0, barcode_left - margin_x),
        max(0, barcode_top + lower_half_top - margin_y),
        min(width - 1, barcode_right + margin_x),
        min(height - 1, barcode_bottom + lower_half_top + margin_y),
    )


def process_barcode_removal(base_dir):
    """Cover the first lower-half barcode found in each issue folder."""
    stage_dir = os.path.join(base_dir, PROCESS_REMOVE_BARCODE_DIR_NAME)
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")
    folders = [
        os.path.join(stage_dir, name)
        for name in sorted(os.listdir(stage_dir))
        if os.path.isdir(os.path.join(stage_dir, name))
    ]
    for folder_path in folders:
        image_paths = [
            os.path.join(folder_path, name)
            for name in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, name))
            and name.lower().endswith(image_extensions)
        ]
        image_paths.sort(key=lambda path: natural_sort_key(os.path.basename(path)))
        if not image_paths:
            logger.warning(f"No images found in barcode-removal folder: {folder_path}")
            continue

        image_path = image_paths[0]
        try:
            with Image.open(image_path) as source_image:
                image = source_image.convert("RGB")
                rectangle = find_barcode_rectangle(image)
                if rectangle is None:
                    logger.info(f"No lower-half barcode found in {image_path}")
                    continue
                image_draw = ImageDraw.Draw(image)
                image_draw.rectangle(rectangle, fill="#00FF00")
                image_format = source_image.format or "JPEG"
                save_options = (
                    {"quality": 100, "subsampling": 0}
                    if image_format.upper() in {"JPG", "JPEG"}
                    else {}
                )
                backup_path = os.path.join(
                    os.path.dirname(image_path),
                    f"{Path(image_path).stem}_o{Path(image_path).suffix}",
                )
                if not os.path.exists(backup_path):
                    shutil.copy2(image_path, backup_path)
                    logger.info(f"Saved original image: {backup_path}")
                else:
                    logger.debug(f"Original image backup already exists: {backup_path}")
                image.save(image_path, format=image_format, **save_options)
                logger.info(f"Covered barcode in {image_path} at {rectangle}")
        except (OSError, ValueError) as error:
            logger.error(f"Could not process barcode in {image_path}: {error}")


def barcode_processing_skipped():
    return os.getenv("SKIP_BARCODE_PROCESSING", "false").strip().casefold() == "true"


def comic_vine_enabled():
    return os.getenv("ENABLE_COMIC_VINE", "false").strip().casefold() == "true"


def lookup_volume_and_issue(folder_name):
    """Resolve a completed-folder name to ComicVine volume metadata and issue.

    A folder name without an explicit issue number represents issue 1.
    """
    comicvine_id_match = re.fullmatch(
        r"4050-(\d+)(?:\s+(\d+[A-Za-z]*))?", folder_name, flags=re.IGNORECASE
    )
    if comicvine_id_match:
        volume_id = int(comicvine_id_match.group(1))
        issue_number = comicvine_id_match.group(2) or "1"
        volume = fetch_volume_by_id(volume_id)
        if not volume:
            raise ValueError(f"ComicVine volume {volume_id} was not found")
        return volume, volume_id, issue_number

    name_match = re.fullmatch(
        r"(?P<name>.+?)(?:\s+\((?P<year>\d{4})\))?(?:\s+(?P<issue>\d+[A-Za-z]*))?",
        folder_name,
    )
    if not name_match:
        raise ValueError(
            f"Folder must be named '4050-<volume id> <issue>' or '<volume name> <issue>': {folder_name}"
        )

    volume_name = name_match.group("name").strip()
    expected_year = name_match.group("year")
    issue_number = name_match.group("issue") or "1"
    volumes = fetch_volumes(volume_name, limit=100)
    matching_volumes = [
        volume
        for volume in volumes
        if str(volume.get("name", "")).strip().casefold() == volume_name.casefold()
        and (
            not expected_year
            or str(volume.get("start_year", "")) == expected_year
        )
    ]
    if len(matching_volumes) != 1:
        raise ValueError(
            f"Expected one ComicVine volume match for '{volume_name}', "
            f"found {len(matching_volumes)}"
        )

    volume = matching_volumes[0]
    volume_id = int(volume["id"])
    return volume, volume_id, issue_number


def archive_completed_issue(folder_path, done_dir, trash_dir):
    folder_name = os.path.basename(folder_path)
    debug_calls = []
    debug_output_dir = os.path.join(done_dir, "_comicvine_debug")
    try:
        with capture_comicvine_calls() as debug_calls:
            volume, volume_id, issue_number = lookup_volume_and_issue(folder_name)
            volume_name = str(volume.get("name", "")).strip()
            start_year = str(volume.get("start_year", "")).strip()
            if not volume_name or not start_year:
                raise ValueError(
                    "ComicVine did not return a volume name and start year "
                    f"for {folder_name}"
                )

            normalized_volume_name = volume_name.replace("/", " - ")
            normalized_volume_name = normalized_volume_name.replace(":", " -")
            normalized_volume_name = normalized_volume_name.replace("!", "")
            normalized_volume_name = normalized_volume_name.replace("?", "")
            normalized_volume_name = normalized_volume_name.replace(".", "")
            normalized_volume_name = normalized_volume_name.replace("'", "")
            normalized_volume_name = normalized_volume_name.replace("&", "and")
            normalized_volume_name = re.sub(r" {2,}", " ", normalized_volume_name)
            safe_volume_name = re.sub(
                r'[<>"/\\|?*]', "_", normalized_volume_name
            ).strip(" .")
            volume_folder_name = f"{safe_volume_name} ({start_year})"
            volume_folder = os.path.join(done_dir, volume_folder_name)
            debug_output_dir = volume_folder

            issues = fetch_issues_by_volume_and_number(volume_id, issue_number)
            exact_issues = [
                issue
                for issue in issues
                if str(issue.get("issue_number", "")).casefold()
                == issue_number.casefold()
            ]
            if not exact_issues:
                raise ValueError(
                    f"ComicVine issue {issue_number} was not found in volume {volume_name}"
                )
            if len(exact_issues) > 1:
                raise ValueError(
                    f"ComicVine returned multiple matches for issue {issue_number} "
                    f"in volume {volume_name}"
                )
            issue = fetch_comic_by_id(int(exact_issues[0]["id"])) or exact_issues[0]

            deck_values = (volume.get("deck"), issue.get("deck"))
            deck_text = " ".join(str(value) for value in deck_values if value)
            deck_match = re.search(r"\bVolume\s+(\d+)\b", deck_text, re.IGNORECASE)
            if deck_match:
                volume_number = int(deck_match.group(1))
                volume_folder_name = (
                    f"{safe_volume_name} (v{volume_number})({start_year})"
                )
                volume_folder = os.path.join(done_dir, volume_folder_name)
                debug_output_dir = volume_folder
    except Exception:
        write_comicvine_debug_files(debug_output_dir, folder_name, debug_calls)
        raise
    else:
        write_comicvine_debug_files(debug_output_dir, folder_name, debug_calls)

    os.makedirs(volume_folder, exist_ok=True)
    issue_match = re.fullmatch(r"(\d+)([A-Za-z]*)", issue_number)
    if not issue_match:
        raise ValueError(f"Unsupported ComicVine issue number: {issue_number}")
    padded_issue_number = f"{int(issue_match.group(1)):03d}{issue_match.group(2)}"
    archive_name = f"{volume_folder_name} - {padded_issue_number}.cbz"
    archive_path = os.path.join(volume_folder, archive_name)

    temporary_archive = f"{archive_path}.{uuid.uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(
            temporary_archive, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            file_count = 0
            image_count = 0
            for root, _, file_names in os.walk(folder_path):
                for file_name in sorted(file_names):
                    source_path = os.path.join(root, file_name)
                    archive_name_in_zip = os.path.relpath(source_path, folder_path)
                    archive.write(source_path, archive_name_in_zip)
                    file_count += 1
                    if file_name.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".gif", ".webp")
                    ):
                        image_count += 1
            if not file_count:
                raise ValueError(f"No files to archive in {folder_path}")
            archive.writestr(
                "ComicInfo.xml", build_comic_info_xml(volume, issue, image_count)
            )
        os.replace(temporary_archive, archive_path)
    finally:
        if os.path.exists(temporary_archive):
            os.remove(temporary_archive)
    logger.info(f"Created CBZ: {archive_path}")

    trash_destination = get_unique_destination_folder(
        trash_dir, os.path.basename(folder_path)
    )
    shutil.move(folder_path, trash_destination)
    logger.info(f"Moved archived source folder to trash: {trash_destination}")


def write_comicvine_debug_files(destination_dir, comic_folder_name, calls):
    """Write one sanitized API response JSON file per captured ComicVine call."""
    if not logger.isEnabledFor(logging.DEBUG) or not calls:
        return

    safe_comic_name = re.sub(
        r'[<>:"/\\|?*]', "_", comic_folder_name
    ).strip(" .") or "comic"
    try:
        os.makedirs(destination_dir, exist_ok=True)
        for index, call in enumerate(calls, start=1):
            file_name = f"{safe_comic_name}_comicvine_{index:02d}.json"
            debug_path = unique_file_path(destination_dir, file_name)
            with open(debug_path, "w", encoding="utf-8") as debug_file:
                json.dump(call, debug_file, indent=2, ensure_ascii=False)
                debug_file.write("\n")
            logger.debug(f"Wrote ComicVine response data: {debug_path}")
    except OSError as error:
        logger.error(f"Could not write ComicVine debug data to {destination_dir}: {error}")


def build_comic_info_xml(volume, issue, page_count):
    root = ET.Element(
        "ComicInfo",
        {
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )

    def add_text(tag, value):
        element = ET.SubElement(root, tag)
        if value is not None:
            element.text = str(value)

    def names_from_credits(field, roles=None):
        people = []
        for credit in issue.get(field) or []:
            role = str(credit.get("role", "")).casefold()
            if roles is None or role in roles:
                name = credit.get("name")
                if name and name not in people:
                    people.append(name)
        return ",".join(people)

    cover_date = str(issue.get("cover_date") or "")
    date_match = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", cover_date)
    if date_match:
        year, month, day = date_match.groups()
    else:
        year, month, day = volume.get("start_year"), None, None

    add_text("Year", year)
    add_text("Month", month)
    add_text("Day", day)
    add_text("Series", volume.get("name"))
    add_text("Number", issue.get("issue_number"))
    add_text("Title", issue.get("name"))
    description = issue.get("description") or issue.get("deck")
    summary = html.unescape(re.sub(r"<[^>]*>", " ", str(description or "")))
    add_text("Summary", " ".join(summary.split()))
    add_text("Volume", volume.get("start_year"))
    publisher = volume.get("publisher")
    add_text(
        "Publisher",
        publisher.get("name") if isinstance(publisher, dict) else publisher,
    )
    add_text("Web", issue.get("site_detail_url"))
    add_text("Count", volume.get("count_of_issues"))
    add_text("PageCount", page_count)
    add_text("Tags", None)
    add_text("GTIN", None)
    add_text("AgeRating", None)
    add_text("Manga", None)
    add_text("Genre", None)
    add_text("LanguageISO", None)

    creator_roles = {
        "Writer": {"writer"},
        "Penciller": {"penciler", "penciller", "pencils"},
        "Inker": {"inker", "inks"},
        "Colorist": {"colorist", "colors"},
        "Letterer": {"letterer", "letters"},
        "CoverArtist": {"cover", "cover artist", "coverartist"},
        "Editor": {"editor"},
        "Translator": {"translator"},
    }
    for xml_tag, accepted_roles in creator_roles.items():
        add_text(xml_tag, names_from_credits("person_credits", accepted_roles))

    for field, xml_tag in (
        ("character_credits", "Characters"),
        ("team_credits", "Teams"),
        ("location_credits", "Locations"),
        ("story_arc_credits", "StoryArc"),
    ):
        values = []
        for credit in issue.get(field) or []:
            name = credit.get("name")
            if name and name not in values:
                values.append(name)
        add_text(xml_tag, ",".join(values))

    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def process_completed_folders(base_dir):
    completed_dir = os.path.join(base_dir, COMPLETED_DIR_NAME)
    convert_failed_dir = os.path.join(base_dir, CONVERT_FAILED_DIR_NAME)
    junk_root = os.path.join(base_dir, JUNK_FILES_DIR_NAME)
    done_dir = os.path.join(base_dir, DONE_DIR_NAME)
    use_comic_vine = comic_vine_enabled()

    for folder_name in sorted(os.listdir(completed_dir)):
        folder_path = os.path.join(completed_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        logger.info(f"Processing completed comic folder: {folder_name}")
        move_junk_files(folder_path, junk_root)
        convert_images_to_jpg(folder_path, convert_failed_dir)
        rename_completed_images(folder_path)
        if use_comic_vine:
            try:
                archive_completed_issue(
                    folder_path, done_dir, os.path.join(base_dir, TRASH_DIR_NAME)
                )
            except Exception as error:
                logger.error(f"ComicVine processing failed for {folder_name}: {error}")


def convert_comic_files(base_dir):
    convert_dir = os.path.join(base_dir, CONVERT_DIR_NAME)
    convert_failed_dir = os.path.join(base_dir, CONVERT_FAILED_DIR_NAME)
    process_dir = os.path.join(base_dir, PROCESS_DIR_NAME)
    trash_dir = os.path.join(base_dir, TRASH_DIR_NAME)
    junk_root = os.path.join(base_dir, JUNK_FILES_DIR_NAME)

    # Expand comic folders into files in step1_convert before processing them.
    for entry_name in sorted(os.listdir(convert_dir)):
        folder_path = os.path.join(convert_dir, entry_name)
        if os.path.isdir(folder_path):
            try:
                convert_comic_folder(folder_path, convert_dir, trash_dir)
            except (OSError, ValueError) as error:
                logger.error(f"Failed to convert folder {entry_name}: {error}")

    comic_paths = [
        os.path.join(convert_dir, name)
        for name in sorted(os.listdir(convert_dir))
        if os.path.isfile(os.path.join(convert_dir, name))
        and is_comic_file(os.path.join(convert_dir, name))
    ]
    status = {"total": len(comic_paths), "processed": 0, "failed": 0}
    logger.info(f"Found {status['total']} comic(s) to convert.")

    for index, comic_path in enumerate(comic_paths, start=1):
        try:
            convert_comic_file(
                comic_path, process_dir, convert_failed_dir, trash_dir, junk_root
            )
            status["processed"] += 1
            result = "processed"
        except Exception as error:
            status["failed"] += 1
            result = f"failed: {error}"
        logger.info(
            f"[{index}/{status['total']}] {os.path.basename(comic_path)}: {result} "
            f"(processed {status['processed']}, failed {status['failed']}, "
            f"remaining {status['total'] - index})",
        )

    logger.info(
        f"Conversion complete: {status['total']} total, "
        f"{status['processed']} processed, {status['failed']} failed."
    )
    return status


def convert_comic_folder(folder_path, convert_dir, trash_dir):
    folder_name = os.path.basename(folder_path)
    comic_files = []
    for root, _, file_names in os.walk(folder_path):
        for file_name in file_names:
            source_path = os.path.join(root, file_name)
            if is_comic_file(source_path):
                issue_number = extract_issue_number(file_name)
                extension = os.path.splitext(file_name)[1]
                target_path = os.path.join(
                    convert_dir, f"{folder_name} {issue_number}{extension}"
                )
                if os.path.lexists(target_path):
                    raise FileExistsError(
                        f"Converted comic already exists: {target_path}"
                    )
                comic_files.append((source_path, target_path))

    # Validate all output names before copying, so a bad name doesn't leave
    # the source folder half converted.
    target_paths = [target for _, target in comic_files]
    if len(target_paths) != len({target.casefold() for target in target_paths}):
        raise FileExistsError(
            f"Duplicate issue filenames found in folder: {folder_name}"
        )

    for source_path, target_path in comic_files:
        shutil.copy2(source_path, target_path)

    trash_destination = get_unique_destination_folder(trash_dir, folder_name)
    shutil.move(folder_path, trash_destination)
    logger.info(
        f"Copied {len(comic_files)} comic file(s) from {folder_name} to {convert_dir}; "
        f"moved source folder to {trash_destination}."
    )


def convert_comic_file(
    comic_path, process_dir, convert_failed_dir, trash_dir, junk_root
):
    file_name = os.path.basename(comic_path)
    folder_name = os.path.splitext(file_name)[0]
    destination_folder = get_unique_destination_folder(process_dir, folder_name)

    # Create destination folder
    os.makedirs(destination_folder)

    try:
        extract_archive(comic_path, destination_folder)
        logger.info(f"Successfully processed: {file_name}")
    except Exception as e:
        logger.error(f"Failed to process: {file_name} - Error: {e}")
        failed_path = unique_file_path(convert_failed_dir, file_name)
        shutil.move(comic_path, failed_path)
        try:
            shutil.rmtree(destination_folder)
        except OSError as cleanup_error:
            logger.warning(
                f"Could not remove incomplete extraction folder "
                f"{destination_folder}: {cleanup_error}"
            )
        raise

    # Flatten files from any extracted subdirectories into the destination folder.
    for root, dirs, files in os.walk(destination_folder, topdown=False):
        for extracted_name in files:
            source_path = os.path.join(root, extracted_name)
            if root != destination_folder:
                shutil.move(
                    source_path, os.path.join(destination_folder, extracted_name)
                )
        if root != destination_folder:
            os.rmdir(root)

    move_junk_files(destination_folder, junk_root)
    convert_images_to_jpg(destination_folder, convert_failed_dir)

    # Move original comic file to trash
    shutil.move(comic_path, os.path.join(trash_dir, file_name))


def is_comic_file(file_path):
    return file_path.lower().endswith((".cbr", ".cbz", ".cb7", ".zip", ".rar", ".7z"))


def main():
    base_dir = os.environ.get("PARENT_DIR", "/Volumes/Storage/comics")

    try:
        # Create required folders
        create_required_folders(base_dir)

        # Count total files in the step1_convert folder
        convert_dir = os.path.join(base_dir, CONVERT_DIR_NAME)
        total_files = 0
        for entry_name in os.listdir(convert_dir):
            entry_path = os.path.join(convert_dir, entry_name)
            if os.path.isfile(entry_path) and is_comic_file(entry_path):
                total_files += 1
            elif os.path.isdir(entry_path):
                total_files += sum(
                    1
                    for root, _, file_names in os.walk(entry_path)
                    for file_name in file_names
                    if is_comic_file(file_name)
                )

        if total_files == 0:
            logger.info(
                f"No comic files found in '{CONVERT_DIR_NAME}' folder. Nothing to process."
            )
        else:
            logger.info(f"Starting job processing for {total_files} comic files...")
            convert_comic_files(base_dir)

        if barcode_processing_skipped():
            logger.info("Skipping barcode processing because SKIP_BARCODE_PROCESSING=true")
        else:
            process_barcode_removal(base_dir)
        process_completed_folders(base_dir)
        logger.info("Job processing completed!")
    finally:
        normalize_junk_file()


if __name__ == "__main__":
    main()
