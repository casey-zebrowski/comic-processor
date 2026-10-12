import os
import shutil

from comic_processor import extract_archive


def create_required_folders(base_dir):
    folders = [
        "step0-trash",
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


def convert_comic_files(base_dir):
    convert_dir = os.path.join(base_dir, "step1-convert")
    convert_failed_dir = os.path.join(base_dir, "step1.1-convert_failed")
    process_dir = os.path.join(base_dir, "step2-process")
    trash_dir = os.path.join(base_dir, "step0-trash")

    # Iterate through the step1-convert folder
    for comic_name in os.listdir(convert_dir):
        comic_path = os.path.join(convert_dir, comic_name)

        if os.path.isdir(comic_path):
            # Convert each folder in step1-convert
            # convert_comic_folder(item_path, process_dir)
            continue
        elif os.path.isfile(comic_path) and is_comic_file(comic_path):
            # Process individual comic files
            convert_comic_file(comic_path, process_dir, convert_failed_dir, trash_dir)


def convert_comic_folder(folder_path, process_dir):
    folder_name = os.path.basename(folder_path)
    destination_folder = os.path.join(process_dir, folder_name)

    # Create destination folder
    if not os.path.exists(destination_folder):
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


def convert_comic_file(comic_path, process_dir, convert_failed_dir, trash_dir):
    file_name = os.path.basename(comic_path)
    folder_name = os.path.splitext(file_name)[0]
    destination_folder = os.path.join(process_dir, folder_name)

    # Create destination folder
    os.makedirs(destination_folder, exist_ok=True)

    try:
        extract_archive(comic_path, destination_folder)
    except (OSError, ValueError):
        shutil.move(comic_path, os.path.join(convert_failed_dir, file_name))
        return

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

    shutil.move(comic_path, os.path.join(trash_dir, file_name))


def is_comic_file(file_path):
    return file_path.endswith((".cbr", ".cbz", ".cb7", ".zip", ".rar", ".7z"))


def main():
    base_dir = os.environ.get("PARENT_DIR", "/Volumes/Storage/comics")

    # Create required folders
    create_required_folders(base_dir)

    # Convert comic files
    convert_comic_files(base_dir)


if __name__ == "__main__":
    main()
