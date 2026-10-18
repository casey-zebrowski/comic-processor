#!/usr/bin/env python3

import logging
import os
import re
import shutil
import uuid
import zipfile  # Added for .cbz (ZIP) files
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import py7zr  # Added for .cb7 (7zip) files
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
from unrar.cffi import rarfile as unrar_rarfile  # type: ignore

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

_configured_log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
_log_level = getattr(logging, _configured_log_level, logging.INFO)
if not isinstance(_log_level, int):
    _log_level = logging.INFO
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
_comicvine_call_capture: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "comicvine_call_capture", default=None
)


@contextmanager
def capture_comicvine_calls():
    """Capture full ComicVine JSON responses for a DEBUG diagnostic dump."""
    calls: list[dict[str, Any]] = []
    if not logger.isEnabledFor(logging.DEBUG):
        yield calls
        return

    token = _comicvine_call_capture.set(calls)
    try:
        yield calls
    finally:
        _comicvine_call_capture.reset(token)


def _record_comicvine_response(response, data: Any) -> None:
    calls = _comicvine_call_capture.get()
    if calls is None:
        return

    parsed_url = urlsplit(response.url)
    safe_params = {
        key: value
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if key.casefold() not in {"api_key", "key"}
    }
    calls.append(
        {
            "method": response.request.method,
            "endpoint": parsed_url.path,
            "params": safe_params,
            "status_code": response.status_code,
            "response": data,
        }
    )

# Read configuration
api_key = os.getenv("API_KEY")

# ComicVine API configuration
COMICVINE_API_BASE = "https://comicvine.gamespot.com/api"
API_KEY = os.getenv("COMICVINE_API_KEY") or os.getenv("VITE_COMICVINE_API_KEY")
COMICVINE_HEADERS = {
    "User-Agent": "ComicProcessor/1.0 (personal comic library)",
    "Accept": "application/json",
}


def _safe_comicvine_error(error):
    """Remove API credentials from request exceptions before logging them."""
    message = re.sub(
        r"([?&](?:api_key|key)=)[^&\s]+", r"\1[REDACTED]", str(error), flags=re.IGNORECASE
    )
    if API_KEY:
        message = message.replace(API_KEY, "[REDACTED]")
    return message

# Komga configuration
KOMGA_LIBRARY_PATH = os.getenv("KOMGA_LIBRARY_PATH")
KOMGA_URL = os.getenv("KOMGA_URL")
KOMGA_API_KEY = os.getenv("KOMGA_API_KEY")
KOMGA_SMB_PATH = os.getenv("KOMGA_SMB_PATH")
KOMGA_SMB_USERNAME = os.getenv("KOMGA_SMB_USERNAME")
KOMGA_SMB_PASSWORD = os.getenv("KOMGA_SMB_PASSWORD")

if not API_KEY:
    logger.warning(
        "ComicVine API key not found. Set COMICVINE_API_KEY to enable ComicVine requests."
    )

if not KOMGA_LIBRARY_PATH and not KOMGA_URL and not KOMGA_SMB_PATH:
    logger.warning(
        "No Komga destination is configured; set a Komga path or URL to use Komga integration."
    )


def move_to_komga(file_path: str) -> None:
    """Move a comic file to the Komga library directory or notify Komga of a new comic"""
    if KOMGA_LIBRARY_PATH:
        try:
            shutil.move(file_path, KOMGA_LIBRARY_PATH)
            logger.info(f"Moved {file_path} to Komga library.")
        except Exception as e:
            logger.error(f"Error moving file to Komga library: {e}")
            raise
    elif KOMGA_SMB_PATH:
        try:
            move_to_komga_smb(file_path, KOMGA_SMB_PATH)
            logger.info(f"Moved {file_path} to Komga SMB share.")
        except Exception as e:
            logger.error(f"Error moving file to Komga SMB share: {e}")
            raise
    elif KOMGA_URL and KOMGA_API_KEY:
        try:
            notify_komga_of_new_comic(file_path)
            logger.info(f"Notified Komga of new comic: {file_path}")
        except Exception as e:
            logger.error(f"Error notifying Komga of new comic: {e}")
            raise
    else:
        raise ValueError(
            "Komga configuration is required. Please set KOMGA_LIBRARY_PATH, KOMGA_URL and KOMGA_API_KEY, or KOMGA_SMB_PATH environment variables."
        )


