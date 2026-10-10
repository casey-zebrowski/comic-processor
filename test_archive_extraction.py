import os
import sys
import zipfile

import py7zr
import rarfile


def extract_archive(comic_file: str, output_dir: str) -> None:
    """Extract and flatten comic archive (.cbr, .cbz, .cb7)"""
    try:
        print(f'Extracting archive: {comic_file}')

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Determine file extension and extract accordingly
        file_extension = comic_file.lower().split('.')[-1]

        if file_extension == 'cbz':
            # Handle ZIP archive (.cbz)
            with zipfile.ZipFile(comic_file, 'r') as zip_ref:
                zip_ref.extractall(output_dir)
                print(f'Successfully extracted ZIP archive: {comic_file}')
        elif file_extension == 'cbr':
            # Handle RAR archive (.cbr)
            with rarfile.RarFile(comic_file, 'r') as rar_ref:
                rar_ref.extractall(output_dir)
                print(f'Successfully extracted RAR archive: {comic_file}')
        elif file_extension == 'cb7':
            # Handle 7zip archive (.cb7)
            with py7zr.SevenZipFile(comic_file, mode='r') as sz_ref:
                sz_ref.extractall(path=output_dir)
                print(f'Successfully extracted 7zip archive: {comic_file}')
        else:
            raise ValueError(f'Unsupported archive format: {file_extension}')

    except Exception as e:
        print(f'Error extracting archive: {e}')
        raise

# Test the extraction function
if __name__ == '__main__':
    # Create a test archive for each type
    test_dir = 'test_archives'
    os.makedirs(test_dir, exist_ok=True)

    # Create a test file
    test_file_path = os.path.join(test_dir, 'test.txt')
    with open(test_file_path, 'w') as f:
        f.write('This is a test file for archive extraction.')

    # Create a ZIP archive (.cbz)
    cbz_file = os.path.join(test_dir, 'test.cbz')
    with zipfile.ZipFile(cbz_file, 'w') as zipf:
        zipf.write(test_file_path, os.path.basename(test_file_path))

    # Note: We can't create a RAR archive with rarfile, so we'll just test with a ZIP and 7zip archive

    # Create a 7zip archive (.cb7)
    cb7_file = os.path.join(test_dir, 'test.cb7')
    with py7zr.SevenZipFile(cb7_file, 'w') as szf:
        szf.write(test_file_path, os.path.basename(test_file_path))

    # Extract each archive
    print('\nExtracting ZIP archive (.cbz):')
    extract_archive(cbz_file, os.path.join(test_dir, 'extracted_cbz'))

    # Note: We can't test RAR extraction without a RAR file
    # print('\nExtracting RAR archive (.cbr):')
    # extract_archive(cbr_file, os.path.join(test_dir, 'extracted_cbr'))

    print('\nExtracting 7zip archive (.cb7):')
    extract_archive(cb7_file, os.path.join(test_dir, 'extracted_cb7'))

    print('\nTest completed successfully.')
