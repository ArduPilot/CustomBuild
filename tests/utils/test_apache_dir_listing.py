"""
Tests for Apache directory listing parser.
"""
from datetime import datetime, timezone
from pathlib import Path

from utils.apache_dir_listing import parse_apache_dir_listing, _parse_apache_date


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_LISTING_HTML = (FIXTURES_DIR / "apache_dir_listing_sample.html").read_text()
BASE_URL = "https://firmware.ardupilot.org/Copter/stable-4.5.0/CubeOrange/"


class TestParseApacheDate:
    def test_parses_single_digit_day(self):
        result = _parse_apache_date("Tue Apr  2 05:11:12 2024")
        assert result == datetime(2024, 4, 2, 5, 11, 12, tzinfo=timezone.utc)

    def test_parses_double_digit_day(self):
        result = _parse_apache_date("Tue Apr 15 05:11:12 2024")
        assert result == datetime(2024, 4, 15, 5, 11, 12, tzinfo=timezone.utc)

    def test_returns_none_for_dash(self):
        assert _parse_apache_date("--") is None

    def test_returns_none_for_invalid(self):
        assert _parse_apache_date("not a date") is None


class TestParseApacheDirListing:
    def test_parses_files_and_skips_parent_directory(self):
        entries = parse_apache_dir_listing(SAMPLE_LISTING_HTML, BASE_URL)

        assert len(entries) == 3
        assert entries[0]["name"] == "arducopter.abin"
        assert entries[1]["name"] == "arducopter.apj"
        assert entries[2]["name"] == "features.txt"

    def test_resolves_absolute_urls(self):
        entries = parse_apache_dir_listing(SAMPLE_LISTING_HTML, BASE_URL)

        assert entries[0]["url"] == (
            "https://firmware.ardupilot.org/Copter/stable-4.5.0/"
            "CubeOrange/arducopter.abin"
        )

    def test_parses_size_and_modified(self):
        entries = parse_apache_dir_listing(SAMPLE_LISTING_HTML, BASE_URL)

        assert entries[0]["size"] == 1814971
        assert entries[0]["modified"] == datetime(
            2024, 4, 2, 5, 11, 12, tzinfo=timezone.utc
        )
        assert entries[1]["modified"] == datetime(
            2024, 4, 15, 5, 11, 12, tzinfo=timezone.utc
        )

    def test_returns_empty_list_when_no_table(self):
        assert parse_apache_dir_listing("<html><body></body></html>", BASE_URL) == []
