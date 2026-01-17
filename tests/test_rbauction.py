"""Unit tests for RB Auction marketplace implementation."""

import time
from pathlib import Path

import pytest
from pytest_playwright.pytest_playwright import CreateContextCallback

from ai_marketplace_monitor.rbauction import (
    RBAuctionDetailPage,
    RBAuctionItemConfig,
    RBAuctionMarketplace,
    RBAuctionMarketplaceConfig,
    RBAuctionSearchResultPage,
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
    """Test that RBAuctionMarketplaceConfig can be created with region support."""
    config = RBAuctionMarketplaceConfig(
        name="rbauction_test",
        monitor_config=monitor_config,
        market_type="rbauction",
        enabled=True,
        region="USA"
    )
    assert config.name == "rbauction_test"
    assert config.market_type == "rbauction"
    assert config.region == "USA"


def test_item_config_with_region():
    """Test that RBAuctionItemConfig can be created with region parameter."""
    config = RBAuctionItemConfig(
        name="test_item",
        search_phrases=["dozer", "excavator"],
        region="USA"
    )
    assert config.name == "test_item"
    assert config.region == "USA"


def test_url_building():
    """Test URL building for RB Auction search with offset-based pagination."""
    marketplace = RBAuctionMarketplace(
        name="rbauction",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Test offset 0 with region
    url = marketplace._build_search_url("dozer", offset=0, region="USA")
    assert "rbauction.com/search" in url
    assert "freeText=dozer" in url
    assert "size=120" in url
    assert "from=0" in url
    assert "rbaLocationLevelTwo=USA" in url

    # Test offset 120 (second page)
    url2 = marketplace._build_search_url("excavator", offset=120, region="USA")
    assert "from=120" in url2
    assert "freeText=excavator" in url2

    # Test without region
    url3 = marketplace._build_search_url("crane", offset=0)
    assert "rbauction.com/search" in url3
    assert "rbaLocationLevelTwo" not in url3


def test_search_result_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of RB Auction search results page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "rbauction" / "New and used equipment.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    search_page = RBAuctionSearchResultPage(page, translator, None)
    listings = search_page.get_listings()

    assert len(listings) > 0, "Should find listings on search results page"

    # Check first listing has required fields
    first_listing = listings[0]
    assert 'id' in first_listing
    assert 'title' in first_listing
    assert 'url' in first_listing
    assert first_listing['id'], "Listing ID should not be empty"


def test_detail_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of RB Auction detail page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "rbauction" / "2005 Liebherr PR734 LGP Crawler Dozer...html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    detail_page = RBAuctionDetailPage(page, translator, None)
    details = detail_page.get_listing_details()

    assert 'title' in details
    assert details['title'], "Title should not be empty"


def test_listing_filtering():
    """Test that check_listing properly filters by keywords and antikeywords."""
    marketplace = RBAuctionMarketplace(
        name="rbauction",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    item_config = RBAuctionItemConfig(
        name="test_item",
        search_phrases=["equipment"],
        keywords=["Liebherr", "dozer"],
        antikeywords=["parts", "manual"]
    )

    # Test listing that should pass
    good_listing = Listing(
        marketplace="rbauction",
        name="test_item",
        id="12345",
        title="Liebherr PR734 Dozer",
        image="",
        price="$125000",
        post_url="http://test.com",
        location="USA",
        seller="RB Auction",
        condition="Used",
        description="2005 Liebherr crawler dozer in working condition"
    )
    assert marketplace.check_listing(item_config, good_listing) is True

    # Test listing that should be excluded (has antikeyword)
    bad_listing = Listing(
        marketplace="rbauction",
        name="test_item",
        id="12346",
        title="Dozer Parts Manual",
        image="",
        price="$50",
        post_url="http://test.com",
        location="USA",
        seller="RB Auction",
        condition="New",
        description="Service manual and parts catalog"
    )
    assert marketplace.check_listing(item_config, bad_listing) is False


def test_get_config():
    """Test that get_config classmethod works."""
    config = RBAuctionMarketplace.get_config(
        name="rbauction_test",
        market_type="rbauction",
        enabled=True,
        monitor_config=MonitorConfig(name="monitor"),
        region="USA"
    )
    assert isinstance(config, RBAuctionMarketplaceConfig)
    assert config.region == "USA"
