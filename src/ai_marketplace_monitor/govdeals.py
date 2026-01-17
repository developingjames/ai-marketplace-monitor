"""GovDeals marketplace implementation."""

import re
import time
from dataclasses import dataclass
from logging import Logger
from typing import Any, Generator, Type
from urllib.parse import quote

from playwright.sync_api import Browser, Page

from .listing import Listing
from .marketplace import ItemConfig, Marketplace, MarketplaceConfig, WebPage
from .utils import (
    BaseConfig,
    CounterItem,
    KeyboardMonitor,
    counter,
    hilight,
    is_substring,
)


@dataclass
class GovDealsMarketItemCommonConfig(BaseConfig):
    """GovDeals-specific configuration options."""

    zipcode: str | None = None
    miles: int | None = None

    def handle_zipcode(self: "GovDealsMarketItemCommonConfig") -> None:
        if self.zipcode is None:
            return
        if not isinstance(self.zipcode, str) or not self.zipcode.isdigit():
            raise ValueError(f"Item {hilight(self.name)} zipcode must be a 5-digit string.")
        if len(self.zipcode) != 5:
            raise ValueError(f"Item {hilight(self.name)} zipcode must be 5 digits.")

    def handle_miles(self: "GovDealsMarketItemCommonConfig") -> None:
        if self.miles is None:
            return
        if not isinstance(self.miles, int) or self.miles < 1:
            raise ValueError(f"Item {hilight(self.name)} miles must be a positive integer.")


@dataclass
class GovDealsMarketplaceConfig(MarketplaceConfig, GovDealsMarketItemCommonConfig):
    """GovDeals marketplace configuration with zip code and radius support."""
    pass


@dataclass
class GovDealsItemConfig(ItemConfig, GovDealsMarketItemCommonConfig):
    """GovDeals item configuration with zip code and radius support."""
    pass


class GovDealsSearchResultPage(WebPage):
    """Parser for GovDeals search results page."""

    def get_listings(self: "GovDealsSearchResultPage") -> list[dict[str, str]]:
        """Extract all listing information from search results page.

        Returns:
            List of dicts containing listing data
        """
        listings = []

        # Find all asset elements: <div id="asset-{item_id}-{seller_id}">
        # Use a more flexible selector to find all divs with id starting with "asset-"
        asset_elements = self.page.query_selector_all('div[id^="asset-"]')

        if self.logger:
            self.logger.debug(f"Found {len(asset_elements)} asset elements on search page")

        for asset_elem in asset_elements:
            try:
                # Extract asset ID and seller ID from div id
                div_id = asset_elem.get_attribute('id') or ''
                # Format: "asset-{item_id}-{seller_id}"
                id_match = re.match(r'asset-(\d+)-(\d+)', div_id)
                if not id_match:
                    continue

                item_id = id_match.group(1)
                seller_id = id_match.group(2)

                # Find title from card-title or image alt
                title = ''
                title_elem = asset_elem.query_selector('p.card-title a')
                if title_elem:
                    title = title_elem.get_attribute('title') or ''

                # Find URL
                url = ''
                link_elem = asset_elem.query_selector('a[name="lnkAssetDetails"]')
                if link_elem:
                    url = link_elem.get_attribute('href') or ''

                # Find image
                image_url = ''
                img_elem = asset_elem.query_selector('img.card-move, img.w-auto')
                if img_elem:
                    image_url = img_elem.get_attribute('src') or ''

                # Find current bid/price
                current_bid = self.translator("**unspecified**")
                price_elem = asset_elem.query_selector('p.card-amount')
                if price_elem:
                    # The display text is like "USD 2,000.00"
                    price_text = price_elem.text_content() or ''
                    current_bid = price_text.strip()

                # Find location
                location = self.translator("**unspecified**")
                loc_elem = asset_elem.query_selector('p[name="pAssetLocation"]')
                if loc_elem:
                    location = (loc_elem.text_content() or '').strip()

                # Only add if we have essential data
                if item_id and seller_id and url:
                    listings.append({
                        'item_id': item_id,
                        'seller_id': seller_id,
                        'id': f"{seller_id}/{item_id}",  # Combined ID
                        'title': title,
                        'url': url,
                        'image': image_url,
                        'current_bid': current_bid,
                        'location': location,
                    })

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing asset element: {e}")
                continue

        return listings

    def has_next_page(self: "GovDealsSearchResultPage") -> bool:
        """Check if there is a next page available.

        Returns:
            True if next page exists, False otherwise
        """
        # Look for pagination with "Next" link
        pagination = self.page.query_selector('ul.pagination')
        if pagination:
            # Check for "Next" text that is not disabled
            next_items = pagination.query_selector_all('li')
            for item in next_items:
                text = item.text_content() or ''
                if 'Next' in text or 'next' in text.lower():
                    # Check if it's not disabled
                    classes = item.get_attribute('class') or ''
                    if 'disabled' not in classes:
                        return True
        return False


