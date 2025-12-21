#!/usr/bin/env python3
"""
Comic Book Extractor

Extracts comic book files (CBZ, CBR, ZIP) to separate folders.
Each comic file is extracted into its own folder named after the file.
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path


def extract_zip(file_path, output_dir):
    """
    Extract a ZIP/CBZ file to a separate folder.
    
    Args:
        file_path: Path to the ZIP/CBZ file
        output_dir: Directory where the extraction folder will be created
    
    Returns:
        True if extraction succeeded, False otherwise
    """
    try:
        file_path = Path(file_path)
        output_dir = Path(output_dir)
        
        # Create folder name from file name (without extension)
        folder_name = file_path.stem
        extract_path = output_dir / folder_name
        
        # Create the extraction directory
        extract_path.mkdir(parents=True, exist_ok=True)
        
        # Extract the ZIP file
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        print(f"✓ Extracted: {file_path.name} -> {extract_path}")
        return True
    except zipfile.BadZipFile:
        print(f"✗ Error: {file_path.name} is not a valid ZIP file", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error extracting {file_path.name}: {e}", file=sys.stderr)
        return False


def extract_rar(file_path, output_dir):
    """
    Extract a RAR/CBR file to a separate folder.
    
    Args:
        file_path: Path to the RAR/CBR file
        output_dir: Directory where the extraction folder will be created
    
    Returns:
        True if extraction succeeded, False otherwise
    """
    try:
        import rarfile
    except ImportError:
        print("✗ Error: rarfile module not installed. Install it with: pip install rarfile", file=sys.stderr)
        print("  Note: You also need the unrar utility installed on your system.", file=sys.stderr)
        return False
    
    try:
        file_path = Path(file_path)
        output_dir = Path(output_dir)
        
        # Create folder name from file name (without extension)
        folder_name = file_path.stem
        extract_path = output_dir / folder_name
        
        # Create the extraction directory
        extract_path.mkdir(parents=True, exist_ok=True)
        
        # Extract the RAR file
        with rarfile.RarFile(file_path, 'r') as rar_ref:
            rar_ref.extractall(extract_path)
        
        print(f"✓ Extracted: {file_path.name} -> {extract_path}")
        return True
    except rarfile.BadRarFile:
        print(f"✗ Error: {file_path.name} is not a valid RAR file", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error extracting {file_path.name}: {e}", file=sys.stderr)
        return False


def extract_comic(file_path, output_dir):
    """
    Extract a comic book file based on its extension.
    
    Args:
        file_path: Path to the comic file
        output_dir: Directory where the extraction folder will be created
    
    Returns:
        True if extraction succeeded, False otherwise
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    
    if extension in ['.cbz', '.zip']:
        return extract_zip(file_path, output_dir)
    elif extension == '.cbr':
        return extract_rar(file_path, output_dir)
    else:
        print(f"✗ Skipping: {file_path.name} (unsupported format)", file=sys.stderr)
        return False


def process_directory(input_dir, output_dir, recursive=False):
    """
    Process all comic book files in a directory.
    
    Args:
        input_dir: Directory containing comic book files
        output_dir: Directory where extraction folders will be created
        recursive: Whether to search subdirectories recursively
    
    Returns:
        Tuple of (success_count, failure_count)
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    # Find comic book files (case-insensitive)
    patterns = ['*.[cC][bB][zZ]', '*.[cC][bB][rR]', '*.[zZ][iI][pP]']
    comic_files = []
    
    if recursive:
        for pattern in patterns:
            comic_files.extend(input_dir.rglob(pattern))
    else:
        for pattern in patterns:
            comic_files.extend(input_dir.glob(pattern))
    
    if not comic_files:
        print("No comic book files found.")
        return 0, 0
    
    print(f"Found {len(comic_files)} comic book file(s)\n")
    
    success_count = 0
    failure_count = 0
    
    for comic_file in sorted(comic_files):
        if extract_comic(comic_file, output_dir):
            success_count += 1
        else:
            failure_count += 1
    
    return success_count, failure_count


def main():
    """Main entry point for the comic book extractor."""
    parser = argparse.ArgumentParser(
        description='Extract comic book files (CBZ, CBR, ZIP) to separate folders',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all comics in current directory to 'extracted' folder
  %(prog)s
  
  # Extract comics from specific directory
  %(prog)s -i /path/to/comics
  
  # Extract to specific output directory
  %(prog)s -i /path/to/comics -o /path/to/output
  
  # Extract recursively from subdirectories
  %(prog)s -i /path/to/comics -r
  
  # Extract specific file
  %(prog)s -f comic.cbz
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        default='.',
        help='Input directory containing comic book files (default: current directory)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output directory for extracted files (default: same as input directory)'
    )
    
    parser.add_argument(
        '-f', '--file',
        help='Extract a specific comic book file instead of processing a directory'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Search for comic files recursively in subdirectories'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if args.file:
        # Extract single file
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        
        if not file_path.is_file():
            print(f"Error: Not a file: {args.file}", file=sys.stderr)
            sys.exit(1)
        
        # Use output directory or file's parent directory
        output_dir = Path(args.output) if args.output else file_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        success = extract_comic(file_path, output_dir)
        sys.exit(0 if success else 1)
    else:
        # Extract directory
        input_dir = Path(args.input)
        if not input_dir.exists():
            print(f"Error: Directory not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        
        if not input_dir.is_dir():
            print(f"Error: Not a directory: {args.input}", file=sys.stderr)
            sys.exit(1)
        
        # Use output directory or input directory
        output_dir = Path(args.output) if args.output else input_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")
        print(f"Recursive: {args.recursive}\n")
        
        success_count, failure_count = process_directory(input_dir, output_dir, args.recursive)
        
        print(f"\nSummary:")
        print(f"  Successfully extracted: {success_count}")
        print(f"  Failed: {failure_count}")
        
        sys.exit(0 if failure_count == 0 else 1)


if __name__ == '__main__':
    main()
