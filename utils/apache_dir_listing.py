"""
Parse Apache HTML directory listings.
"""
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def _parse_apache_date(raw: str) -> Optional[datetime]:
    """
    Parse an Apache directory listing date string into UTC datetime.

    Example input: "Tue Apr  2 05:11:12 2024"
    """
    raw = raw.strip()
    if not raw or raw == "--":
        return None

    try:
        parsed = datetime.strptime(raw, "%a %b %d %H:%M:%S %Y")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_size(raw: str) -> Optional[int]:
    raw = raw.strip()
    if not raw or raw == "--":
        return None

    try:
        return int(raw)
    except ValueError:
        return None


def _is_parent_directory_row(link_text: str, icon_src: Optional[str]) -> bool:
    if icon_src and "back.gif" in icon_src:
        return True
    return "parent directory" in link_text.lower()


def parse_apache_dir_listing(html: str, base_url: str) -> list[dict]:
    """
    Parse an Apache HTML directory listing into file entries.

    Parameters:
        html: Raw HTML from the directory listing page.
        base_url: Base URL of the listing (used to resolve relative links).

    Returns:
        List of dicts with keys: name, url, size, modified.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    entries = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        link = cells[1].find("a")
        if not link:
            continue

        name = link.get_text(strip=True)
        href = link.get("href")
        if not href or not name:
            continue

        icon = cells[0].find("img")
        icon_src = icon.get("src") if icon else None
        if _is_parent_directory_row(name, icon_src):
            continue

        entries.append({
            "name": name,
            "url": urljoin(base_url, href),
            "modified": _parse_apache_date(cells[2].get_text()),
            "size": _parse_size(cells[3].get_text()),
        })

    return entries
