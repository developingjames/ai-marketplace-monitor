"""
TractorHouse Marketplace Implementation

STATUS: DISABLED - Bot Detection Issues
========================================

CURRENT STATE:
- Implementation is complete and functional for parsing search results and detail pages
- Uses JSON extraction from embedded data (not HTML scraping)
- Supports pagination, filtering by state, category, horsepower, year, price
- Manual initialization pattern allows user to complete captchas

BOT DETECTION PROBLEM:
- TractorHouse uses enterprise-grade bot protection (Distil Networks/Imperva)
- Homepage allows access (honeypot to fingerprint)
- Any navigation to search/listing pages triggers bot detection
- Even after solving captchas, subsequent pages get blocked
- The browser profile gets flagged and remains blocked even on manual navigation
- Standard Playwright automation markers are detected despite stealth attempts

WHAT WE TRIED:
1. Stealth JavaScript injection (navigator.webdriver overrides, etc.)
2. Browser args to hide automation (--disable-blink-features=AutomationControlled)
3. Human-like delays and timing (random sleep, networkidle waits)
4. Manual initialization with captcha solving
5. Persistent browser context to maintain cookies/fingerprint
6. Following Facebook's proven pattern (which works for less aggressive detection)

RESULT: TractorHouse's bot detection is too sophisticated for standard Playwright

POTENTIAL FUTURE SOLUTIONS (NOT IMPLEMENTED):
1. Undetected-chromedriver approach:
   - Use real Google Chrome (not Chromium) with binary patching
   - Libraries: rebrowser-playwright, playwright-stealth-patch, nodriver
   - Patches Chrome binary to remove automation flags at runtime
   - Success rate: 40-60% against Distil Networks (not guaranteed)
   - Requires ongoing maintenance as detection evolves

2. Official API:
   - Check if TractorHouse offers a legitimate API for developers
   - More reliable but may have rate limits or costs

3. Real Chrome profile:
   - Use user's actual Chrome profile (risky - could corrupt profile or flag account)
   - More complex implementation

4. Manual monitoring:
   - TractorHouse may need to be checked manually

RECOMMENDATION: Table TractorHouse until bot detection approach is worth the effort/risk

See TRACTORHOUSE_IMPLEMENTATION.md for full implementation details.
"""

