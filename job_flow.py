import fnmatch
import os
import shutil
from pathlib import Path

from comic_processor import extract_archive

JUNK_FILES_PATH = Path(__file__).with_name("junk_files.txt")


def create_required_folders(base_dir):
    folders = [
        "step0-trash",
        "step0.1-junk_files",
        "step1-convert",
        "step1.1-convert_failed",
        "step2-process",
        "step2.1-process-remove_border",
        "step2.2-process-remove_barcode",
        "step2.3-manual_cleanup",
        "step2.4-process_covers",
        "step3-completed",
        "step4-done",
    ]

    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Created folder: {folder_path}")


def get_unique_destination_folder(parent_dir, folder_name):
    """Return a folder path that won't overwrite an existing destination."""
    destination = os.path.join(parent_dir, folder_name)
    duplicate_number = 1
    while os.path.lexists(destination):
        destination = os.path.join(parent_dir, f"{folder_name} ({duplicate_number})")
        duplicate_number += 1
    return destination


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
            print(f"Moved junk file: {file_path} -> {destination_path}")


def convert_comic_files(base_dir):
    convert_dir = os.path.join(base_dir, "step1-convert")
    convert_failed_dir = os.path.join(base_dir, "step1.1-convert_failed")
    process_dir = os.path.join(base_dir, "step2-process")
    trash_dir = os.path.join(base_dir, "step0-trash")
    junk_root = os.path.join(base_dir, "step0.1-junk_files")

    comic_paths = [
        os.path.join(convert_dir, name)
        for name in sorted(os.listdir(convert_dir))
        if os.path.isfile(os.path.join(convert_dir, name))
        and is_comic_file(os.path.join(convert_dir, name))
    ]
    status = {"total": len(comic_paths), "processed": 0, "failed": 0}
    print(f"Found {status['total']} comic(s) to convert.")

    for index, comic_path in enumerate(comic_paths, start=1):
        try:
            convert_comic_file(
                comic_path, process_dir, convert_failed_dir, trash_dir, junk_root
            )
            status["processed"] += 1
            result = "processed"
        except (OSError, ValueError) as error:
            status["failed"] += 1
            result = f"failed: {error}"
        print(
            f"[{index}/{status['total']}] {os.path.basename(comic_path)}: {result} "
            f"(processed {status['processed']}, failed {status['failed']}, "
            f"remaining {status['total'] - index})"
        )

    print(
        f"Conversion complete: {status['total']} total, "
        f"{status['processed']} processed, {status['failed']} failed."
    )
    return status


def convert_comic_folder(folder_path, process_dir):
    folder_name = os.path.basename(folder_path)
    destination_folder = get_unique_destination_folder(process_dir, folder_name)

    # Create destination folder
    os.makedirs(destination_folder)

    # Move existing files to the destination folder
    for item_name in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item_name)
        if os.path.isfile(item_path):
            shutil.move(item_path, destination_folder)

    # Extract comic archives
    for item_name in os.listdir(destination_folder):
        item_path = os.path.join(destination_folder, item_name)
        if is_comic_file(item_path):
            # extract_and_rename(item_path, destination_folder, folder_name)
            continue


def convert_comic_file(comic_path, process_dir, convert_failed_dir, trash_dir, junk_root):
    file_name = os.path.basename(comic_path)
    folder_name = os.path.splitext(file_name)[0]
    destination_folder = get_unique_destination_folder(process_dir, folder_name)

    # Create destination folder
    os.makedirs(destination_folder)

    try:
        extract_archive(comic_path, destination_folder)
        print(f"Successfully processed: {file_name}")
    except Exception as e:
        print(f"Failed to process: {file_name} - Error: {e}")
        shutil.move(comic_path, os.path.join(convert_failed_dir, file_name))
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

    # Move original comic file to trash
    shutil.move(comic_path, os.path.join(trash_dir, file_name))


def is_comic_file(file_path):
    return file_path.endswith((".cbr", ".cbz", ".cb7", ".zip", ".rar", ".7z"))


def main():
    base_dir = os.environ.get("PARENT_DIR", "/Volumes/Storage/comics")

    try:
        # Create required folders
        create_required_folders(base_dir)

        # Count total files in the step1-convert folder
        convert_dir = os.path.join(base_dir, "step1-convert")
        comic_files = [
            f
            for f in os.listdir(convert_dir)
            if is_comic_file(os.path.join(convert_dir, f))
        ]
        total_files = len(comic_files)

        if total_files == 0:
            print("No comic files found in step1-convert folder. Nothing to process.")
            return

        print(f"Starting job processing for {total_files} comic files...")

        # Convert comic files
        convert_comic_files(base_dir)

        print("Job processing completed!")
    finally:
        normalize_junk_file()


if __name__ == "__main__":
    main()
