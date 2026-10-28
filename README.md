# Comic Processor

A Python workflow for extracting comic archives, preparing scanned page images, and optionally packaging completed issues with ComicVine metadata.

## Requirements

- Python 3.10 or newer
- Dependencies from `requirements.txt`
- A ComicVine API key when `ENABLE_COMIC_VINE=true`

Install dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then set the values needed for your workflow:

```dotenv
PARENT_DIR=/path/to/comics
COMICVINE_API_KEY=your_api_key
ENABLE_COMIC_VINE=false
SKIP_BARCODE_PROCESSING=false
LOG_LEVEL=INFO
GET_COMICS_ORG_DELAY_SECONDS=1
GET_COMICS_ORG_RETRY_COUNT=3
```

`PARENT_DIR` defaults to `/Volumes/Storage/comics`. ComicVine integration is disabled unless `ENABLE_COMIC_VINE` is exactly `true` (case-insensitive). Set `SKIP_BARCODE_PROCESSING=true` to skip barcode detection and image modification; it defaults to `false`. `LOG_LEVEL` controls console logging and accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; it defaults to `INFO`. `GET_COMICS_ORG_DELAY_SECONDS` sets the pause between GetComics archive-page requests (default `1`), and `GET_COMICS_ORG_RETRY_COUNT` sets retries after a failed request (default `3`). With `LOG_LEVEL=DEBUG`, each ComicVine API response is saved as a separate JSON file in the volume's `step4_done` destination folder. If no volume destination can be resolved, dumps go in `step4_done/_comicvine_debug`. API keys are omitted. `comic_processor.py` loads `.env` from the project directory.

## Run the workflow

```bash
python job_flow.py
```

The job reports the comic count, progress, and conversion results. It creates any missing workflow directories under `PARENT_DIR`.

## Workflow folders

| Folder | Purpose |
| --- | --- |
| `step0_trash` | Source folders and archives moved aside after conversion |
| `step0.1_junk_files` | Files matching patterns in `junk_files.txt`, grouped by comic folder |
| `step1_convert` | Source archives or folders containing per-issue archives |
| `step1.1_convert_failed` | Non-image extracted files and failed conversions |
| `step2_process` | Extracted comic issues, one directory per archive |
| `step2.1_process_remove_border` | Manual border-removal stage |
| `step2.2_process_remove_barcode` | Barcode cleanup stage; the job covers a detected barcode on the first image of each issue folder |
| `step2.3_process_manual_cleanup` | Manual cleanup stage |
| `step2.4_process_covers` | Cover-processing stage |
| `step3_completed` | Completed issue folders ready for page renumbering and optional packaging |
| `step4_done` | Final CBZ archives, grouped by series and start year |

## Conversion behavior

- Direct archives in `step1_convert` are extracted to `step2_process/<archive name>/`.
- Subfolders in `step1_convert` are scanned recursively. Their comic archives are copied to `step1_convert` as `<source folder> <issue number>.<extension>`, then the source folder is moved to `step0_trash`.
- Existing destination folder names are preserved. A collision creates a numbered folder such as `Issue (1)`.
- Extracted files are flattened into the issue folder. Files matching case-insensitive wildcard patterns in `junk_files.txt` are moved to `step0.1_junk_files/<issue folder>/`.
- Readable images are converted to JPEG. Other files are moved to `step1.1_convert_failed`.
- An archive that fails extraction is moved to `step1.1_convert_failed`; its incomplete extraction folder is removed, and the job continues with the next archive.
- For each issue folder in `step2.2_process_remove_barcode`, the job checks the first image in natural filename order for a barcode in the lower half. It covers the enclosing panel when detected, or a large solid dark rectangle used in place of a barcode, with `#00FF00`. Before editing, it saves the original once as `<filename>_o.<extension>`; existing backups are preserved. Folders without a detected barcode or solid rectangle are left unchanged.
- After each run, `junk_files.txt` is sorted and its nonblank patterns are converted to lowercase.

Put one filename pattern per line in `junk_files.txt`. Patterns use shell-style wildcards such as `*.db` or `thumbs*`; matching is case-insensitive and applies to filenames.

## Completed issues and ComicVine

For each folder under `step3_completed`, the job applies junk-file patterns, converts images to JPEG, and renumbers pages in natural filename order. Portrait pages receive names such as `001.jpg`; landscape spreads receive a page range such as `002-003.jpg` and advance the page counter by two.

When `ENABLE_COMIC_VINE=true`, each completed folder is matched to ComicVine. Folder names may use the ComicVine ID form `4050-<volume id> <issue number>` (for example, `4050-160511 1`) or `<volume name> <issue number>`. Issue numbers can include a decimal and/or letter suffix, such as `615.1` or `12A`; the integer part is padded to three digits in the archive name (for example, `615.1` stays `615.1`, while `1.1` becomes `001.1`). A folder name with no issue number, including a bare ComicVine ID such as `4050-89803`, is treated as issue `1`. Destination volume names remove `!`, `?`, `"`, `,`, `.`, and `'`, replace `/` with ` - `, replace `:` with ` - `, and replace `&` with `and`; the normalized name is used for both the output folder and CBZ archive. If the matched issue title contains `TPB`, ` TPB` is appended to the volume name before the year (for example, `Avengers - The Enemy Within (2013)` becomes `Avengers - The Enemy Within TPB (2013)`). For example, `Black Hammer/Justice League: Hammer of Justice!` becomes `Black Hammer - Justice League - Hammer of Justice`, `Grimm Spotlight - Hercules Payne vs. The Scorpion Queen` becomes `Grimm Spotlight - Hercules Payne vs The Scorpion Queen`, and `Black Hammer '45` becomes `Black Hammer 45`. If the ComicVine volume or issue `deck` includes `Volume <number>`, the `(v<number>)` marker is added before the start year in the output folder and archive name (for example, `Hawkman (v1)(1964)`). The workflow creates:

```text
step4_done/<Volume Name> (<start year>)/<Volume Name> (<start year>) - <issue padded to 3>.cbz
step4_done/<Volume Name> (v<number>)(<start year>)/<Volume Name> (v<number>)(<start year>) - <issue padded to 3>.cbz
```

For example, issue `1` becomes `001.cbz`. The archive contains the page images and a `ComicInfo.xml` file at its root. Available volume and issue metadata is written into ComicInfo fields; fields without values are emitted as empty XML elements. After the CBZ is successfully created, its source folder is moved to `step0_trash`. If ComicVine lookup or archive creation fails, the error is reported and the source folder remains in `step3_completed` for review or retry.

To update existing CBZ folders from their embedded `ComicInfo.xml` metadata, run `python refresh_comicvine_deck_names.py --root /path/to/comic/library` for a dry run. Add `--apply` to rename folders and CBZ files. It adds ` TPB` when an issue's ComicInfo title contains `TPB`. The utility caches volume lookups in `comicvine_deck_refresh_cache.json` so large libraries can be handled in batches; it defaults to at most 450 new volume searches per run. Use `--cached-only` to process cached results without network lookups. If ComicVine throttles the request, the batch pauses and can be resumed later with the same cache.

## Other modules

- `comic_processor.py` contains archive extraction, ComicVine API helpers, and optional Komga integration functions.
- `example_usage.py` demonstrates ComicVine API helper calls.
- `test_archive_extraction.py` contains archive extraction examples/tests.
- `YOLO_TRAINING.md` documents how to prepare data and train a YOLO barcode-region detector, and describes the integration needed to replace the current OpenCV-based rectangle detection.

Configure Komga with the relevant `KOMGA_*` variables shown in `.env.example` before calling the Komga integration functions.
