"""Unit tests for GovDeals marketplace implementation."""

import time
from pathlib import Path

import pytest
from pytest_playwright.pytest_playwright import CreateContextCallback

from ai_marketplace_monitor.govdeals import (
    GovDealsDetailPage,
    GovDealsItemConfig,
    GovDealsMarketplace,
    GovDealsMarketplaceConfig,
    GovDealsSearchResultPage,
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
    """Test that GovDealsMarketplaceConfig can be created with location support."""
    config = GovDealsMarketplaceConfig(
        name="govdeals_test",
        monitor_config=monitor_config,
        market_type="govdeals",
        enabled=True,
        zipcode="43311",
        miles=250
    )
    assert config.name == "govdeals_test"
    assert config.market_type == "govdeals"
    assert config.zipcode == "43311"
    assert config.miles == 250


def test_item_config_with_location():
    """Test that GovDealsItemConfig can be created with location parameters."""
    config = GovDealsItemConfig(
        name="test_item",
        search_phrases=["trailer", "equipment"],
        zipcode="43311",
        miles=200
    )
    assert config.name == "test_item"
    assert config.zipcode == "43311"
    assert config.miles == 200


def test_zipcode_validation():
    """Test that zipcode validation works."""
    with pytest.raises(ValueError, match="zipcode must be 5 digits"):
        config = GovDealsItemConfig(
            name="test_item",
            search_phrases=["test"],
            zipcode="1234"  # Only 4 digits
        )
        config.handle_zipcode()


def test_miles_validation():
    """Test that miles validation works."""
    with pytest.raises(ValueError, match="miles must be a positive integer"):
        config = GovDealsItemConfig(
            name="test_item",
            search_phrases=["test"],
            miles=-10  # Negative value
        )
        config.handle_miles()


def test_url_building():
    """Test URL building for GovDeals search."""
    marketplace = GovDealsMarketplace(
        name="govdeals",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    # Test page 1 with location
    url = marketplace._build_search_url("trailer", page=1, zipcode="43311", miles=250)
    assert "govdeals.com/en/search" in url
    assert "kWord=trailer" in url
    assert "zipcode=43311" in url
    assert "miles=250" in url

    # Test page 2 (different URL pattern)
    url2 = marketplace._build_search_url("equipment", page=2, zipcode="43311", miles=250)
    assert "govdeals.com/en/search/filters" in url2
    assert "pn=2" in url2
    assert "kWord=equipment" in url2

    # Test without location
    url3 = marketplace._build_search_url("vehicle", page=1)
    assert "govdeals.com/en/search" in url3
    assert "zipcode" not in url3


def test_search_result_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of GovDeals search results page."""
    html_file = Path(__file__).parent.parent / "Scraping" / "govdeals" / "trailer _ GovDeals.html"

    if not html_file.exists():
        pytest.skip(f"HTML file not found: {html_file}")

    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    search_page = GovDealsSearchResultPage(page, translator, None)
    listings = search_page.get_listings()

    assert len(listings) > 0, "Should find listings on search results page"

    # Check first listing has required fields
    first_listing = listings[0]
    assert 'id' in first_listing
    assert 'item_id' in first_listing
    assert 'seller_id' in first_listing
    assert 'title' in first_listing
    assert 'url' in first_listing
    assert first_listing['id'], "Listing ID should not be empty"


def test_detail_page_parsing(new_context: CreateContextCallback, translator):
    """Test parsing of GovDeals detail page."""
    # Find detail page HTML file
    html_files = list(Path(__file__).parent.parent.glob("Scraping/govdeals/*GovDeals.html"))
    detail_files = [f for f in html_files if "trailer _" not in f.name and "Page 2" not in f.name]

    if not detail_files:
        pytest.skip("No GovDeals detail page HTML found")

    html_file = detail_files[0]
    page = new_context(java_script_enabled=False).new_page()
    page.goto(f"file://{html_file}")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)

    detail_page = GovDealsDetailPage(page, translator, None)
    details = detail_page.get_listing_details()

    assert 'title' in details
    assert details['title'], "Title should not be empty"


def test_listing_filtering():
    """Test that check_listing properly filters by keywords and antikeywords."""
    marketplace = GovDealsMarketplace(
        name="govdeals",
        browser=None,
        keyboard_monitor=None,
        logger=None
    )

    item_config = GovDealsItemConfig(
        name="test_item",
        search_phrases=["equipment"],
        keywords="trailer OR truck",
        antikeywords="salvage parts"
    )

    # Test listing that should pass
    good_listing = Listing(
        marketplace="govdeals",
        name="test_item",
        id="123/456",
        title="Utility Trailer",
        image="",
        price="USD 2,000.00",
        post_url="http://test.com",
        location="Ohio, USA",
        seller="GovDeals",
        condition="Used",
        description="Good condition utility trailer"
    )
    assert marketplace.check_listing(item_config, good_listing) is True

    # Test listing that should be excluded (has antikeyword)
    bad_listing = Listing(
        marketplace="govdeals",
        name="test_item",
        id="124/457",
        title="Salvage Truck Parts",
        image="",
        price="USD 500.00",
        post_url="http://test.com",
        location="Ohio, USA",
        seller="GovDeals",
        condition="For Parts",
        description="Salvage parts only"
    )
    assert marketplace.check_listing(item_config, bad_listing) is False


def test_get_config():
    """Test that get_config classmethod works."""
    config = GovDealsMarketplace.get_config(
        name="govdeals_test",
        market_type="govdeals",
        enabled=True,
        monitor_config=MonitorConfig(name="monitor"),
        zipcode="43311",
        miles=250
    )
    assert isinstance(config, GovDealsMarketplaceConfig)
    assert config.zipcode == "43311"
    assert config.miles == 250