class GovDealsDetailPage(WebPage):
    """Parser for GovDeals detail page."""

    def get_listing_details(self: "GovDealsDetailPage") -> dict[str, str]:
        """Extract detailed information from a listing detail page.

        Returns:
            Dict containing detailed listing data
        """
        details = {}

        try:
            # Extract title from h1 or page title
            page_title = self.page.title()
            details['title'] = page_title.replace(' | GovDeals', '').strip()

            # Extract description from product-details or subject-info divs
            desc_elements = self.page.query_selector_all('div.subject-info')
            description_parts = []
            for elem in desc_elements:
                text = elem.text_content() or ''
                if text.strip() and len(text.strip()) > 10:
                    description_parts.append(text.strip())

            if description_parts:
                details['description'] = ' '.join(description_parts)
            else:
                details['description'] = self.translator("**unspecified**")

            # Extract minimum bid
            page_text = self.page.text_content('body') or ''
            min_bid_match = re.search(r'Minimum Bid is USD ([\d,\.]+)', page_text)
            if min_bid_match:
                details['min_bid'] = f"USD {min_bid_match.group(1)}"

            # Extract current bid (may not always be present)
            if 'Current Bid' in page_text:
                current_bid_match = re.search(r'Current Bid[:\s]*USD ([\d,\.]+)', page_text)
                if current_bid_match:
                    details['current_bid'] = f"USD {current_bid_match.group(1)}"

            # Extract bid count
            bid_count_match = re.search(r'(\d+)\s+Bids?', page_text)
            if bid_count_match:
                details['bid_count'] = bid_count_match.group(1)

            # Extract location
            # Look for location with city, state, country format
            location_match = re.search(r'([A-Z][a-z]+,\s*[A-Z][a-z]+,\s*[A-Z]+)', page_text)
            if location_match:
                details['location'] = location_match.group(1)
            else:
                details['location'] = self.translator("**unspecified**")

            # Extract seller/agency from URL or page
            url = self.page.url
            seller_match = re.search(r'/asset/(\d+)/', url)
            if seller_match:
                details['seller_id'] = seller_match.group(1)

            # Look for seller/agency name
            # Often in breadcrumb or header
            seller_elem = self.page.query_selector('a[href*="/buyer/"]')
            if seller_elem:
                details['seller'] = (seller_elem.text_content() or '').strip()

            if 'seller' not in details:
                details['seller'] = "GovDeals"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing GovDeals detail page: {e}")

        return details


