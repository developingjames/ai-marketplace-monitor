import re
import time
from dataclasses import dataclass
from enum import Enum
from logging import Logger
from typing import Any, Generator, List, Tuple, Type
from urllib.parse import quote

from playwright.sync_api import Browser, Page

from .listing import Listing
from .marketplace import ItemConfig, MarketPlace, Marketplace, MarketplaceConfig
from .utils import BaseConfig, KeyboardMonitor, hilight, is_substring


class CraigslistCondition(Enum):
    NEW = "new"
    LIKE_NEW = "like new"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    SALVAGE = "salvage"


class CraigslistCategory(Enum):
    ALL = "sss"
    ANTIQUES = "ata"
    APPLIANCES = "ppa"
    ARTS_CRAFTS = "ara"
    ATV_UTV_SNO = "sna"
    AUTO_PARTS = "pta"
    AVIATION = "ava"
    BABY_KID = "baa"
    BARTER = "bar"
    BICYCLE_PARTS = "bip"
    BICYCLES = "bia"
    BOAT_PARTS = "bpa"
    BOATS = "boa"
    BOOKS = "bka"
    BUSINESS = "bfa"
    CARS_TRUCKS = "cta"
    CDS_DVD_VHS = "ema"
    CELL_PHONES = "moa"
    CLOTHING_ACC = "cla"
    COLLECTIBLES = "cba"
    COMPUTER_PARTS = "syp"
    COMPUTERS = "sya"
    ELECTRONICS = "ela"
    FARM_GARDEN = "gra"
    FREE = "zip"
    FURNITURE = "fua"
    GARAGE_SALE = "gms"
    GENERAL = "foa"
    HEALTH_BEAUTY = "haa"
    HEAVY_EQUIP = "hva"
    HOUSEHOLD = "hsa"
    JEWELRY = "jwa"
    MATERIALS = "maa"
    MOTORCYCLE_PARTS = "mpa"
    MOTORCYCLES = "mca"
    MUSIC_INSTR = "msa"
    PHOTO_VIDEO = "pha"
    RV_CAMP = "rva"
    SPORTING = "sga"
    TICKETS = "tia"
    TOOLS = "tla"
    TOYS_GAMES = "taa"
    TRAILERS = "tra"
    VIDEO_GAMING = "vga"
    WANTED = "waa"
    WHEELS_TIRES = "wta"


