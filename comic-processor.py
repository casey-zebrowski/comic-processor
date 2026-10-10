import os
import shutil
import uuid
import zipfile  # Added for .cbz (ZIP) files
from pathlib import Path
from typing import Any, Optional

import py7zr  # Added for .cb7 (7zip) files
import rarfile  # Added for .cbr (RAR) files
import requests  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
from dotenv import load_dotenv
from smbprotocol.connection import (  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
    Connection,
)
from smbprotocol.open import (  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
    CreateDisposition,
    Open,
)
from smbprotocol.session import (  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
    Session,
)
from smbprotocol.tree import (  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
    TreeConnect,  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]
)

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

# Read configuration
api_key = os.getenv("API_KEY")

# ComicVine API configuration
COMICVINE_API_BASE = "https://comicvine.gamespot.com/api"
API_KEY = os.getenv('COMICVINE_API_KEY') or os.getenv('VITE_COMICVINE_API_KEY')
COMICVINE_HEADERS = {
    "User-Agent": "ComicProcessor/1.0 (personal comic library)",
    "Accept": "application/json",
}

# Komga configuration
KOMGA_LIBRARY_PATH = os.getenv('KOMGA_LIBRARY_PATH')
KOMGA_URL = os.getenv('KOMGA_URL')
KOMGA_API_KEY = os.getenv('KOMGA_API_KEY')
KOMGA_SMB_PATH = os.getenv('KOMGA_SMB_PATH')
KOMGA_SMB_USERNAME = os.getenv('KOMGA_SMB_USERNAME')
KOMGA_SMB_PASSWORD = os.getenv('KOMGA_SMB_PASSWORD')

if not API_KEY:
    print('Warning: ComicVine API key not found. Please set COMICVINE_API_KEY environment variable.')

if not KOMGA_LIBRARY_PATH and not KOMGA_URL and not KOMGA_SMB_PATH:
    print('Warning: Neither Komga library path, Komga URL, nor Komga SMB path is set. Please set one of these environment variables.')

def move_to_komga(file_path: str) -> None:
    """Move a comic file to the Komga library directory or notify Komga of a new comic"""
    if KOMGA_LIBRARY_PATH:
        try:
            shutil.move(file_path, KOMGA_LIBRARY_PATH)
            print(f'Moved {file_path} to Komga library.')
        except Exception as e:
            print(f'Error moving file to Komga library: {e}')
            raise
    elif KOMGA_SMB_PATH:
        try:
            move_to_komga_smb(file_path, KOMGA_SMB_PATH)
            print(f'Moved {file_path} to Komga SMB share.')
        except Exception as e:
            print(f'Error moving file to Komga SMB share: {e}')
            raise
    elif KOMGA_URL and KOMGA_API_KEY:
        try:
            notify_komga_of_new_comic(file_path)
            print(f'Notified Komga of new comic: {file_path}')
        except Exception as e:
            print(f'Error notifying Komga of new comic: {e}')
            raise
    else:
        raise ValueError('Komga configuration is required. Please set KOMGA_LIBRARY_PATH, KOMGA_URL and KOMGA_API_KEY, or KOMGA_SMB_PATH environment variables.')

def move_to_komga_smb(file_path: str, smb_path: str) -> None:
    """Move a comic file to the Komga SMB share"""
    if not KOMGA_SMB_USERNAME or not KOMGA_SMB_PASSWORD:
        raise ValueError('Komga SMB username and password are required to access the SMB share.')

    try:
        # Parse the SMB path
        smb_url = smb_path.replace('smb://', '')
        server_name, share_name = smb_url.split('/', 1)

        # Connect to the SMB server
        connection = Connection(uuid.uuid4(), server_name, 445)
        connection.connect()

        # Create a session
        session = Session(connection, KOMGA_SMB_USERNAME, KOMGA_SMB_PASSWORD)
        session.connect()

        # Connect to the share
        tree = TreeConnect(session, share_name, '?????')
        tree.connect()

        # Open the file on the SMB share
        open = Open(tree, file_path, create_disposition=CreateDisposition.FILE_OVERWRITE_IF)
        open.create()

        # Copy the file to the SMB share
        with open.file as smb_file, open(file_path, 'rb') as local_file:
            shutil.copyfileobj(local_file, smb_file)

        print(f'Successfully moved {file_path} to {smb_path}')
    except Exception as e:
        print(f'Error moving file to Komga SMB share: {e}')
        raise
    finally:
        # Clean up resources
        open.close()
        tree.disconnect()
        session.disconnect()
        connection.disconnect()

def notify_komga_of_new_comic(file_path: str) -> None:
    """Notify Komga of a new comic via its API"""
    if not KOMGA_URL or not KOMGA_API_KEY:
        raise ValueError('Komga URL and API key are required to notify Komga of new comics.')

    try:
        # Implement the API call to notify Komga of a new comic
        # This is a placeholder and should be replaced with the actual API call
        response = requests.post(
            f'{KOMGA_URL}/api/v1/library',
            headers={
                'Authorization': f'Bearer {KOMGA_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'filePath': file_path,
            },
        )
        response.raise_for_status()
        print(f'Successfully notified Komga of new comic: {file_path}')
    except requests.RequestException as e:
        print(f'Error notifying Komga of new comic: {e}')
        raise

