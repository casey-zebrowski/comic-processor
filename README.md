# comic-processor

Comic book processor

## Getting an API Key

1. Visit [ComicVine API](https://comicvine.gamespot.com/api/)
2. Register for a free API key
3. Add your API key to the environment variables

## Setting up Environment Variables

You can set the API key in your environment:

```bash
export COMICVINE_API_KEY="your_api_key_here"
```

## Features

- Process comic archives (CBZ, CBR, CB7)
- Extract and organize comic files
- Integrate with Komga library management system
- Batch processing through job flow

## Status Reporting

The tool now provides detailed status reporting during processing:

### In `job_flow.py`:
- Shows total number of comics to process at start
- Displays progress for each individual comic file processed
- Reports success/failure counts
- Shows remaining files to process
- Indicates when processing is complete

### In `comic_processor.py`:
- Shows number of comics and volumes found during example searches
- Provides clear status messages for API key validation

## Usage

1. Set up environment variables (KOMGA_URL, KOMGA_API_KEY, etc.)
2. Configure your ComicVine API key in the `.env` file
3. Run `python job_flow.py` to process comics in the step folders
4. Run `python comic_processor.py` for example searches and processing

## Folder Structure

The tool expects a specific folder structure:
- `step0-trash` - Files moved to trash after processing
- `step1-convert` - Source comic files to be processed  
- `step1.1-convert_failed` - Failed conversions
- `step2-process` - Processed comic files
- `step2.1-process-remove_border` - Files with border removal
- `step2.2-process-remove_barcode` - Files with barcode removal
- `step2.3-manual_cleanup` - Files requiring manual cleanup
- `step2.4-process_covers` - Cover processing
- `step3-completed` - Completed comics
- `step4-done` - Final destination

## Requirements

- Python 3.8+
- Required packages in requirements.txt