import re
import time
from dataclasses import dataclass
from logging import Logger
from typing import Any, Dict, Generator, List, Tuple, Type
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
    login_wait_time: int | None = None

    def handle_market_type(self: "TractorHouseMarketplaceConfig") -> None:
        """Validate that market_type is tractorhouse"""
        super().handle_market_type()
        if self.market_type and self.market_type != "tractorhouse":
            raise ValueError(
                f"TractorHouseMarketplaceConfig market_type must be 'tractorhouse', "
                f"got '{self.market_type}'"
            )

    def handle_login_wait_time(self: "TractorHouseMarketplaceConfig") -> None:
        from .utils import convert_to_seconds

        if self.login_wait_time is None:
            return
        if isinstance(self.login_wait_time, str):
            try:
                self.login_wait_time = convert_to_seconds(self.login_wait_time)
            except ValueError:
                raise ValueError(
                    f"Marketplace {self.name} login_wait_time {self.login_wait_time} is not recognized."
                )
        if not isinstance(self.login_wait_time, int) or self.login_wait_time < 0:
            raise ValueError(
                f"Marketplace {self.name} login_wait_time should be a non-negative number."
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
    ) -> Tuple[List[Listing], dict]:
        """Parse TractorHouse search results page

        TractorHouse embeds listing data as JSON in the HTML page.
        We extract this JSON data instead of scraping HTML elements.

        Returns:
            Tuple of (listings, page_info) where page_info contains pagination data
        """
        listings = []
        page_info = {}

        try:
            # Wait for page to load
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'warn')} Timeout waiting for page load"
                )

        # Get page content
        content = page.content()

        # Extract the JSON data containing listings
        # TractorHouse embeds listing data in a format like: "Listings": [...]
        import json

        # Find the Listings array in the embedded JSON using brace matching
        start_match = re.search(r'"Listings":\s*\[', content)
        if not start_match:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Parse]', 'warn')} Could not find Listings array in page"
                )
                # Save page to file for debugging
                debug_file = "tractorhouse_debug_page.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.debug(f"Saved page content to {debug_file} for debugging")
            return listings, page_info

        # Extract the complete array by matching braces
        start_pos = start_match.end() - 1  # Include the opening bracket
        depth = 0
        in_string = False
        escape = False
        end_pos = None

        for i in range(start_pos, min(start_pos + 10000000, len(content))):
            char = content[i]

            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char in '[{':
                    depth += 1
                elif char in ']}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break

        if end_pos is None:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Parse]', 'warn')} Could not find end of Listings array"
                )
            return listings, page_info

        listings_json_str = content[start_pos:end_pos]

        # Parse the listings array
        try:
            listings_data = json.loads(listings_json_str)

            if self.logger:
                self.logger.debug(
                    f"{hilight('[Parse]', 'info')} Found {len(listings_data)} listings in JSON data"
                )

            for listing_data in listings_data:
                try:
                    # Extract listing information from JSON
                    listing_id = str(listing_data.get("Id", ""))

                    # Build title from year, manufacturer, and model
                    year = listing_data.get("Year", "")
                    manufacturer = listing_data.get("ManufacturerName", "")
                    model = listing_data.get("Model", "")
                    title = listing_data.get("ListingTitle", f"{year} {manufacturer} {model}").strip()

                    # Extract price
                    price_val = listing_data.get("Price", 0)
                    retail_price = listing_data.get("RetailPrice", "")
                    if retail_price:
                        price = retail_price
                    elif price_val:
                        price = f"USD ${price_val:,.0f}"
                    else:
                        price = "$0"

                    # Extract location
                    location = listing_data.get("DealerLocation", "")

                    # Extract seller/dealer name
                    seller = listing_data.get("Dealer", "")

                    # Extract condition
                    condition = listing_data.get("Condition", "")

                    # Extract description (available in search results!)
                    description = listing_data.get("Description", "")

                    # Build URL from listing ID
                    # Format: /listing/for-sale/{id}/{year}-{manufacturer}-{model}-{category}
                    category_name = listing_data.get("CategoryName", "").lower().replace(" ", "-")
                    listing_type = listing_data.get("ListingType", "for-sale").replace(" ", "-")
                    url_slug = f"{year}-{manufacturer}-{model}".lower().replace(" ", "-")
                    post_url = f"https://www.tractorhouse.com/listing/{listing_type}/{listing_id}/{url_slug}-{category_name}"

                    # Extract image URL
                    # TractorHouse uses ListingImageModel which contains an array of image URLs
                    image_url = ""
                    image_model = listing_data.get("ListingImageModel", {})
                    if image_model and isinstance(image_model, dict):
                        image_urls = image_model.get("ImageUrl", [])
                        if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                            # Use the first image
                            image_url = image_urls[0]

                    # Fallback to other potential image fields
                    if not image_url:
                        image_url = listing_data.get("image", "")
                    if not image_url:
                        image_url = listing_data.get("ImageUrl", "")
                    if not image_url:
                        image_url = listing_data.get("Thumbnail", "")

                    # Validate essential data
                    if not title:
                        if self.logger:
                            self.logger.debug(
                                f"{hilight('[Parse]', 'warn')} No title for listing {listing_id}, skipping"
                            )
                        continue

                    listing = Listing(
                        marketplace="tractorhouse",
                        name=item_name,
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

                    listings.append(listing)

                except Exception as e:
                    if self.logger:
                        self.logger.debug(
                            f"{hilight('[Parse]', 'warn')} Failed to parse listing from JSON: {e}"
                        )
                    continue

        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Parse]', 'warn')} Failed to parse listings JSON: {e}"
                )
            return listings, page_info

        return listings, page_info

    def get_listing_details(
        self: "TractorHouseMarketplace",
        post_url: str,
        item_config: TractorHouseItemConfig,
        price: str | None = None,
        title: str | None = None,
    ) -> Tuple[Listing, bool]:
        """Fetch detailed information for a TractorHouse listing

        TractorHouse embeds listing data as JSON in the HTML page.
        We extract this JSON data instead of scraping HTML elements.
        """
        from .listing import Listing
        import json

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
            # Use existing page like Facebook does
            assert self.page is not None
            self.goto_url(post_url)

            # Simple delay like Facebook
            time.sleep(2)

            # Get page content
            content = self.page.content()

            # Extract listing ID from URL
            # Format: /listing/for-sale/{id}/{slug}
            listing_id_match = re.search(r'/listing/[^/]+/(\d+)/', post_url)
            listing_id = listing_id_match.group(1) if listing_id_match else ""

            # Extract the JSON data - look for listing object with matching ID
            # The detail page may have the listing data in various formats
            # Common pattern: "Id": 249472857, with surrounding listing data

            # Try to find a JSON object with the listing ID
            listing_data = None

            # Pattern 1: Look for complete listing object with our ID
            pattern = rf'{{\s*"[^"]*":\s*[^,]+,.*?"Id":\s*{listing_id}.*?}}'
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    obj_str = match.group(0)
                    # Find the complete JSON object by matching braces
                    # This is a simplified approach - we'll try to parse what we found
                    test_data = json.loads(obj_str)
                    if test_data.get("Id") == int(listing_id):
                        listing_data = test_data
                        break
                except:
                    continue

            # Pattern 2: If pattern 1 failed, look for key fields around the ID
            if not listing_data:
                # Try to extract individual fields from the page
                # Look for patterns like "ListingTitle": "...", "Price": ..., etc.
                title_match = re.search(r'"ListingTitle":\s*"([^"]*)"', content)
                price_match = re.search(r'"RetailPrice":\s*"([^"]*)"', content)
                price_val_match = re.search(r'"Price":\s*([\d.]+)', content)
                dealer_match = re.search(r'"Dealer":\s*"([^"]*)"', content)
                location_match = re.search(r'"DealerLocation":\s*"([^"]*)"', content)
                condition_match = re.search(r'"Condition":\s*"([^"]*)"', content)
                desc_match = re.search(r'"Description":\s*"((?:[^"\\]|\\.)*)"', content)
                year_match = re.search(r'"Year":\s*"([^"]*)"', content)
                mfr_match = re.search(r'"ManufacturerName":\s*"([^"]*)"', content)
                model_match = re.search(r'"Model":\s*"([^"]*)"', content)

                # Build a pseudo-listing object from individual matches
                listing_data = {
                    "Id": int(listing_id) if listing_id else 0,
                    "ListingTitle": title_match.group(1) if title_match else "",
                    "RetailPrice": price_match.group(1) if price_match else "",
                    "Price": float(price_val_match.group(1)) if price_val_match else 0,
                    "Dealer": dealer_match.group(1) if dealer_match else "",
                    "DealerLocation": location_match.group(1) if location_match else "",
                    "Condition": condition_match.group(1) if condition_match else "",
                    "Description": desc_match.group(1) if desc_match else "",
                    "Year": year_match.group(1) if year_match else "",
                    "ManufacturerName": mfr_match.group(1) if mfr_match else "",
                    "Model": model_match.group(1) if model_match else "",
                }

            # Extract data from the listing object
            if listing_data:
                # Extract title
                year = listing_data.get("Year", "")
                manufacturer = listing_data.get("ManufacturerName", "")
                model = listing_data.get("Model", "")
                title = listing_data.get("ListingTitle", f"{year} {manufacturer} {model}").strip()

                # Extract price
                price_val = listing_data.get("Price", 0)
                retail_price = listing_data.get("RetailPrice", "")
                if retail_price:
                    price = retail_price
                elif price_val:
                    price = f"USD ${price_val:,.0f}"
                else:
                    price = "$0"

                # Extract location
                location = listing_data.get("DealerLocation", "")

                # Extract seller
                seller = listing_data.get("Dealer", "")

                # Extract condition
                condition = listing_data.get("Condition", "")

                # Extract description
                description = listing_data.get("Description", "")
                # Unescape the description if it was JSON-encoded
                if description:
                    # Replace common escape sequences
                    description = description.replace(r'\r\n', '\n').replace(r'\n', '\n')
                    description = description.replace(r'\"', '"').replace(r'\\', '\\')

                # Extract image URL - look for image data
                # TractorHouse uses ListingImageModel which contains an array of image URLs
                image_url = ""
                image_model = listing_data.get("ListingImageModel", {})
                if image_model and isinstance(image_model, dict):
                    image_urls = image_model.get("ImageUrl", [])
                    if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                        # Use the first image
                        image_url = image_urls[0]

                # Fallback to other potential image fields
                if not image_url:
                    image_url = listing_data.get("image", "")
                if not image_url:
                    image_url = listing_data.get("ImageUrl", "")
                if not image_url:
                    image_url = listing_data.get("Thumbnail", "")
                if not image_url:
                    # Try to find ListingImageModel in page content with regex
                    img_model_match = re.search(r'"ListingImageModel":\s*\{[^}]*"ImageUrl":\s*\[\s*"([^"]*)"', content)
                    if img_model_match:
                        image_url = img_model_match.group(1)
                    else:
                        # Look for img tags as fallback
                        img_element = page.query_selector("img[src*='img.sm360.ca'], img[src*='sandhills.com'], img[src*='media.sandhills.com']")
                        if img_element:
                            image_url = img_element.get_attribute("src") or ""

            else:
                # Fallback: could not parse JSON, return with passed values
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Parse]', 'warn')} Could not extract listing data from detail page"
                    )
                title = normalized_title or "Unknown Equipment"
                price = normalized_price or "$0"
                location = ""
                seller = ""
                condition = ""
                description = ""
                image_url = ""

            # Final validation
            if not title:
                if self.logger:
                    self.logger.warning(
                        f"{hilight('[Parse Warning]', 'warn')} Failed to extract title from detail page: {post_url}"
                    )
                title = normalized_title or "Unknown Equipment"

            if not price or price == "$0":
                if self.logger:
                    self.logger.debug(
                        f"{hilight('[Parse]', 'warn')} No price found for listing {listing_id}"
                    )
                price = normalized_price or "$0"

            if not seller:
                seller = "TractorHouse Seller"

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

    def initialize(self: "TractorHouseMarketplace") -> None:
        """Initialize browser and allow manual interaction to bypass bot detection"""
        assert self.browser is not None
        from .utils import doze
        import humanize

        self.page = self.create_page(swap_proxy=True)

        # Navigate to TractorHouse homepage
        initial_url = "https://www.tractorhouse.com"
        self.goto_url(initial_url)

        # Give page time to load
        time.sleep(2)

        # Wait for manual interaction (solving captchas, etc.)
        login_wait_time = (
            60 if self.config.login_wait_time is None else self.config.login_wait_time
        )
        if login_wait_time > 0:
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Initialize]", "info")} Please complete any captchas in the browser window."""
                )
                self.logger.info(
                    f"""{hilight("[Initialize]", "info")} Waiting {humanize.naturaldelta(login_wait_time)}"""
                    + (
                        f""" or press {hilight("Esc")} when you are ready."""
                        if self.keyboard_monitor is not None
                        else ""
                    )
                )
            doze(login_wait_time, keyboard_monitor=self.keyboard_monitor)

    def search(
        self: "TractorHouseMarketplace", item: TractorHouseItemConfig
    ) -> Generator[Listing, None, None]:
        """Search TractorHouse for listings matching the item configuration"""
        if self.logger:
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching TractorHouse for {hilight(item.name)}"
            )

        # Ensure we have a page (initialize if first run)
        if not self.page:
            self.initialize()
            assert self.page is not None

        # Search each phrase
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.info(
                    f"{hilight('[Search]', 'info')} Searching for '{search_phrase}'"
                )

            # Build search URL for first page
            url = self.build_search_url(
                item, search_phrase, item.min_price, item.max_price
            )

            # Navigate to search results and handle pagination
            try:
                current_page = 1
                total_pages = 1  # Will be updated from JSON

                while current_page <= total_pages:
                    # Build URL with page parameter
                    if current_page == 1:
                        page_url = url
                    else:
                        # Add page parameter to URL
                        separator = "&" if "?" in url else "?"
                        page_url = f"{url}{separator}page={current_page}"

                    if self.logger:
                        self.logger.info(
                            f"{hilight('[Navigate]', 'info')} Fetching page {current_page} of {total_pages if total_pages > 1 else '?'}"
                        )

                    self.goto_url(page_url)

                    # Simple delay like Facebook does
                    time.sleep(5)

                    # Parse search results and extract pagination info
                    listings, page_info = self.parse_search_results(self.page, item.name)

                    # Update total pages from the first page response
                    if current_page == 1 and page_info:
                        total_pages = page_info.get("total_pages", 1)
                        if self.logger and total_pages > 1:
                            self.logger.info(
                                f"{hilight('[Pagination]', 'info')} Found {total_pages} pages of results"
                            )

                    if self.logger:
                        self.logger.info(
                            f"{hilight('[Found]', 'succ')} Found {len(listings)} listings on page {current_page}"
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

                    # Move to next page
                    current_page += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"{hilight('[Error]', 'fail')} Failed to process search results: {e}"
                    )
                raise
