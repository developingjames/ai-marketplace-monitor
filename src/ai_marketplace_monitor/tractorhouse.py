import re
import time
from dataclasses import dataclass
from logging import Logger
from typing import Any, Generator, List, Tuple, Type
from urllib.parse import quote

from playwright.sync_api import Browser, Page

from .listing import Listing
from .marketplace import ItemConfig, MarketPlace, Marketplace, MarketplaceConfig
from .utils import BaseConfig, KeyboardMonitor, hilight, is_substring


@dataclass
class TractorHouseMarketItemCommonConfig(BaseConfig):
    """Item options that can be defined in marketplace

    This class defines and processes options that can be specified
    in both marketplace and item sections, specific to TractorHouse
    """

    states: List[str] | None = None
    category: str | None = None
    horsepower_min: int | None = None
    horsepower_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None

    def handle_states(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.states is None:
            return

        if isinstance(self.states, str):
            self.states = [self.states]
        if not isinstance(self.states, list) or not all(
            isinstance(x, str) for x in self.states
        ):
            raise ValueError(f"Item {hilight(self.name)} states must be a list of strings.")

    def handle_category(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.category is None:
            return
        if not isinstance(self.category, str):
            raise ValueError(f"Item {hilight(self.name)} category must be a string.")

    def handle_horsepower_min(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.horsepower_min is None:
            return
        if not isinstance(self.horsepower_min, int) or self.horsepower_min < 0:
            raise ValueError(
                f"Item {hilight(self.name)} horsepower_min must be a positive integer."
            )

    def handle_horsepower_max(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.horsepower_max is None:
            return
        if not isinstance(self.horsepower_max, int) or self.horsepower_max < 0:
            raise ValueError(
                f"Item {hilight(self.name)} horsepower_max must be a positive integer."
            )

    def handle_year_min(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.year_min is None:
            return
        if not isinstance(self.year_min, int) or self.year_min < 1900:
            raise ValueError(
                f"Item {hilight(self.name)} year_min must be an integer >= 1900."
            )

    def handle_year_max(self: "TractorHouseMarketItemCommonConfig") -> None:
        if self.year_max is None:
            return
        if not isinstance(self.year_max, int) or self.year_max < 1900:
            raise ValueError(
                f"Item {hilight(self.name)} year_max must be an integer >= 1900."
            )


@dataclass
class TractorHouseMarketplaceConfig(MarketplaceConfig, TractorHouseMarketItemCommonConfig):
    """TractorHouse marketplace configuration"""

    market_type: str | None = "tractorhouse"

    def handle_market_type(self: "TractorHouseMarketplaceConfig") -> None:
        """Validate that market_type is tractorhouse"""
        super().handle_market_type()
        if self.market_type and self.market_type != "tractorhouse":
            raise ValueError(
                f"TractorHouseMarketplaceConfig market_type must be 'tractorhouse', "
                f"got '{self.market_type}'"
            )


@dataclass
class TractorHouseItemConfig(ItemConfig, TractorHouseMarketItemCommonConfig):
    """TractorHouse item search configuration"""

    pass


class TractorHouseMarketplace(Marketplace[TractorHouseMarketplaceConfig, TractorHouseItemConfig]):
    ItemConfigClass = TractorHouseItemConfig

    def __init__(
        self: "TractorHouseMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)

    @classmethod
    def get_config(
        cls: Type["TractorHouseMarketplace"], **kwargs: Any
    ) -> TractorHouseMarketplaceConfig:
        return TractorHouseMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["TractorHouseMarketplace"], **kwargs: Any) -> TractorHouseItemConfig:
        # Filter kwargs to only include fields that exist in TractorHouseItemConfig
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return TractorHouseItemConfig(**filtered_kwargs)

    def build_search_url(
        self: "TractorHouseMarketplace",
        item_config: TractorHouseItemConfig,
        search_phrase: str,
        min_price: str | None = None,
        max_price: str | None = None,
    ) -> str:
        """Build TractorHouse search URL with filters"""
        # Base URL
        url = "https://www.tractorhouse.com/listings/search"

        # Query parameters
        params = []

        # Keywords
        if search_phrase:
            params.append(f"keywords={quote(search_phrase)}")

        # Category - default to 1100 (Tractors) if not specified
        category = item_config.category or self.config.category or "1100"
        params.append(f"Category={category}")

        # Price filters
        if min_price or max_price:
            min_val = "0"
            max_val = "999999"

            if min_price:
                price_value = min_price.split()[0] if " " in min_price else min_price
                min_val = price_value

            if max_price:
                price_value = max_price.split()[0] if " " in max_price else max_price
                max_val = price_value

            # TractorHouse uses min*max format
            params.append(f"Price={min_val}*{max_val}")

        # Horsepower range
        horsepower_min = item_config.horsepower_min or self.config.horsepower_min
        horsepower_max = item_config.horsepower_max or self.config.horsepower_max

        if horsepower_min is not None or horsepower_max is not None:
            min_hp = horsepower_min if horsepower_min is not None else 0
            max_hp = horsepower_max if horsepower_max is not None else 999
            params.append(f"Horsepower={min_hp}*{max_hp}")

        # Year range
        year_min = item_config.year_min or self.config.year_min
        year_max = item_config.year_max or self.config.year_max

        if year_min is not None or year_max is not None:
            min_yr = year_min if year_min is not None else 1920
            max_yr = year_max if year_max is not None else 2026
            params.append(f"Year={min_yr}*{max_yr}")

        # States filter
        states = item_config.states or self.config.states
        if states:
            # Convert states to uppercase and join with pipe
            state_str = "|".join([state.upper() for state in states])
            params.append(f"State={state_str}")

        return url + "?" + "&".join(params)

    def parse_search_results(
        self: "TractorHouseMarketplace", page: Page, item_name: str
    ) -> List[Listing]:
        """Parse TractorHouse search results page"""
        listings = []

        # Wait for search results to load
        try:
            # TractorHouse likely uses a different selector - we'll need to inspect
            # Common patterns: .listing-item, .search-result, .equipment-listing, etc.
            page.wait_for_selector(".listing-item, .search-result, .equipment-card", timeout=10000)
        except Exception:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Retrieve]', 'warn')} No search results found on page"
                )
            return listings

        # Try common selectors for listing containers
        result_elements = None
        for selector in [".listing-item", ".search-result", ".equipment-card", ".listing-card", "[data-listing-id]"]:
            result_elements = page.query_selector_all(selector)
            if result_elements:
                break

        if not result_elements:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Parse]', 'warn')} Could not find listing elements on page"
                )
            return listings

        for element in result_elements:
            try:
                # Extract listing ID - try multiple approaches
                listing_id = (
                    element.get_attribute("data-listing-id") or
                    element.get_attribute("data-id") or
                    element.get_attribute("id") or
                    ""
                )

                # Extract title - try multiple selectors
                title = ""
                title_selectors = [
                    ".listing-title",
                    ".title",
                    "h3",
                    "h4",
                    ".equipment-name",
                    "a[href*='/listings/']",
                ]
                for selector in title_selectors:
                    title_element = element.query_selector(selector)
                    if title_element:
                        title = title_element.text_content().strip()
                        if title:
                            break

                # Extract price - try multiple selectors
                price = "$0"
                price_selectors = [
                    ".price",
                    ".listing-price",
                    ".equipment-price",
                    "[class*='price']",
                ]
                for selector in price_selectors:
                    price_element = element.query_selector(selector)
                    if price_element:
                        price_text = price_element.text_content().strip()
                        if price_text and price_text != "$0":
                            price = price_text
                            break

                # Extract location
                location = ""
                location_selectors = [".location", ".listing-location", ".seller-location"]
                for selector in location_selectors:
                    location_element = element.query_selector(selector)
                    if location_element:
                        location = location_element.text_content().strip()
                        if location:
                            break

                # Extract URL
                link_element = element.query_selector("a[href*='/listings/']") or element.query_selector("a")
                post_url = ""
                if link_element:
                    post_url = link_element.get_attribute("href") or ""
                    if post_url and not post_url.startswith("http"):
                        post_url = "https://www.tractorhouse.com" + post_url

                # Extract image URL
                img_element = element.query_selector("img")
                image_url = ""
                if img_element:
                    image_url = img_element.get_attribute("src") or img_element.get_attribute("data-src") or ""

                # Validate that we extracted essential data
                if not title:
                    if self.logger:
                        self.logger.debug(
                            f"{hilight('[Parse]', 'warn')} Failed to extract title for listing {listing_id}. "
                            f"Skipping this listing."
                        )
                    continue

                # If we couldn't extract a listing ID, try to get it from the URL
                if not listing_id and post_url:
                    id_match = re.search(r'/listings/([^/]+)', post_url)
                    if id_match:
                        listing_id = id_match.group(1)

                listing = Listing(
                    marketplace="tractorhouse",
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
        self: "TractorHouseMarketplace",
        post_url: str,
        item_config: TractorHouseItemConfig,
        price: str | None = None,
        title: str | None = None,
    ) -> Tuple[Listing, bool]:
        """Fetch detailed information for a TractorHouse listing"""
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

            # Wait for page to load - try multiple selectors
            try:
                page.wait_for_selector(".listing-details, .equipment-details, h1", timeout=10000)
            except Exception:
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Retrieve]', 'warn')} Timeout waiting for listing details page"
                    )

            # Extract listing ID from URL
            listing_id_match = re.search(r'/listings/([^/]+)', post_url)
            listing_id = listing_id_match.group(1) if listing_id_match else ""

            # Extract title
            title = ""
            title_selectors = ["h1", ".listing-title", ".equipment-title", ".detail-title"]
            for selector in title_selectors:
                title_element = page.query_selector(selector)
                if title_element:
                    title = title_element.text_content().strip()
                    if title:
                        break

            # Extract price
            price = "$0"
            price_selectors = [".price", ".listing-price", ".equipment-price", "[class*='price']"]
            for selector in price_selectors:
                price_element = page.query_selector(selector)
                if price_element:
                    price_text = price_element.text_content().strip()
                    if price_text and price_text != "$0":
                        price = price_text
                        break

            # Extract description
            description = ""
            description_selectors = [
                ".description",
                ".listing-description",
                ".equipment-description",
                "[class*='description']",
            ]
            for selector in description_selectors:
                description_element = page.query_selector(selector)
                if description_element:
                    description = description_element.text_content().strip()
                    if description:
                        break

            # Extract location
            location = ""
            location_selectors = [".location", ".seller-location", ".listing-location"]
            for selector in location_selectors:
                location_element = page.query_selector(selector)
                if location_element:
                    location = location_element.text_content().strip()
                    if location:
                        break

            # Extract condition
            condition = ""
            condition_selectors = [".condition", ".equipment-condition", "[class*='condition']"]
            for selector in condition_selectors:
                condition_element = page.query_selector(selector)
                if condition_element:
                    condition = condition_element.text_content().strip()
                    if condition:
                        break

            # Extract image URL
            image_url = ""
            img_element = page.query_selector(".main-image img, .gallery img, img[class*='listing']")
            if img_element:
                image_url = img_element.get_attribute("src") or img_element.get_attribute("data-src") or ""

            # Extract seller info
            seller = ""
            seller_selectors = [".seller-name", ".dealer-name", "[class*='seller']"]
            for selector in seller_selectors:
                seller_element = page.query_selector(selector)
                if seller_element:
                    seller = seller_element.text_content().strip()
                    if seller:
                        break

            if not seller:
                seller = "TractorHouse Seller"

            # Validate that we extracted essential data from detail page
            if not title:
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Parse Warning]', 'warn')} Failed to extract title from detail page: {post_url}. "
                        f"Using title from search results if available."
                    )
                # Use the title passed from search results if available
                title = normalized_title or "Unknown Equipment"

            if not price or price == "$0":
                if self.logger:
                    self.logger.debug(
                        f"{hilight('[Parse]', 'warn')} No price found for listing {listing_id}: {title}. "
                        f"This may be a contact-for-price listing."
                    )
                price = "$0"

            listing = Listing(
                marketplace="tractorhouse",
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
        self: "TractorHouseMarketplace",
        item: Listing,
        item_config: TractorHouseItemConfig,
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
        self: "TractorHouseMarketplace", item: TractorHouseItemConfig
    ) -> Generator[Listing, None, None]:
        """Search TractorHouse for listings matching the item configuration"""
        if self.logger:
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching TractorHouse for {hilight(item.name)}"
            )

        # Search each phrase
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.info(
                    f"{hilight('[Search]', 'info')} Searching for '{search_phrase}'"
                )

            # Build search URL
            url = self.build_search_url(
                item, search_phrase, item.min_price, item.max_price
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
                                f"[Detail Fetch] {detailed_listing.title} (ID: {detailed_listing.id}) - "
                                f"from_cache={from_cache}, "
                                f"desc_len={len(detailed_listing.description)} "
                                f"for item={item.name}"
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
                        f"{hilight('[Error]', 'fail')} Failed to process search results: {e}"
                    )
                raise