class GovDealsMarketplace(Marketplace):
    """GovDeals marketplace implementation."""

    name = "govdeals"
    ItemConfigClass = GovDealsItemConfig

    def __init__(
        self: "GovDealsMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["GovDealsMarketplace"], **kwargs: Any) -> GovDealsMarketplaceConfig:
        return GovDealsMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["GovDealsMarketplace"], **kwargs: Any) -> GovDealsItemConfig:
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return GovDealsItemConfig(**filtered_kwargs)

    def _build_search_url(
        self: "GovDealsMarketplace",
        query: str,
        page: int = 1,
        zipcode: str | None = None,
        miles: int | None = None
    ) -> str:
        """Build search URL for GovDeals.

        Args:
            query: Search term
            page: Page number (1 for first page, 2+ for subsequent)
            zipcode: Optional zip code for location-based search
            miles: Optional radius in miles

        Returns:
            Complete search URL
        """
        encoded_query = quote(query)

        # Page 1 uses different URL pattern than page 2+
        if page == 1:
            base_url = "https://www.govdeals.com/en/search"
            params = [f"kWord={encoded_query}"]

            if zipcode:
                params.append(f"zipcode={zipcode}")
            if miles:
                params.append(f"miles={miles}")

            return f"{base_url}?{'&'.join(params)}"
        else:
            # Page 2+ uses /en/search/filters with pn parameter
            base_url = "https://www.govdeals.com/en/search/filters"
            params = [
                f"kWord={encoded_query}",
                f"pn={page}",
                "so=",
                "sf=bestfit",
                "ps=24"
            ]

            if zipcode:
                params.append(f"zipcode={zipcode}")
            if miles:
                params.append(f"miles={miles}")

            return f"{base_url}?{'&'.join(params)}"

    def check_listing(
        self: "GovDealsMarketplace",
        item: GovDealsItemConfig,
        listing: Listing,
    ) -> bool:
        """Check if listing matches item criteria.

        Args:
            item: Item configuration
            listing: Listing to check

        Returns:
            True if listing passes filters, False otherwise
        """
        # Check antikeywords
        if item.antikeywords:
            combined_text = f"{listing.title} {listing.description}".lower()
            for antikeyword in item.antikeywords:
                if is_substring(antikeyword, combined_text):
                    if self.logger:
                        self.logger.debug(
                            f"{hilight('[Excluded]', 'warning')} {listing.title[:50]}... "
                            f"(matched antikeyword: {antikeyword})"
                        )
                    counter.increment(CounterItem.EXCLUDED_LISTING, item.name)
                    return False

        # Check keywords
        if item.keywords:
            combined_text = f"{listing.title} {listing.description}".lower()
            keyword_match = False
            for keyword in item.keywords:
                if is_substring(keyword, combined_text):
                    keyword_match = True
                    break

            if not keyword_match:
                if self.logger:
                    self.logger.debug(
                        f"{hilight('[Excluded]', 'warning')} {listing.title[:50]}... "
                        f"(no keyword match)"
                    )
                counter.increment(CounterItem.EXCLUDED_LISTING, item.name)
                return False

        return True

    def search(self: "GovDealsMarketplace", item: GovDealsItemConfig) -> Generator[Listing, None, None]:
        """Search GovDeals for items matching the configuration.

        Args:
            item: Item configuration with search phrases and filters

        Yields:
            Listing objects that match the criteria
        """
        assert self.browser is not None
        counter.increment(CounterItem.SEARCH_PERFORMED, item.name)

        if self.logger:
            location_info = ""
            if item.zipcode and item.miles:
                location_info = f" within {item.miles} miles of {item.zipcode}"
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching GovDeals for {hilight(item.name)}{location_info}"
            )

        self.page = self.create_page()

        # Track seen listings
        found: dict[str, bool] = {}

        # Iterate through search phrases
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.debug(f"Searching for phrase: {hilight(search_phrase)}")

            page_num = 1

            while True:
                # Build and navigate to search URL
                search_url = self._build_search_url(
                    search_phrase,
                    page_num,
                    item.zipcode,
                    item.miles
                )

                if self.logger:
                    self.logger.debug(f"Fetching page {page_num}: {search_url}")

                self.goto_url(search_url)
                time.sleep(2)

                # Parse search results
                search_page = GovDealsSearchResultPage(self.page, self.translator, self.logger)
                listings_data = search_page.get_listings()

                if not listings_data:
                    if self.logger:
                        self.logger.debug(f"No listings found on page {page_num}")
                    break

                if self.logger:
                    self.logger.debug(f"Found {len(listings_data)} listings on page {page_num}")

                # Process each listing
                for listing_data in listings_data:
                    counter.increment(CounterItem.LISTING_EXAMINED, item.name)

                    # Normalize URL for deduplication
                    normalized_url = listing_data['url'].split('?')[0]

                    if normalized_url in found:
                        continue

                    found[normalized_url] = True

                    # Get full details from detail page
                    counter.increment(CounterItem.LISTING_QUERY, item.name)

                    # Construct full URL
                    full_url = listing_data['url'] if listing_data['url'].startswith('http') else f"https://www.govdeals.com{listing_data['url']}"

                    # Check cache
                    cached_listing = Listing.from_cache(full_url)

                    if cached_listing:
                        if self.logger:
                            self.logger.debug(f"Using cached listing for {listing_data['title'][:50]}")

                        if self.check_listing(item, cached_listing):
                            yield cached_listing
                        continue

                    # Fetch detail page
                    self.goto_url(full_url)
                    time.sleep(1)

                    detail_page = GovDealsDetailPage(self.page, self.translator, self.logger)
                    details = detail_page.get_listing_details()

                    # Create Listing object
                    listing = Listing(
                        marketplace=self.name,
                        name=item.name,
                        id=listing_data['id'],
                        title=details.get('title', listing_data['title']),
                        image=listing_data['image'],
                        price=details.get('current_bid', details.get('min_bid', listing_data['current_bid'])),
                        post_url=full_url,
                        location=details.get('location', listing_data['location']),
                        seller=details.get('seller', "GovDeals"),
                        condition=self.translator("**unspecified**"),
                        description=details.get('description', self.translator("**unspecified**")),
                        auction_end_time=None,
                        time_remaining=None,
                        bid_count=int(details['bid_count']) if 'bid_count' in details else None,
                        lot_number=None,
                        auction_id=None,
                    )

                    # Cache the listing
                    listing.to_cache(full_url)

                    # Check if listing passes filters
                    if self.check_listing(item, listing):
                        yield listing

                # Check for next page
                if search_page.has_next_page():
                    page_num += 1
                    if self.logger:
                        self.logger.debug(f"Moving to page {page_num}")
                else:
                    if self.logger:
                        self.logger.debug("No more pages available")
                    break