@dataclass
class CraigslistMarketItemCommonConfig(BaseConfig):
    """Item options that can be defined in marketplace

    This class defines and processes options that can be specified
    in both marketplace and item sections, specific to craigslist
    """

    seller_locations: List[str] | None = None
    posted_today: bool | None = None
    has_image: bool | None = None
    search_nearby: bool | None = None
    bundle_duplicates: bool | None = None
    search_distance: int | None = None  # Legacy Craigslist-specific parameter
    search_lat: float | None = None
    search_lon: float | None = None
    category: str | None = None
    condition: List[str] | None = None
    crypto_ok: bool | None = None

    def handle_seller_locations(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.seller_locations is None:
            return

        if isinstance(self.seller_locations, str):
            self.seller_locations = [self.seller_locations]
        if not isinstance(self.seller_locations, list) or not all(
            isinstance(x, str) for x in self.seller_locations
        ):
            raise ValueError(f"Item {hilight(self.name)} seller_locations must be a list.")

    def handle_posted_today(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.posted_today is None:
            return
        if not isinstance(self.posted_today, bool):
            raise ValueError(f"Item {hilight(self.name)} posted_today must be a boolean.")

    def handle_has_image(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.has_image is None:
            return
        if not isinstance(self.has_image, bool):
            raise ValueError(f"Item {hilight(self.name)} has_image must be a boolean.")

    def handle_search_nearby(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.search_nearby is None:
            return
        if not isinstance(self.search_nearby, bool):
            raise ValueError(f"Item {hilight(self.name)} search_nearby must be a boolean.")

    def handle_bundle_duplicates(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.bundle_duplicates is None:
            return
        if not isinstance(self.bundle_duplicates, bool):
            raise ValueError(f"Item {hilight(self.name)} bundle_duplicates must be a boolean.")

    def handle_search_distance(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.search_distance is None:
            return
        if not isinstance(self.search_distance, int) or self.search_distance < 0:
            raise ValueError(
                f"Item {hilight(self.name)} search_distance must be a positive integer."
            )

    def handle_search_lat(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.search_lat is None:
            return
        if not isinstance(self.search_lat, (int, float)) or not (-90 <= self.search_lat <= 90):
            raise ValueError(
                f"Item {hilight(self.name)} search_lat must be a number between -90 and 90."
            )

    def handle_search_lon(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.search_lon is None:
            return
        if not isinstance(self.search_lon, (int, float)) or not (-180 <= self.search_lon <= 180):
            raise ValueError(
                f"Item {hilight(self.name)} search_lon must be a number between -180 and 180."
            )

    def handle_category(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.category is None:
            return
        if not isinstance(self.category, str):
            raise ValueError(f"Item {hilight(self.name)} category must be a string.")
        # Validate against known categories
        valid_categories = [cat.value for cat in CraigslistCategory]
        if self.category not in valid_categories:
            raise ValueError(
                f"Item {hilight(self.name)} category '{self.category}' is not valid. "
                f"See CraigslistCategory enum for valid values."
            )

    def handle_condition(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.condition is None:
            return
        if isinstance(self.condition, str):
            self.condition = [self.condition]
        if not isinstance(self.condition, list) or not all(
            isinstance(x, str) and x in [cond.value for cond in CraigslistCondition]
            for x in self.condition
        ):
            raise ValueError(
                f"Item {hilight(self.name)} condition must be one or more of "
                f"'new', 'like new', 'excellent', 'good', 'fair', 'salvage'."
            )

    def handle_crypto_ok(self: "CraigslistMarketItemCommonConfig") -> None:
        if self.crypto_ok is None:
            return
        if not isinstance(self.crypto_ok, bool):
            raise ValueError(f"Item {hilight(self.name)} crypto_ok must be a boolean.")


@dataclass
class CraigslistMarketplaceConfig(MarketplaceConfig, CraigslistMarketItemCommonConfig):
    """Craigslist marketplace configuration"""

    market_type: str | None = MarketPlace.CRAIGSLIST.value

    def handle_market_type(self: "CraigslistMarketplaceConfig") -> None:
        """Validate that market_type is craigslist"""
        super().handle_market_type()
        if self.market_type and self.market_type != MarketPlace.CRAIGSLIST.value:
            raise ValueError(
                f"CraigslistMarketplaceConfig market_type must be 'craigslist', "
                f"got '{self.market_type}'"
            )


@dataclass
class CraigslistItemConfig(ItemConfig, CraigslistMarketItemCommonConfig):
    """Craigslist item search configuration"""

    pass


class CraigslistMarketplace(Marketplace[CraigslistMarketplaceConfig, CraigslistItemConfig]):
    ItemConfigClass = CraigslistItemConfig

    def __init__(
        self: "CraigslistMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)

    @classmethod
    def get_config(
        cls: Type["CraigslistMarketplace"], **kwargs: Any
    ) -> CraigslistMarketplaceConfig:
        return CraigslistMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["CraigslistMarketplace"], **kwargs: Any) -> CraigslistItemConfig:
        return CraigslistItemConfig(**kwargs)

    def build_search_url(
        self: "CraigslistMarketplace",
        item_config: CraigslistItemConfig,
        city: str,
        search_phrase: str,
        min_price: str | None = None,
        max_price: str | None = None,
    ) -> str:
        """Build Craigslist search URL with filters"""
        # Determine category
        category = item_config.category or self.config.category or CraigslistCategory.ALL.value

        # Base URL
        url = f"https://{city}.craigslist.org/search/{category}"

        # Query parameters
        params = []
        params.append(f"query={quote(search_phrase)}")

        # Price filters
        if min_price:
            price_value = min_price.split()[0] if " " in min_price else min_price
            params.append(f"min_price={price_value}")

        if max_price:
            price_value = max_price.split()[0] if " " in max_price else max_price
            params.append(f"max_price={price_value}")

        # Distance filter with lat/lon coordinates
        # Precedence: item-specific (search_distance > search_radius) > marketplace defaults
        search_distance = (
            item_config.search_distance
            or item_config.search_radius
            or self.config.search_distance
            or self.config.search_radius
        )
        search_lat = item_config.search_lat or self.config.search_lat
        search_lon = item_config.search_lon or self.config.search_lon

        if search_distance:
            params.append(f"search_distance={search_distance}")
            # Add lat/lon if provided to enable proper radius search
            if search_lat is not None and search_lon is not None:
                params.append(f"lat={search_lat}")
                params.append(f"lon={search_lon}")

        # Posted today filter
        posted_today = item_config.posted_today or self.config.posted_today
        if posted_today:
            params.append("postedToday=1")

        # Has image filter
        has_image = item_config.has_image or self.config.has_image
        if has_image:
            params.append("hasPic=1")

        # Search nearby areas
        search_nearby = item_config.search_nearby or self.config.search_nearby
        if search_nearby:
            params.append("searchNearby=1")

        # Bundle duplicates
        bundle_duplicates = item_config.bundle_duplicates or self.config.bundle_duplicates
        if bundle_duplicates:
            params.append("bundleDuplicates=1")

        # Condition filters
        condition = item_config.condition or self.config.condition
        if condition:
            for cond in condition:
                # Map condition values to Craigslist condition codes
                condition_map = {
                    "new": "10",
                    "like new": "20",
                    "excellent": "30",
                    "good": "40",
                    "fair": "50",
                    "salvage": "60",
                }
                if cond in condition_map:
                    params.append(f"condition={condition_map[cond]}")

        # Crypto OK filter
        crypto_ok = item_config.crypto_ok or self.config.crypto_ok
        if crypto_ok:
            params.append("crypto_currency_ok=1")

        # Sort by newest
        params.append("sort=date")

        return url + "?" + "&".join(params)

    def parse_search_results(
        self: "CraigslistMarketplace", page: Page, item_name: str
    ) -> List[Listing]:
        """Parse Craigslist search results page"""
        listings = []

        # Wait for search results to load
        try:
            page.wait_for_selector(".cl-search-result", timeout=10000)
        except Exception:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Retrieve]', 'warn')} No search results found on page"
                )
            return listings

        # Get all listing elements
        result_elements = page.query_selector_all(".cl-search-result")

        for element in result_elements:
            try:
                # Extract listing ID from data-pid attribute
                listing_id = element.get_attribute("data-pid")
                if not listing_id:
                    continue

                # Try to find title with multiple possible selectors
                title = ""
                title_selectors = [
                    ".posting-title .label",  # New Craigslist layout
                    ".posting-title span.label",  # Alternative
                    ".title",  # Old selector
                    ".title-blob",  # Possible selector
                    "a.main",  # Link might have title attribute
                    ".meta .title",
                ]
                for selector in title_selectors:
                    title_element = element.query_selector(selector)
                    if title_element:
                        # Try getting from text content first
                        title = title_element.text_content().strip()
                        # If empty, try title attribute
                        if not title:
                            title = title_element.get_attribute("title") or ""
                        if title:
                            break

                if not title:
                    link = element.query_selector("a")
                    if link:
                        title = link.get_attribute("aria-label") or ""

                # Try to find price with multiple possible selectors
                price = "$0"
                price_selectors = [
                    ".price",  # Old selector
                    ".priceinfo",  # Possible new selector
                    ".meta .price",
                ]
                for selector in price_selectors:
                    price_element = element.query_selector(selector)
                    if price_element:
                        price = price_element.text_content().strip()
                        if price and price != "$0":
                            break

                # Extract location
                location_element = element.query_selector(".location")
                location = location_element.text_content().strip() if location_element else ""

                # Extract URL
                link_element = element.query_selector("a")
                post_url = link_element.get_attribute("href") if link_element else ""
                if post_url and not post_url.startswith("http"):
                    post_url = "https:" + post_url if post_url.startswith("//") else post_url

                # Extract image URL
                img_element = element.query_selector("img")
                image_url = ""
                if img_element:
                    image_url = img_element.get_attribute("src") or ""

                # Validate that we extracted essential data
                # Title is always required - if missing, HTML structure likely changed
                if not title:
                    if self.logger:
                        self.logger.error(
                            f"{hilight('[Parse Error]', 'fail')} Failed to extract title for listing {listing_id}. "
                            f"Craigslist HTML structure may have changed. URL: {post_url}"
                        )
                    raise RuntimeError(
                        f"Failed to extract title from Craigslist search results for listing {listing_id}. "
                        f"The HTML structure may have changed and the scraper needs to be updated."
                    )

                # Price is optional (free listings, contact for price, etc.)
                # But log a warning if we can't extract it for debugging
                if not price or price == "$0":
                    if self.logger:
                        self.logger.debug(
                            f"{hilight('[Parse]', 'warn')} No price found for listing {listing_id}: {title}. "
                            f"This may be a free listing or contact-for-price."
                        )
                    # Set to $0 for free/no-price listings
                    price = "$0"

                listing = Listing(
                    marketplace="craigslist",
                    name=item_name,
                    id=listing_id,
                    title=title,
                    image=image_url,
                    price=price,
                    post_url=post_url,
                    location=location,
                    seller="",
                    condition="",
                    description="",
                )

                listings.append(listing)

            except Exception as e:
                if self.logger:
                    self.logger.debug(f"{hilight('[Parse]', 'warn')} Failed to parse listing: {e}")
                continue

        return listings

    def get_listing_details(
        self: "CraigslistMarketplace",
        post_url: str,
        item_config: CraigslistItemConfig,
        price: str | None = None,
        title: str | None = None,
    ) -> Tuple[Listing, bool]:
        """Fetch detailed information for a Craigslist listing"""
        from .listing import Listing

        details = Listing.from_cache(post_url)

        # Check if we should ignore price changes for cache validation
        ignore_price = getattr(item_config, "cache_ignore_price_changes", False) or False

        # Normalize empty strings to None for comparison
        normalized_price = price if price and price != "$0" else None
        normalized_title = title if title else None

        # Price validation: ignore if user disabled price checking
        price_matches = (
            normalized_price is None
            or ignore_price
            or details is None
            or details.price == normalized_price
        )

        # Title validation: treat empty strings as None
        title_matches = (
            normalized_title is None
            or details is None
            or details.title == normalized_title
        )

        if details is not None and price_matches and title_matches:
            # if the price and title are the same, we assume everything else is unchanged.
            return details, True

        try:
            page = self.create_page()
            self.goto_url(post_url)

            # Wait for page to load
            page.wait_for_selector("#titletextonly", timeout=10000)

            # Extract listing ID from URL
            listing_id_match = re.search(r"/(\d+)\.html", post_url)
            listing_id = listing_id_match.group(1) if listing_id_match else ""

            # Extract title
            title_element = page.query_selector("#titletextonly")
            title = title_element.text_content().strip() if title_element else ""

            # Extract price
            price_element = page.query_selector(".price")
            price = price_element.text_content().strip() if price_element else "$0"

            # Extract description
            description_element = page.query_selector("#postingbody")
            description = ""
            if description_element:
                description = description_element.text_content().strip()
                # Remove "QR Code Link to This Post" text that appears at the end
                description = re.sub(r"QR Code Link to This Post.*$", "", description).strip()

            # Extract location
            location = ""
            location_element = page.query_selector(".postingtitletext small")
            if location_element:
                location = location_element.text_content().strip()
                # Remove parentheses
                location = location.strip("()")

            # Extract condition
            condition = ""
            condition_element = page.query_selector(".condition")
            if condition_element:
                condition = condition_element.text_content().strip()

            # Extract image URL
            image_url = ""
            img_element = page.query_selector(".slide img")
            if img_element:
                image_url = img_element.get_attribute("src") or ""

            # Extract seller info (Craigslist doesn't show seller names publicly)
            seller = "Craigslist User"

            # Validate that we extracted essential data from detail page
            if not title:
                raise RuntimeError(
                    f"Failed to extract title from Craigslist detail page: {post_url}. "
                    f"The HTML structure may have changed and the scraper needs to be updated."
                )

            if not price or price == "$0":
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Parse Warning]', 'warn')} Failed to extract price from detail page: {post_url}. "
                        f"Using price from search results if available."
                    )

            if not description:
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Parse Warning]', 'warn')} Failed to extract description from detail page: {post_url}. "
                        f"Description will be empty."
                    )

            listing = Listing(
                marketplace="craigslist",
                name=item_config.name,
                id=listing_id,
                title=title,
                image=image_url,
                price=price,
                post_url=post_url,
                location=location,
                seller=seller,
                condition=condition,
                description=description,
            )

            # Save to cache
            listing.to_cache(post_url)

            return listing, False

        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Retrieve]', 'warn')} Failed to fetch listing details: {e}"
                )
            # If we have stale cache, return it with warning
            if details is not None:
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Cache]', 'warn')} Returning stale cache for {post_url}"
                    )
                return details, True
            raise  # No cache available, propagate error

    def check_listing(
        self: "CraigslistMarketplace",
        item: Listing,
        item_config: CraigslistItemConfig,
        description_available: bool = True,
    ) -> bool:
        """Filter listings based on keywords, location, and sellers"""
        # Check for keyword spam in description before checking keywords
        if description_available and item.description:
            from .utils import detect_keyword_spam
            if detect_keyword_spam(item.description, logger=self.logger):
                if self.logger:
                    self.logger.info(
                        f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} due to {hilight("keyword spam detected", "fail")} in description"""
                    )
                return False

        # Check antikeywords
        antikeywords = item_config.antikeywords
        if antikeywords and (
            is_substring(antikeywords, item.title + " " + item.description, logger=self.logger)
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} due to {hilight("excluded keywords", "fail")}: {", ".join(antikeywords) if isinstance(antikeywords, list) else antikeywords}"""
                )
            return False

        # Check required keywords
        keywords = item_config.keywords
        if (
            description_available
            and keywords
            and not (
                is_substring(keywords, item.title + "  " + item.description, logger=self.logger)
            )
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} {hilight("without required keywords", "fail")} in title and description."""
                )
            return False

        # Check seller locations
        if item_config.seller_locations is not None:
            allowed_locations = item_config.seller_locations
        else:
            allowed_locations = self.config.seller_locations or []
        if allowed_locations and not is_substring(
            allowed_locations, item.location, logger=self.logger
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight("out of area", "fail")} item {hilight(item.title)} from location {hilight(item.location)}"""
                )
            return False

        # Check exclude_sellers
        if item_config.exclude_sellers is not None:
            exclude_sellers = item_config.exclude_sellers
        else:
            exclude_sellers = self.config.exclude_sellers or []
        if (
            item.seller
            and exclude_sellers
            and is_substring(exclude_sellers, item.seller, logger=self.logger)
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} sold by {hilight("banned seller", "failed")} {hilight(item.seller)}"""
                )
            return False

        return True

    def search(
        self: "CraigslistMarketplace", item: CraigslistItemConfig
    ) -> Generator[Listing, None, None]:
        """Search Craigslist for listings matching the item configuration"""
        if self.logger:
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching Craigslist for {hilight(item.name)}"
            )

        # Determine search cities
        search_cities = item.search_city or self.config.search_city
        if not search_cities:
            if self.logger:
                self.logger.error(
                    f"{hilight('[Error]', 'fail')} No search_city specified for {item.name}"
                )
            return

        # Search each city
        for city in search_cities:
            for search_phrase in item.search_phrases:
                if self.logger:
                    self.logger.info(
                        f"{hilight('[Search]', 'info')} Searching {hilight(city)} for '{search_phrase}'"
                    )

                # Build search URL
                url = self.build_search_url(
                    item, city, search_phrase, item.min_price, item.max_price
                )

                # Navigate to search results
                try:
                    page = self.create_page()
                    self.goto_url(url)
                    time.sleep(2)  # Brief delay to let page load

                    # Parse search results
                    listings = self.parse_search_results(page, item.name)

                    if self.logger:
                        self.logger.info(
                            f"{hilight('[Found]', 'succ')} Found {len(listings)} listings"
                        )

                    # Process each listing
                    for listing in listings:
                        # Check basic filters first (without description)
                        if not self.check_listing(listing, item, description_available=False):
                            continue

                        # Fetch detailed listing information with cache support
                        try:
                            detailed_listing, from_cache = self.get_listing_details(
                                listing.post_url,
                                item,
                                price=listing.price,
                                title=listing.title,
                            )

                            if self.logger:
                                self.logger.debug(
                                    f"[Detail Fetch] {detailed_listing.title} - "
                                    f"from_cache={from_cache}, "
                                    f"desc_len={len(detailed_listing.description)}"
                                )

                            # Check filters again with description
                            if self.check_listing(detailed_listing, item):
                                if self.logger:
                                    self.logger.debug(
                                        f"[Filter Pass] {detailed_listing.title} - "
                                        f"Passed all filters, yielding result"
                                    )
                                yield detailed_listing

                            # Only delay if we fetched from web (not cache)
                            if not from_cache:
                                time.sleep(1)
                        except Exception as e:
                            if self.logger:
                                self.logger.error(
                                    f"{hilight('[Error]', 'fail')} Failed to get details for {listing.post_url}: {e}"
                                )
                            raise

                except Exception as e:
                    if self.logger:
                        self.logger.error(
                            f"{hilight('[Error]', 'fail')} Failed to process search results for {city}: {e}"
                        )
                    raise
