"""Unit tests for Auction Ohio marketplace implementation."""

import time
from pathlib import Path

import pytest
from pytest_playwright.pytest_playwright import CreateContextCallback

from ai_marketplace_monitor.auctionohio import (
    AuctionOhioDetailPage,
    AuctionOhioItemConfig,
    AuctionOhioMarketplace,
    AuctionOhioMarketplaceConfig,
    AuctionOhioSearchResultPage,
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
    """Test that AuctionOhioMarketplaceConfig can be created."""
    config = AuctionOhioMarketplaceConfig(
        name="auctionohio_test",
        monitor_config=monitor_config,
        market_type="auctionohio",
        enabled=True
    )
    assert config.name == "auctionohio_test"
    assert config.market_type == "auctionohio"
    assert config.enabled is True


def test_item_config_creation():
    """Test that AuctionOhioItemConfig can be created."""
    config = AuctionOhioItemConfig(
        name="test_item",
        search_phrases=["tractor", "equipment"],
        keywords="tractor OR equipment",
        antikeywords="toy model",
        min_price=1000,
        max_price=50000
    )
    assert config.name == "test_item"
    assert len(config.search_phrases) == 2
    assert config.keywords == "tractor OR equipment"


def test_url_building():
    """Test URL building for Auction Ohio search."""
    marketplace = AuctionOhioMarketplace(
        name="auctionohio",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Test page 1
    url = marketplace._build_search_url("tractor", page=1)
    assert "auctionohio.com/search" in url
    assert "page=1" in url
    assert "pageSize=125" in url
    assert "search=tractor" in url
    assert "filter=(auction_type:online;auction_lot_status:100)" in url

    # Test page 2
    url2 = marketplace._build_search_url("equipment", page=2)
    assert "page=2" in url2
    assert "search=equipment" in url2


def test_search_result_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Auction Ohio search results page."""
    # Use the HTML file from the Scraping folder
    html_file = Path(__file__).parent.parent / "Scraping" / "auctionohio" / "Search Results - Auction Ohio.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)  # Brief wait for any delayed content

    search_page = AuctionOhioSearchResultPage(page, translator, None)
    listings = search_page.get_listings()

    assert len(listings) > 0, "Should find listings on search results page"

    # Check first listing has required fields
    first_listing = listings[0]
    assert 'id' in first_listing
    assert 'title' in first_listing
    assert 'url' in first_listing
    assert first_listing['id'], "Listing ID should not be empty"
    assert first_listing['url'], "Listing URL should not be empty"


def test_detail_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of Auction Ohio detail page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "auctionohio" / "Pyrex - Early American designs - Auction Ohio.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    detail_page = AuctionOhioDetailPage(page, translator, None)
    details = detail_page.get_listing_details()

    assert 'title' in details
    assert details['title'], "Title should not be empty"
    # Description may or may not be present depending on the listing


def test_listing_filtering():
    """Test that check_listing properly filters by keywords and antikeywords."""
    marketplace = AuctionOhioMarketplace(
        name="auctionohio",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Create test item config
    item_config = AuctionOhioItemConfig(
        name="test_item",
        search_phrases=["tractor"],
        keywords="Kubota OR 'John Deere'",
        antikeywords="toy model miniature"
    )

    # Test listing that should pass (has keyword, no antikeyword)
    good_listing = Listing(
        marketplace="auctionohio",
        name="test_item",
        id="123",
        title="Kubota L3901 Tractor",
        image="",
        price="$15000",
        post_url="http://test.com",
        location="Ohio",
        seller="Auction Ohio",
        condition="Used",
        description="Nice tractor in good condition"
    )
    assert marketplace.check_listing(item_config, good_listing) is True

    # Test listing that should be excluded (has antikeyword)
    bad_listing = Listing(
        marketplace="auctionohio",
        name="test_item",
        id="124",
        title="Toy Tractor Model",
        image="",
        price="$50",
        post_url="http://test.com",
        location="Ohio",
        seller="Auction Ohio",
        condition="New",
        description="Miniature toy tractor"
    )
    assert marketplace.check_listing(item_config, bad_listing) is False

    # Test listing that should be excluded (no keyword match)
    no_keyword_listing = Listing(
        marketplace="auctionohio",
        name="test_item",
        id="125",
        title="Forklift Equipment",
        image="",
        price="$5000",
        post_url="http://test.com",
        location="Ohio",
        seller="Auction Ohio",
        condition="Used",
        description="Industrial forklift"
    )
    assert marketplace.check_listing(item_config, no_keyword_listing) is False


def test_get_config():
    """Test that get_config classmethod works."""
    config = AuctionOhioMarketplace.get_config(
        name="auctionohio_test",
        market_type="auctionohio",
        enabled=True,
        monitor_config=MonitorConfig(name="monitor")
    )
    assert isinstance(config, AuctionOhioMarketplaceConfig)
    assert config.name == "auctionohio_test"


def test_get_item_config():
    """Test that get_item_config classmethod works."""
    item_config = AuctionOhioMarketplace.get_item_config(
        name="test_item",
        search_phrases=["tractor"],
        keywords="tractor",
        extra_field="should_be_filtered"
    )
    assert isinstance(item_config, AuctionOhioItemConfig)
    assert item_config.name == "test_item"
    assert not hasattr(item_config, 'extra_field'), "Extra fields should be filtered out"
