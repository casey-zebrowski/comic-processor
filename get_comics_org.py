#!/usr/bin/env python3
"""Export unique GetComics links from every page of a yearly archive."""

from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sys
import time

import requests
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_PATH)

EXCLUDED_LINK_PREFIXES = (
    "https://getcomics.org/cat/",
    "https://getcomics.org/tag/",
    "https://getcomics.org/?s=",
)
EXCLUDED_LINKS = {
    "https://getcomics.org/",
    "https://getcomics.org/support/",
    "https://getcomics.org/sitemap/",
    "https://getcomics.org/about/",
    "https://getcomics.org/contact/",
    "https://getcomics.org/how-to-download/",
    "https://getcomics.org/find-comic/",
    "https://getcomics.org/about/privacy-policy/",
    "https://getcomics.org/dmca/",
}
PAGE_LINK_PATTERN = re.compile(r"^https://getcomics\.org/\d{4}/page/\d+/?$")
YEAR_ARCHIVE_PATTERN = re.compile(r"^https://getcomics\.org/\d{4}/?$")


class ArchivePageParser(HTMLParser):
    """Collect pagination values and GetComics links from an archive page."""

    def __init__(self) -> None:
        super().__init__()
        self._pagination_depth = 0
        self._page_number_depth = 0
        self._page_number_text: list[str] = []
        self.page_numbers: list[int] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        href = attributes.get("href")
        if tag == "a" and href and href.startswith("https://getcomics.org/"):
            self.links.append(href)

        classes = set((attributes.get("class") or "").split())
        if tag == "nav" and {"pagination", "pagination-standard"} <= classes:
            self._pagination_depth = 1
            return

        if not self._pagination_depth:
            return

        self._pagination_depth += 1
        if self._page_number_depth:
            self._page_number_depth += 1
        elif tag in {"a", "span"} and "page-numbers" in classes:
            self._page_number_depth = 1
            self._page_number_text = []

    def handle_data(self, data: str) -> None:
        if self._page_number_depth:
            self._page_number_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._pagination_depth:
            return

        if self._page_number_depth:
            self._page_number_depth -= 1
            if not self._page_number_depth:
                text = "".join(self._page_number_text).strip()
                if text.isdecimal():
                    self.page_numbers.append(int(text))
                self._page_number_text = []

        self._pagination_depth -= 1


def archive_url(year: str, page: int | None = None) -> str:
    """Return the archive URL for *year*, optionally at a specific page."""
    suffix = f"page/{page}/" if page is not None else ""
    return f"https://getcomics.org/{year}/{suffix}"


def should_export_link(link: str) -> bool:
    """Return whether a collected GetComics link belongs in the CSV export."""
    normalized_link = link.lower()
    return (
        "#comments" not in normalized_link
        and normalized_link not in EXCLUDED_LINKS
        and not normalized_link.startswith(EXCLUDED_LINK_PREFIXES)
        and not PAGE_LINK_PATTERN.fullmatch(normalized_link)
        and not YEAR_ARCHIVE_PATTERN.fullmatch(normalized_link)
    )


def read_existing_rows(output_path: Path) -> dict[str, str]:
    """Read existing export rows, retaining one status for each unique URL."""
    if not output_path.exists():
        return {}

    rows: dict[str, str] = {}
    with output_path.open(newline="", encoding="utf-8") as existing_file:
        for row_number, row in enumerate(csv.reader(existing_file)):
            if not row:
                continue
            url = row[0].strip()
            if row_number == 0 and url.lower() == "url":
                continue
            if not url:
                continue
            downloaded = row[1].strip() if len(row) > 1 else ""
            if url not in rows or downloaded == "X":
                rows[url] = downloaded
    return rows


def fetch_page(
    session: requests.Session, url: str, timeout: float, retry_count: int, delay_seconds: float
) -> ArchivePageParser:
    """Fetch and parse one archive page, retrying transient request failures."""
    for attempt in range(retry_count + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            parser = ArchivePageParser()
            parser.feed(response.text)
            parser.close()
            return parser
        except requests.RequestException:
            if attempt == retry_count:
                raise
            print(
                f"Request failed; retrying ({attempt + 1} of {retry_count}): {url}",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)

    raise RuntimeError("unreachable")


def get_max_page(
    session: requests.Session, year: str, timeout: float, retry_count: int, delay_seconds: float
) -> int:
    """Return the highest pagination entry shown for *year*."""
    url = archive_url(year)
    page = fetch_page(session, url, timeout, retry_count, delay_seconds)
    if not page.page_numbers:
        raise LookupError(f"no pagination entries found at {url}")
    return max(page.page_numbers)


def export_links(
    year: str,
    output_directory: Path,
    timeout: float,
    delay_seconds: float,
    retry_count: int,
) -> tuple[Path, int]:
    """Fetch every annual archive page and write its unique GetComics links to CSV."""
    if len(year) != 4 or not year.isdecimal():
        raise ValueError("year must be exactly four digits (for example, 2025)")
    if delay_seconds < 0:
        raise ValueError("delay must be zero or greater")
    if retry_count < 0:
        raise ValueError("retry count must be zero or greater")

    with requests.Session() as session:
        session.headers.update({"User-Agent": "comic-processor get_comics_org.py"})
        max_page = get_max_page(session, year, timeout, retry_count, delay_seconds)
        links: dict[str, None] = {}
        for page_number in range(1, max_page + 1):
            time.sleep(delay_seconds)
            url = archive_url(year, page_number)
            print(f"Fetching page {page_number} of {max_page}: {url}", file=sys.stderr)
            for link in fetch_page(session, url, timeout, retry_count, delay_seconds).links:
                if should_export_link(link):
                    links.setdefault(link, None)

    output_path = output_directory / f"get-comics-org_{year}.csv"
    output_directory.mkdir(parents=True, exist_ok=True)
    rows = read_existing_rows(output_path)
    for link in links:
        rows.setdefault(link, "")

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["url", "downloaded"])
        writer.writerows((link, rows[link]) for link in sorted(rows))
    return output_path, len(rows)


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        description="Export unique GetComics links from every page of a yearly archive."
    )
    argument_parser.add_argument("year", help="four-digit archive year, such as 2025")
    argument_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "get_comics_org",
        help="directory for the CSV (default: ../get_comics_org)",
    )
    argument_parser.add_argument(
        "--timeout", type=float, default=30.0, help="HTTP timeout in seconds (default: 30)"
    )
    argument_parser.add_argument(
        "--delay",
        type=float,
        default=float(os.getenv("GET_COMICS_ORG_DELAY_SECONDS", "1")),
        help="seconds to wait between page requests (default: GET_COMICS_ORG_DELAY_SECONDS)",
    )
    argument_parser.add_argument(
        "--retries",
        type=int,
        default=int(os.getenv("GET_COMICS_ORG_RETRY_COUNT", "3")),
        help="number of retries after a failed request (default: GET_COMICS_ORG_RETRY_COUNT)",
    )
    arguments = argument_parser.parse_args()

    try:
        output_path, link_count = export_links(
            arguments.year,
            arguments.output_dir,
            arguments.timeout,
            arguments.delay,
            arguments.retries,
        )
    except (requests.RequestException, ValueError, LookupError, OSError) as error:
        argument_parser.error(str(error))
    print(f"Wrote {link_count} unique links to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