def move_to_komga_smb(file_path: str, smb_path: str) -> None:
    """Move a comic file to the Komga SMB share"""
    if not KOMGA_SMB_USERNAME or not KOMGA_SMB_PASSWORD:
        raise ValueError(
            "Komga SMB username and password are required to access the SMB share."
        )

    try:
        # Parse the SMB path
        smb_url = smb_path.replace("smb://", "")
        server_name, share_name = smb_url.split("/", 1)

        # Connect to the SMB server
        connection = Connection(uuid.uuid4(), server_name, 445)
        connection.connect()

        # Create a session
        session = Session(connection, KOMGA_SMB_USERNAME, KOMGA_SMB_PASSWORD)
        session.connect()

        # Connect to the share
        tree = TreeConnect(session, share_name, "?????")
        tree.connect()

        # Open the file on the SMB share
        open = Open(
            tree, file_path, create_disposition=CreateDisposition.FILE_OVERWRITE_IF
        )
        open.create()

        # Copy the file to the SMB share
        with open.file as smb_file, open(file_path, "rb") as local_file:
            shutil.copyfileobj(local_file, smb_file)

        logger.info(f"Successfully moved {file_path} to {smb_path}")
    except Exception as e:
        logger.error(f"Error moving file to Komga SMB share: {e}")
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
        raise ValueError(
            "Komga URL and API key are required to notify Komga of new comics."
        )

    try:
        # Implement the API call to notify Komga of a new comic
        # This is a placeholder and should be replaced with the actual API call
        response = requests.post(
            f"{KOMGA_URL}/api/v1/library",
            headers={
                "Authorization": f"Bearer {KOMGA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "filePath": file_path,
            },
        )
        response.raise_for_status()
        logger.info(f"Successfully notified Komga of new comic: {file_path}")
    except requests.RequestException as e:
        logger.error(f"Error notifying Komga of new comic: {_safe_comicvine_error(e)}")
        raise


