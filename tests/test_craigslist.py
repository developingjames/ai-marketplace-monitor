"""Tests for Craigslist marketplace implementation."""

import pytest

from ai_marketplace_monitor.craigslist import (
    CraigslistCategory,
    CraigslistCondition,
    CraigslistItemConfig,
    CraigslistMarketplace,
    CraigslistMarketplaceConfig,
)
from ai_marketplace_monitor.listing import Listing


class TestCraigslistConfig:
    """Test Craigslist configuration classes."""

    def test_marketplace_config_creation(self):
        """Test creating a valid marketplace config."""
        config = CraigslistMarketplaceConfig(
            name="test_craigslist",
            market_type="craigslist",
            search_city=["houston"],
        )
        assert config.name == "test_craigslist"
        assert config.market_type == "craigslist"
        assert config.search_city == ["houston"]

    def test_item_config_creation(self):
        """Test creating a valid item config."""
        config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["test phrase"],
            marketplace="craigslist",
        )
        assert config.name == "test_item"
        assert config.search_phrases == ["test phrase"]
        assert config.marketplace == "craigslist"

    def test_posted_today_validation(self):
        """Test posted_today must be boolean."""
        with pytest.raises(ValueError, match="posted_today must be a boolean"):
            CraigslistItemConfig(
                name="test",
                search_phrases=["test"],
                posted_today="invalid",
            )

    def test_has_image_validation(self):
        """Test has_image must be boolean."""
        with pytest.raises(ValueError, match="has_image must be a boolean"):
            CraigslistItemConfig(
                name="test",
                search_phrases=["test"],
                has_image="invalid",
            )

    def test_search_distance_validation(self):
        """Test search_distance must be positive integer."""
        with pytest.raises(ValueError, match="search_distance must be a positive integer"):
            CraigslistItemConfig(
                name="test",
                search_phrases=["test"],
                search_distance=-5,
            )

    def test_category_validation_valid(self):
        """Test valid category codes."""
        config = CraigslistItemConfig(
            name="test",
            search_phrases=["test"],
            category="cta",  # Cars & Trucks
        )
        assert config.category == "cta"

    def test_category_validation_invalid(self):
        """Test invalid category code raises error."""
        with pytest.raises(ValueError, match="category.*is not valid"):
            CraigslistItemConfig(
                name="test",
                search_phrases=["test"],
                category="invalid_category",
            )

    def test_condition_validation_valid(self):
        """Test valid condition values."""
        config = CraigslistItemConfig(
            name="test",
            search_phrases=["test"],
            condition=["new", "like new"],
        )
        assert config.condition == ["new", "like new"]

    def test_condition_validation_invalid(self):
        """Test invalid condition value raises error."""
        with pytest.raises(ValueError, match="condition must be one or more of"):
            CraigslistItemConfig(
                name="test",
                search_phrases=["test"],
                condition=["invalid_condition"],
            )

    def test_seller_locations_list_conversion(self):
        """Test seller_locations converts string to list."""
        config = CraigslistItemConfig(
            name="test",
            search_phrases=["test"],
            seller_locations="Houston",
        )
        assert config.seller_locations == ["Houston"]


