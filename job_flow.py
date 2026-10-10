import os
import shutil

from comic_processor import extract_archive


def create_required_folders(base_dir):
    folders = [
        "step0-trash",
        "step1-convert",
        "step2-process",
        "step2.1-process-remove_border",
        "step2.2-process-remove_barcode",
        "step2.3-manual_cleanup",
        "step2.4-process_covers",
        "step3-completed",
        "step4-done"
    ]

    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Created folder: {folder_path}")

def process_comic_files(base_dir):
    convert_dir = os.path.join(base_dir, "step1-convert")
    process_dir = os.path.join(base_dir, "step2-process")

    # Iterate through the step1-convert folder
    for item_name in os.listdir(convert_dir):
        item_path = os.path.join(convert_dir, item_name)

        if os.path.isdir(item_path):
            # Process each folder in step1-convert
            process_folder(item_path, process_dir)
        elif os.path.isfile(item_path) and is_comic_file(item_path):
            # Process individual comic files
            process_file(item_path, process_dir)

def process_folder(folder_path, process_dir):
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
            extract_and_rename(item_path, destination_folder, folder_name)

def process_file(file_path, process_dir):
    file_name = os.path.basename(file_path)
    destination_folder = os.path.join(process_dir, file_name)

    # Create destination folder
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Move the file to the destination folder
    shutil.move(file_path, os.path.join(destination_folder, file_name))

    # Extract and rename the comic file
    extract_and_rename(os.path.join(destination_folder, file_name), destination_folder, file_name)

def is_comic_file(file_path):
    return file_path.endswith(('.cbr', '.cbz', '.cb7', '.zip', '.rar', '.7z'))

def extract_and_rename(file_path, destination_folder, folder_name):
    # Extract the archive
    extract_archive(file_path, destination_folder)

    # Get the extracted files
    extracted_files = os.listdir(destination_folder)

    # Rename the files with the folder name and a number
    for i, file_name in enumerate(extracted_files):
        old_file_path = os.path.join(destination_folder, file_name)
        new_file_name = f"{folder_name} {i+1}"
        new_file_path = os.path.join(destination_folder, new_file_name)

        # Only rename if it's not a directory
        if os.path.isfile(old_file_path):
            os.rename(old_file_path, new_file_path)
            print(f"Renamed: {old_file_path} -> {new_file_path}")

def main():
    base_dir = "/Volumes/Storage/comics"

    # Create required folders
    create_required_folders(base_dir)

    # Process comic files
    process_comic_files(base_dir)

if __name__ == "__main__":
    main()