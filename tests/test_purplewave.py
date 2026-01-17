"""Unit tests for Purple Wave marketplace implementation."""

import time
from pathlib import Path

import pytest
from pytest_playwright.pytest_playwright import CreateContextCallback

from ai_marketplace_monitor.purplewave import (
    PurpleWaveDetailPage,
    PurpleWaveItemConfig,
    PurpleWaveMarketplace,
    PurpleWaveMarketplaceConfig,
    PurpleWaveSearchResultPage,
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
    """Test that PurpleWaveMarketplaceConfig can be created with location support."""
    config = PurpleWaveMarketplaceConfig(
        name="purplewave_test",
        monitor_config=monitor_config,
        market_type="purplewave",
        enabled=True,
        zipcode="66062",
        miles=300
    )
    assert config.name == "purplewave_test"
    assert config.market_type == "purplewave"
    assert config.zipcode == "66062"
    assert config.miles == 300


def test_item_config_with_location():
    """Test that PurpleWaveItemConfig can be created with location parameters."""
    config = PurpleWaveItemConfig(
        name="test_item",
        search_phrases=["excavator", "loader"],
        zipcode="66062",
        miles=250
    )
    assert config.name == "test_item"
    assert config.zipcode == "66062"
    assert config.miles == 250


def test_url_building():
    """Test URL building for Purple Wave search."""
    marketplace = PurpleWaveMarketplace(
        name="purplewave",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Test page 1 with location
    url = marketplace._build_search_url("excavator", page=1, zipcode="66062", miles=250)
    assert "purplewave.com/search" in url
    assert "q=excavator" in url
    assert "zipCode=66062" in url
    assert "radius=250" in url
    assert "page=1" in url
    assert "perPage=100" in url

    # Test page 2
    url2 = marketplace._build_search_url("loader", page=2, zipcode="66062", miles=250)
    assert "page=2" in url2

    # Test without location
    url3 = marketplace._build_search_url("tractor", page=1)
    assert "purplewave.com/search" in url3
    assert "zipCode" not in url3


def test_search_result_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Purple Wave search results page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "purplewave" / "Search our current inventory _ Purple Wave.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    search_page = PurpleWaveSearchResultPage(page, translator, None)
    listings = search_page.get_listings()

    assert len(listings) > 0, "Should find listings on search results page"

    # Check first listing has required fields
    first_listing = listings[0]
    assert 'id' in first_listing
    assert 'title' in first_listing
    assert 'url' in first_listing
    assert first_listing['id'], "Listing ID should not be empty"


def test_detail_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Purple Wave detail page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "purplewave" / "2015 Bobcat E33 mini excavator...Purple Wave.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    detail_page = PurpleWaveDetailPage(page, translator, None)
    details = detail_page.get_listing_details()

    assert 'title' in details
    assert details['title'], "Title should not be empty"


def test_listing_filtering():
    """Test that check_listing properly filters by keywords and antikeywords."""
    marketplace = PurpleWaveMarketplace(
        name="purplewave",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    item_config = PurpleWaveItemConfig(
        name="test_item",
        search_phrases=["equipment"],
        keywords=["Bobcat", "excavator"],
        antikeywords=["attachment", "bucket"]
    )

    # Test listing that should pass
    good_listing = Listing(
        marketplace="purplewave",
        name="test_item",
        id="12345-67890",
        title="Bobcat E33 Excavator",
        image="",
        price="$25000",
        post_url="http://test.com",
        location="Kansas, USA",
        seller="Purple Wave",
        condition="Used",
        description="2015 Bobcat excavator in excellent condition"
    )
    assert marketplace.check_listing(item_config, good_listing) is True

    # Test listing that should be excluded (has antikeyword)
    bad_listing = Listing(
        marketplace="purplewave",
        name="test_item",
        id="12345-67891",
        title="Bucket Attachment Only",
        image="",
        price="$500",
        post_url="http://test.com",
        location="Kansas, USA",
        seller="Purple Wave",
        condition="Used",
        description="Bucket attachment for excavator"
    )
    assert marketplace.check_listing(item_config, bad_listing) is False


def test_get_config():
    """Test that get_config classmethod works."""
    config = PurpleWaveMarketplace.get_config(
        name="purplewave_test",
        market_type="purplewave",
        enabled=True,
        monitor_config=MonitorConfig(name="monitor"),
        zipcode="66062",
        miles=300
    )
    assert isinstance(config, PurpleWaveMarketplaceConfig)
    assert config.zipcode == "66062"
    assert config.miles == 300
