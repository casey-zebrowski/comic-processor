# Example usage of the comic-processor

import os
import sys

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from comic_processor import (
    fetch_comic_by_id,
    fetch_comics,
    fetch_volume_by_id,
    fetch_volumes,
    get_api_key_status,
    process_comic,  # Added for testing archive extraction
)

# Check API key status
status = get_api_key_status()
print(f"API Key Status: {'Valid' if status['is_valid'] else 'Invalid'}")

if status['is_valid']:
    try:
        # Fetch comics
        print("\nFetching comics...")
        comics = fetch_comics("spider-man", 5)
        for comic in comics:
            print(f"- {comic.get('name', 'Unknown')} (Issue #{comic.get('issue_number', 'N/A')})")
         
        # Fetch volumes
        print("\nFetching volumes...")
        volumes = fetch_volumes("marvel", 5)
        for volume in volumes:
            print(f"- {volume.get('name', 'Unknown')} ({volume.get('start_year', 'N/A')})")
         
        # Fetch specific comic by ID
        if comics:
            print("\nFetching specific comic...")
            comic_id = comics[0].get('id')
            if comic_id:
                specific_comic = fetch_comic_by_id(comic_id)
                print(f"Specific comic: {specific_comic.get('name', 'Unknown')}")
        
        # Test archive extraction (uncomment and modify the path as needed)
        # process_comic('/path/to/comic.cbz')
        # process_comic('/path/to/comic.cbr')
        # process_comic('/path/to/comic.cb7')
         
    except Exception as e:
        print(f"Error during usage: {e}")
else:
    print("Please set your ComicVine API key in the environment variable COMICVINE_API_KEY")