def fetch_comics(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch comics from ComicVine API"""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

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
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        if data.get("status_code") not in (None, 1):
            raise RuntimeError(
                "ComicVine search failed with API status "
                f"{data.get('status_code')}: {data.get('error', 'Unknown API error')}"
            )
        return data.get("results", [])
    except requests.RequestException as e:
        logger.error(f"Error fetching comics: {_safe_comicvine_error(e)}")
        raise


def fetch_volumes(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch comic volumes from ComicVine API"""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

    try:
        response = requests.get(
            f"{COMICVINE_API_BASE}/search/",
            params={
                "api_key": API_KEY,
                "format": "json",
                "query": f'"{query}"',
                "resources": "volume",
                "limit": limit,
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        if data.get("status_code") not in (None, 1):
            raise RuntimeError(
                "ComicVine volume search failed with API status "
                f"{data.get('status_code')}: {data.get('error', 'Unknown API error')}"
            )
        return data.get("results", [])
    except requests.RequestException as e:
        logger.error(f"Error fetching volumes: {_safe_comicvine_error(e)}")
        raise


def fetch_comic_by_id(id: int) -> dict[str, Any] | None:
    """Fetch a specific comic by ID"""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

    try:
        response = requests.get(
            f"{COMICVINE_API_BASE}/issue/4000-{id}/",
            params={
                "api_key": API_KEY,
                "format": "json",
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        return data.get("results")
    except requests.RequestException as e:
        logger.error(f"Error fetching comic by ID: {_safe_comicvine_error(e)}")
        raise


def fetch_volume_by_id(id: int) -> dict[str, Any] | None:
    """Fetch a specific volume by ID"""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

    try:
        response = requests.get(
            f"{COMICVINE_API_BASE}/volume/4050-{id}/",
            params={
                "api_key": API_KEY,
                "format": "json",
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        return data.get("results")
    except requests.RequestException as e:
        logger.error(f"Error fetching volume by ID: {_safe_comicvine_error(e)}")
        raise


def fetch_issues_by_volume_and_number(
    volume_id: int, issue_number: str
) -> list[dict[str, Any]]:
    """Fetch issue records matching a ComicVine volume and issue number."""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

    try:
        response = requests.get(
            f"{COMICVINE_API_BASE}/issues/",
            params={
                "api_key": API_KEY,
                "format": "json",
                "filter": f"volume:{volume_id},issue_number:{issue_number}",
                "field_list": "id,issue_number,volume",
                "limit": 100,
            },
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        return data.get("results", [])
    except requests.RequestException as e:
        logger.error(
            f"Error fetching issue {issue_number} for volume {volume_id}: "
            f"{_safe_comicvine_error(e)}"
        )
        raise


def search_comics(
    query: str, filter_params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Search for comics with advanced filtering"""
    if not API_KEY:
        raise ValueError(
            "ComicVine API key is required. Please set COMICVINE_API_KEY environment variable."
        )

    params: dict[str, Any] = {
        "api_key": API_KEY,
        "format": "json",
        "query": f'"{query}"',
        "resources": "issue",
        "limit": filter_params.get("limit", 10) if filter_params else 10,
    }

    if filter_params:
        for key, value in filter_params.items():
            if key != "limit":
                params[key] = value

    try:
        response = requests.get(
            f"{COMICVINE_API_BASE}/search/",
            params=params,
            headers=COMICVINE_HEADERS,
            timeout=30,
        )
        data = response.json()
        _record_comicvine_response(response, data)
        response.raise_for_status()
        return data.get("results", [])
    except requests.RequestException as e:
        logger.error(f"Error searching comics: {_safe_comicvine_error(e)}")
        raise


def get_api_key_status() -> dict[str, Any]:
    """Get the current API key status"""
    return {
        "is_valid": bool(API_KEY),
        "key": API_KEY[:5] + "..." if API_KEY else None,
    }


def extract_archive(comic_file: str, output_dir: str) -> None:
    """Extract and flatten comic archive (.cbr, .cbz, .cb7)"""
    try:
        logger.info(f"Extracting archive: {comic_file}")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Determine file extension and extract accordingly
        file_extension = comic_file.lower().split(".")[-1]

        if file_extension == "cbz":
            # Handle ZIP archive (.cbz)
            try:
                with zipfile.ZipFile(comic_file, "r") as zip_ref:
                    zip_ref.extractall(output_dir)
                    logger.info(f"Successfully extracted ZIP archive: {comic_file}")
                return
            except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
                logger.error(f"Error extracting ZIP archive: {e}")
        elif file_extension == "cbr":
            # Use the pip-installed UnRAR binding rather than relying on an
            # OS-specific executable such as unrar, unar, or bsdtar.
            os.makedirs(output_dir, exist_ok=True)
            destination_root = os.path.abspath(output_dir)
            rar_ref = unrar_rarfile.RarFile(comic_file)
            for member in rar_ref.infolist():
                archive_name = member.filename.replace("\\", "/")
                if archive_name.startswith("/") or os.path.splitdrive(archive_name)[0]:
                    raise ValueError(f"Unsafe path in RAR archive: {member.filename}")
                destination = os.path.abspath(
                    os.path.join(destination_root, *archive_name.split("/"))
                )
                if (
                    os.path.commonpath((destination_root, destination))
                    != destination_root
                ):
                    raise ValueError(f"Unsafe path in RAR archive: {member.filename}")
                if member.is_dir() or archive_name.endswith("/"):
                    os.makedirs(destination, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                with rar_ref.open(member) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)
            logger.info(f"Successfully extracted RAR archive: {comic_file}")
            return
        elif file_extension == "cb7":
            # Handle 7zip archive (.cb7)
            try:
                with py7zr.SevenZipFile(comic_file, mode="r") as sz_ref:
                    sz_ref.extractall(path=output_dir)
                    logger.info(f"Successfully extracted 7zip archive: {comic_file}")
                return
            except py7zr.Bad7zFile as e:
                logger.error(f"Error extracting 7zip archive: {e}")
                # Try alternative extraction method
                try:
                    logger.info(
                        f"Attempting alternative extraction for 7zip file: {comic_file}"
                    )
                    # Use subprocess to call 7z command if available
                    import subprocess

                    subprocess.run(
                        ["7z", "x", comic_file, f"-o{output_dir}"],
                        check=True,
                        capture_output=True,
                    )
                    logger.info(
                        f"Successfully extracted 7zip archive using alternative method: {comic_file}"
                    )
                except (subprocess.CalledProcessError, FileNotFoundError) as alt_e:
                    logger.warning(f"Alternative extraction failed: {alt_e}")
        else:
            raise ValueError(f"Unsupported archive format: {file_extension}")

        # If we get here, extraction failed
        raise ValueError(f"Failed to extract {file_extension} archive: {comic_file}")

    except Exception as e:
        logger.error(f"Error extracting archive: {e}")
        raise


def process_comic(comic_file: str) -> None:
    """Process a comic and move it to the Komga library or notify Komga of a new comic"""
    try:
        # Extract the archive if it's a comic archive
        file_extension = comic_file.lower().split(".")[-1]
        if file_extension in ["cbz", "cbr", "cb7"]:
            # Create a temporary directory for extraction
            temp_dir = os.path.join(
                os.path.dirname(comic_file), "extracted_" + os.path.basename(comic_file)
            )
            extract_archive(comic_file, temp_dir)

            # After extraction, we need to decide what to do with the extracted files
            # For now, we'll just print the extracted files and move the original file
            logger.info(f"Extracted files: {os.listdir(temp_dir)}")

            # Move the original archive file to Komga
            move_to_komga(comic_file)

            # Optionally, we could also move the extracted files or handle them differently
            # For now, we'll just leave them in the temp directory
        else:
            # If it's not an archive, just process it as a regular file
            logger.info(f"Processing non-archive comic: {comic_file}")
            move_to_komga(comic_file)
    except Exception as e:
        logger.error(f"Error processing comic: {e}")
        raise


# Example usage
if __name__ == "__main__":
    # Check if API key is set
    status = get_api_key_status()
    logger.info(f"API Key Status: {'Valid' if status['is_valid'] else 'Invalid'}")

    if status["is_valid"]:
        try:
            # Example search for comics
            comics = fetch_comics("spider-man", 5)
            logger.info(f'Found {len(comics)} comics matching "spider-man"')

            # Example search for volumes
            volumes = fetch_volumes("marvel", 5)
            logger.info(f'Found {len(volumes)} volumes matching "marvel"')

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
            logger.error(f"Error: {e}")
    else:
        logger.info(
            "Please set your ComicVine API key in the environment variable COMICVINE_API_KEY"
        )
