# comic-processor

Comic book processor - Extract CBZ, CBR, and ZIP comic book files to separate folders.

## Features

- Extracts comic book files (CBZ, CBR, ZIP) to separate folders
- Each comic file is extracted into its own folder named after the file
- Supports batch processing of multiple files
- Recursive directory scanning option
- Error handling for corrupted files

## Requirements

- Python 3.6 or higher
- For CBR (RAR) file support:
  - Install `rarfile` Python package: `pip install rarfile`
  - Install `unrar` utility on your system:
    - **Ubuntu/Debian**: `sudo apt-get install unrar`
    - **macOS**: `brew install unrar`
    - **Windows**: Download from https://www.rarlab.com/

## Installation

1. Clone this repository:
```bash
git clone https://github.com/casey-zebrowski/comic-processor.git
cd comic-processor
```

2. (Optional) Install dependencies for CBR support:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Extract all comics in the current directory:
```bash
python extract_comics.py
```

### Extract from Specific Directory

```bash
python extract_comics.py -i /path/to/comics
```

### Extract to Specific Output Directory

```bash
python extract_comics.py -i /path/to/comics -o /path/to/output
```

### Extract Recursively from Subdirectories

```bash
python extract_comics.py -i /path/to/comics -r
```

### Extract a Single File

```bash
python extract_comics.py -f comic.cbz
```

### Command-Line Options

```
usage: extract_comics.py [-h] [-i INPUT] [-o OUTPUT] [-f FILE] [-r]

Extract comic book files (CBZ, CBR, ZIP) to separate folders

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input directory containing comic book files (default: current directory)
  -o OUTPUT, --output OUTPUT
                        Output directory for extracted files (default: same as input directory)
  -f FILE, --file FILE  Extract a specific comic book file instead of processing a directory
  -r, --recursive       Search for comic files recursively in subdirectories
```

## Examples

### Example 1: Extract all comics in current directory
```bash
$ python extract_comics.py
Found 3 comic book file(s)

✓ Extracted: Amazing_Spider-Man_001.cbz -> ./Amazing_Spider-Man_001
✓ Extracted: Batman_050.cbr -> ./Batman_050
✓ Extracted: Superman_100.zip -> ./Superman_100

Summary:
  Successfully extracted: 3
  Failed: 0
```

### Example 2: Extract specific file to custom location
```bash
$ python extract_comics.py -f /comics/MyComic.cbz -o /extracted
✓ Extracted: MyComic.cbz -> /extracted/MyComic
```

## File Format Support

- **CBZ** - Comic Book ZIP (standard ZIP archive containing images)
- **CBR** - Comic Book RAR (RAR archive containing images, requires rarfile and unrar)
- **ZIP** - Standard ZIP archives

## License

See [LICENSE](LICENSE) file for details.