def fetch_comics(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch comics from ComicVine API"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    try:

        response = requests.get(
            f"{COMICVINE_API_BASE}/search/",
            params={
                "api_key": API_KEY,
                "format": "json",
                "query": query,
                "resources": "issue",
                "limit": limit,
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except requests.RequestException as e:
        print(f'Error fetching comics: {e}')
        raise

def fetch_volumes(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch comic volumes from ComicVine API"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    try:
        response = requests.get(
            f'{COMICVINE_API_BASE}/search/',
            params={
                'api_key': API_KEY,
                'format': 'json',
                'query': f'"{query}"',
                'resources': 'volume',
                'limit': limit,
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except requests.RequestException as e:
        print(f'Error fetching volumes: {e}')
        raise

def fetch_comic_by_id(id: int) -> Optional[dict[str, Any]]:
    """Fetch a specific comic by ID"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    try:
        response = requests.get(
            f'{COMICVINE_API_BASE}/issue/4000-{id}/',
            params={
                'api_key': API_KEY,
                'format': 'json',
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results')
    except requests.RequestException as e:
        print(f'Error fetching comic by ID: {e}')
        raise

def fetch_volume_by_id(id: int) -> dict[str, Any] | None:
    """Fetch a specific volume by ID"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    try:
        response = requests.get(
            f'{COMICVINE_API_BASE}/volume/4000-{id}/',
            params={
                'api_key': API_KEY,
                'format': 'json',
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results')
    except requests.RequestException as e:
        print(f'Error fetching volume by ID: {e}')
        raise

def search_comics(query: str, filter_params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Search for comics with advanced filtering"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    params: dict[str, Any] = {
        'api_key': API_KEY,
        'format': 'json',
        'query': f'"{query}"',
        'resources': 'issue',
        'limit': filter_params.get('limit', 10) if filter_params else 10,
    }

    if filter_params:
        for key, value in filter_params.items():
            if key != 'limit':
                params[key] = value

    try:
        response = requests.get(
            f'{COMICVINE_API_BASE}/search/',
            params=params,
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except requests.RequestException as e:
        print(f'Error searching comics: {e}')
        raise

def get_api_key_status() -> dict[str, Any]:
    """Get the current API key status"""
    return {
        'is_valid': bool(API_KEY),
        'key': API_KEY[:5] + '...' if API_KEY else None,
    }

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

def process_comic(comic_file: str) -> None:
    """Process a comic and move it to the Komga library or notify Komga of a new comic"""
    try:
        # Extract the archive if it's a comic archive
        file_extension = comic_file.lower().split('.')[-1]
        if file_extension in ['cbz', 'cbr', 'cb7']:
            # Create a temporary directory for extraction
            temp_dir = os.path.join(os.path.dirname(comic_file), 'extracted_' + os.path.basename(comic_file))
            extract_archive(comic_file, temp_dir)

            # After extraction, we need to decide what to do with the extracted files
            # For now, we'll just print the extracted files and move the original file
            print(f'Extracted files: {os.listdir(temp_dir)}')

            # Move the original archive file to Komga
            move_to_komga(comic_file)

            # Optionally, we could also move the extracted files or handle them differently
            # For now, we'll just leave them in the temp directory
        else:
            # If it's not an archive, just process it as a regular file
            print(f'Processing non-archive comic: {comic_file}')
            move_to_komga(comic_file)
    except Exception as e:
        print(f'Error processing comic: {e}')
        raise

# Example usage
if __name__ == '__main__':
    # Check if API key is set
    status = get_api_key_status()
    print(f"API Key Status: {'Valid' if status['is_valid'] else 'Invalid'}")

    if status['is_valid']:
        try:
            # Example search for comics
            comics = fetch_comics('spider-man', 5)
            print(f'Found {len(comics)} comics')

            # Example search for volumes
            volumes = fetch_volumes('marvel', 5)
            print(f'Found {len(volumes)} volumes')

            # Process a comic (example)
            # Uncomment and modify the line below to process a real comic file
            # process_comic('/path/to/comic.cbz')

            # Example of setting environment variables for Komga
            # os.environ['KOMGA_LIBRARY_PATH'] = '/path/to/komga/library'
            # os.environ['KOMGA_URL'] = 'http://komga.local:8585'
            # os.environ['KOMGA_API_KEY'] = 'your_komga_api_key'
            # os.environ['KOMGA_SMB_PATH'] = 'smb://truenas.local/comics'
            # os.environ['KOMGA_SMB_USERNAME'] = 'your_username'
            # os.environ['KOMGA_SMB_PASSWORD'] = 'your_password'

        except (requests.RequestException, ValueError) as e:
            print(f'Error: {e}')
    else:
        print('Please set your ComicVine API key in the environment variable COMICVINE_API_KEY')