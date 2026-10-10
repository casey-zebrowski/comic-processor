import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

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

def process_comic(comic_file: str) -> None:
    """Process a comic and move it to the Komga library or notify Komga of a new comic"""
    try:
        # Placeholder for comic processing logic
        print(f'Processing comic: {comic_file}')

        # Move the processed comic to the Komga library or notify Komga of a new comic
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