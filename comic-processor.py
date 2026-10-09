import os
from typing import Any, Optional

import requests  # type: ignore[import-not-found, import-untyped]  # pyright: ignore[reportMissingModuleSource]

# ComicVine API configuration
COMICVINE_API_BASE = 'https://comicvine.gamespot.com/api'
API_KEY = os.getenv('COMICVINE_API_KEY') or os.getenv('VITE_COMICVINE_API_KEY')

if not API_KEY:
    print('Warning: ComicVine API key not found. Please set COMICVINE_API_KEY environment variable.')


def fetch_comics(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch comics from ComicVine API"""
    if not API_KEY:
        raise ValueError('ComicVine API key is required. Please set COMICVINE_API_KEY environment variable.')

    try:
        response = requests.get(
            f'{COMICVINE_API_BASE}/search/',
            params={
                'api_key': API_KEY,
                'format': 'json',
                'query': f'"{query}"',
                'resources': 'issue',
                'limit': limit,
            },
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
        )
        response.raise_for_status()
        data = response.json()
        return data.get('results')
    except requests.RequestException as e:
        print(f'Error fetching comic by ID: {e}')
        raise


def fetch_volume_by_id(id: int) -> Optional[dict[str, Any]]:
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

        except Exception as e:
            print(f'Error: {e}')
    else:
        print('Please set your ComicVine API key in the environment variable COMICVINE_API_KEY')