class TestCraigslistMarketplace:
    """Test Craigslist marketplace methods."""

    def test_get_config(self):
        """Test get_config class method."""
        config = CraigslistMarketplace.get_config(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        assert isinstance(config, CraigslistMarketplaceConfig)
        assert config.name == "test"

    def test_get_item_config(self):
        """Test get_item_config class method."""
        config = CraigslistMarketplace.get_item_config(
            name="test",
            search_phrases=["test"],
        )
        assert isinstance(config, CraigslistItemConfig)
        assert config.name == "test"

    def test_build_search_url_basic(self):
        """Test building a basic search URL."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["gopro"],
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        url = marketplace.build_search_url(item_config, "houston", "gopro")

        assert "houston.craigslist.org" in url
        assert "query=gopro" in url
        assert "sort=date" in url

    def test_build_search_url_with_price(self):
        """Test building search URL with price filters."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["gopro"],
            min_price="100",
            max_price="300",
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        url = marketplace.build_search_url(
            item_config, "houston", "gopro", min_price="100", max_price="300"
        )

        assert "min_price=100" in url
        assert "max_price=300" in url

    def test_build_search_url_with_category(self):
        """Test building search URL with category."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["honda civic"],
            category="cta",  # Cars & Trucks
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        url = marketplace.build_search_url(item_config, "houston", "honda civic")

        assert "/search/cta" in url

    def test_build_search_url_with_filters(self):
        """Test building search URL with multiple filters."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["bike"],
            posted_today=True,
            has_image=True,
            search_distance=25,
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        url = marketplace.build_search_url(item_config, "houston", "bike")

        assert "postedToday=1" in url
        assert "hasPic=1" in url
        assert "search_distance=25" in url

    def test_check_listing_with_keywords(self):
        """Test listing filtering with keywords."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["bike"],
            keywords=["carbon", "shimano"],
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        # Listing with required keywords
        listing = Listing(
            marketplace="craigslist",
            name="test_item",
            id="123",
            title="Carbon bike",
            image="",
            price="$500",
            post_url="https://test.com",
            location="Houston",
            seller="User",
            condition="good",
            description="Shimano components",
        )

        assert marketplace.check_listing(listing, item_config) is True

        # Listing without required keywords
        listing_no_keywords = Listing(
            marketplace="craigslist",
            name="test_item",
            id="124",
            title="Mountain bike",
            image="",
            price="$300",
            post_url="https://test.com",
            location="Houston",
            seller="User",
            condition="fair",
            description="Basic components",
        )

        assert marketplace.check_listing(listing_no_keywords, item_config) is False

    def test_check_listing_with_antikeywords(self):
        """Test listing filtering with antikeywords."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["bike"],
            antikeywords=["damaged", "broken"],
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        # Listing with excluded keywords
        listing_damaged = Listing(
            marketplace="craigslist",
            name="test_item",
            id="123",
            title="Road bike",
            image="",
            price="$200",
            post_url="https://test.com",
            location="Houston",
            seller="User",
            condition="fair",
            description="Frame is damaged",
        )

        assert marketplace.check_listing(listing_damaged, item_config) is False

    def test_check_listing_with_location_filter(self):
        """Test listing filtering by location."""
        marketplace_config = CraigslistMarketplaceConfig(
            name="test",
            market_type="craigslist",
            search_city=["houston"],
        )
        item_config = CraigslistItemConfig(
            name="test_item",
            search_phrases=["bike"],
            seller_locations=["Houston", "Katy"],
        )

        marketplace = CraigslistMarketplace(
            name="test",
            browser=None,
        )
        marketplace.configure(marketplace_config)

        # Listing in allowed location
        listing_houston = Listing(
            marketplace="craigslist",
            name="test_item",
            id="123",
            title="Road bike",
            image="",
            price="$500",
            post_url="https://test.com",
            location="Houston",
            seller="User",
            condition="good",
            description="Good bike",
        )

        assert marketplace.check_listing(listing_houston, item_config, False) is True

        # Listing outside allowed location
        listing_austin = Listing(
            marketplace="craigslist",
            name="test_item",
            id="124",
            title="Mountain bike",
            image="",
            price="$400",
            post_url="https://test.com",
            location="Austin",
            seller="User",
            condition="good",
            description="Great bike",
        )

        assert marketplace.check_listing(listing_austin, item_config, False) is False


class TestCraigslistEnums:
    """Test Craigslist enum definitions."""

    def test_condition_enum_values(self):
        """Test CraigslistCondition enum values."""
        assert CraigslistCondition.NEW.value == "new"
        assert CraigslistCondition.LIKE_NEW.value == "like new"
        assert CraigslistCondition.EXCELLENT.value == "excellent"
        assert CraigslistCondition.GOOD.value == "good"
        assert CraigslistCondition.FAIR.value == "fair"
        assert CraigslistCondition.SALVAGE.value == "salvage"

    def test_category_enum_values(self):
        """Test CraigslistCategory enum has expected categories."""
        assert CraigslistCategory.ALL.value == "sss"
        assert CraigslistCategory.CARS_TRUCKS.value == "cta"
        assert CraigslistCategory.BICYCLES.value == "bia"
        assert CraigslistCategory.COMPUTERS.value == "sya"
        assert CraigslistCategory.FURNITURE.value == "fua"
        assert CraigslistCategory.FREE.value == "zip"
