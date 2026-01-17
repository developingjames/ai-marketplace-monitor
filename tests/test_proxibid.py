"""Unit tests for Proxibid marketplace implementation."""

import time
from pathlib import Path

import pytest
from pytest_playwright.pytest_playwright import CreateContextCallback

from ai_marketplace_monitor.proxibid import (
    ProxibidDetailPage,
    ProxibidItemConfig,
    ProxibidMarketplace,
    ProxibidMarketplaceConfig,
    ProxibidSearchResultPage,
)
from ai_marketplace_monitor.listing import Listing
from ai_marketplace_monitor.utils import MonitorConfig, Translator


@pytest.fixture
def translator():
    """Create a default translator for tests."""
    return Translator(locale="English", dictionary={})


@pytest.fixture
def monitor_config():
    """Create a default monitor config for tests."""
    return MonitorConfig(name="monitor")


def test_marketplace_config_creation(monitor_config):
    """Test that ProxibidMarketplaceConfig can be created."""
    config = ProxibidMarketplaceConfig(
        name="proxibid_test",
        monitor_config=monitor_config,
        market_type="proxibid",
        enabled=True
    )
    assert config.name == "proxibid_test"
    assert config.market_type == "proxibid"


def test_item_config_creation():
    """Test that ProxibidItemConfig can be created."""
    config = ProxibidItemConfig(
        name="test_item",
        search_phrases=["equipment", "machinery"]
    )
    assert config.name == "test_item"
    assert len(config.search_phrases) == 2


def test_url_building():
    """Test URL building for Proxibid search with hash fragments."""
    marketplace = ProxibidMarketplace(
        name="proxibid",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Test start position 1
    url = marketplace._build_search_url("tractor", start=1)
    assert "proxibid.com/asp/SearchAdvanced_i.asp" in url
    assert "searchTerm=tractor" in url
    assert "#" in url, "URL should contain hash fragment"
    assert "search=tractor" in url
    assert "start=1" in url
    assert "length=100" in url

    # Test start position 101
    url2 = marketplace._build_search_url("equipment", start=101)
    assert "start=101" in url2
    assert "search=equipment" in url2


def test_search_result_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Proxibid search results page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "proxibid" / "Advanced Search Online Auctions _ Proxibid.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    search_page = ProxibidSearchResultPage(page, translator, None)
    listings = search_page.get_listings()

    assert len(listings) > 0, "Should find listings on search results page"

    # Check first listing has required fields
    first_listing = listings[0]
    assert 'id' in first_listing
    assert 'title' in first_listing
    assert 'url' in first_listing
    assert first_listing['id'], "Listing ID should not be empty"


def test_detail_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Proxibid detail page."""
    # Find detail page HTML file (should be one starting with a number)
    scraping_dir = Path(__file__).parent.parent / "Scraping" / "proxibid"
    detail_files = [f for f in scraping_dir.glob("*.html") if f.name[0].isdigit()]

    if not detail_files:
        pytest.skip("No Proxibid detail page HTML found")

    html_file = detail_files[0]
    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    detail_page = ProxibidDetailPage(page, translator, None)
    details = detail_page.get_listing_details()

    assert 'title' in details
    # Title might be empty on some pages, so just check the key exists


def test_listing_filtering():
    """Test that check_listing properly filters by keywords and antikeywords."""
    marketplace = ProxibidMarketplace(
        name="proxibid",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    item_config = ProxibidItemConfig(
        name="test_item",
        search_phrases=["equipment"],
        keywords=["Caterpillar", "John Deere"],
        antikeywords=["toy", "model"]
    )

    # Test listing that should pass
    good_listing = Listing(
        marketplace="proxibid",
        name="test_item",
        id="123456",
        title="Caterpillar Excavator",
        image="",
        price="$25000",
        post_url="http://test.com",
        location="Ohio",
        seller="Proxibid",
        condition="Used",
        description="Heavy equipment in good condition"
    )
    assert marketplace.check_listing(item_config, good_listing) is True

    # Test listing that should be excluded (has antikeyword)
    bad_listing = Listing(
        marketplace="proxibid",
        name="test_item",
        id="123457",
        title="Toy Excavator Model",
        image="",
        price="$50",
        post_url="http://test.com",
        location="Ohio",
        seller="Proxibid",
        condition="New",
        description="Miniature toy model"
    )
    assert marketplace.check_listing(item_config, bad_listing) is False


def test_get_config():
    """Test that get_config classmethod works."""
    config = ProxibidMarketplace.get_config(
        name="proxibid_test",
        market_type="proxibid",
        enabled=True,
        monitor_config=MonitorConfig(name="monitor")
    )
    assert isinstance(config, ProxibidMarketplaceConfig)
    assert config.name == "proxibid_test"
