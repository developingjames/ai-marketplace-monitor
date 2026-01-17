"""Purple Wave marketplace implementation."""

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
class PurpleWaveMarketItemCommonConfig(BaseConfig):
    """Purple Wave-specific configuration options."""

    zipcode: str | None = None
    miles: int | None = None

    def handle_zipcode(self: "PurpleWaveMarketItemCommonConfig") -> None:
        if self.zipcode is None:
            return
        if not isinstance(self.zipcode, str) or not self.zipcode.isdigit():
            raise ValueError(f"Item {hilight(self.name)} zipcode must be a 5-digit string.")
        if len(self.zipcode) != 5:
            raise ValueError(f"Item {hilight(self.name)} zipcode must be 5 digits.")

    def handle_miles(self: "PurpleWaveMarketItemCommonConfig") -> None:
        if self.miles is None:
            return
        if not isinstance(self.miles, int) or self.miles < 1:
            raise ValueError(f"Item {hilight(self.name)} miles must be a positive integer.")


@dataclass
class PurpleWaveMarketplaceConfig(MarketplaceConfig, PurpleWaveMarketItemCommonConfig):
    """Purple Wave marketplace configuration with zip code and radius support."""
    pass


@dataclass
class PurpleWaveItemConfig(ItemConfig, PurpleWaveMarketItemCommonConfig):
    """Purple Wave item configuration with zip code and radius support."""
    pass


class PurpleWaveSearchResultPage(WebPage):
    """Parser for Purple Wave search results page."""

    def get_listings(self: "PurpleWaveSearchResultPage") -> list[dict[str, str]]:
        """Extract all listing information from search results page.

        Returns:
            List of dicts containing listing data
        """
        listings = []

        # Find all auction items: <div id="{auction_id}-{item_id}" class="panel panel-default auction-item-compressed">
        # Or fallback to li.list-group-item if structure changed
        card_elements = self.page.query_selector_all('div[id][class*="auction-item"], li.list-group-item')

        if self.logger:
            self.logger.debug(f"Found {len(card_elements)} auction item elements on search page")

        for card_elem in card_elements:
            try:
                # Extract auction ID and item ID from id attribute
                elem_id = card_elem.get_attribute('id') or ''
                # Format: "{auction_id}-{item_id}"
                id_match = re.match(r'(\d+)-([A-Z]+\d+)', elem_id)
                if not id_match:
                    # Skip if no valid ID format
                    continue

                auction_id = id_match.group(1)
                item_id = id_match.group(2)
                combined_id = f"{auction_id}-{item_id}"

                # Find title from h3 tag
                title = ''
                title_elem = card_elem.query_selector('h3')
                if title_elem:
                    title = (title_elem.text_content() or '').strip()

                # Find URL from link
                url = ''
                link_elem = card_elem.query_selector('a[href*="/auction/"]')
                if link_elem:
                    url = link_elem.get_attribute('href') or ''

                # Find image from thumbnail
                image_url = ''
                img_elem = card_elem.query_selector('a.thumbnail img, img.img-responsive')
                if img_elem:
                    image_url = img_elem.get_attribute('src') or ''

                # Find current bid from bid-block
                current_bid = self.translator("**unspecified**")
                bid_elem = card_elem.query_selector('div.bid-block')
                if bid_elem:
                    bid_text = bid_elem.text_content() or ''
                    price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', bid_text)
                    if price_match:
                        current_bid = price_match.group(0)

                # Find location (City, ST format)
                location = self.translator("**unspecified**")
                card_text = card_elem.text_content() or ''
                location_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})\b', card_text)
                if location_match:
                    location = location_match.group(1)

                # Find time remaining (not always available on search results)
                time_remaining = ''
                time_match = re.search(r'(\d+)\s+(days?|hours?|minutes?)', card_text, re.IGNORECASE)
                if time_match:
                    time_remaining = f"{time_match.group(1)} {time_match.group(2)}"

                # Find bid count
                bid_count_match = re.search(r'(\d+)\s+bids?', card_text, re.IGNORECASE)
                bid_count = bid_count_match.group(1) if bid_count_match else ''

                # Only add if we have essential data
                if combined_id and url:
                    listings.append({
                        'auction_id': auction_id,
                        'item_id': item_id,
                        'id': combined_id,
                        'title': title,
                        'url': url,
                        'image': image_url,
                        'current_bid': current_bid,
                        'location': location,
                        'time_remaining': time_remaining,
                        'bid_count': bid_count,
                    })

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing auction item: {e}")
                continue

        return listings

    def has_next_page(self: "PurpleWaveSearchResultPage") -> bool:
        """Check if there is a next page available.

        Returns:
            True if next page exists, False otherwise
        """
        # Look for pagination button or link with "Next"
        # Material-UI pagination typically uses button elements
        pagination = self.page.query_selector('nav[aria-label*="pagination"]')
        if pagination:
            # Look for next button that is not disabled
            next_buttons = pagination.query_selector_all('button')
            for button in next_buttons:
                aria_label = button.get_attribute('aria-label') or ''
                if 'next' in aria_label.lower():
                    # Check if disabled
                    disabled = button.get_attribute('disabled')
                    if disabled is None:
                        return True
        return False


class PurpleWaveDetailPage(WebPage):
    """Parser for Purple Wave detail page."""

    def get_listing_details(self: "PurpleWaveDetailPage") -> dict[str, str]:
        """Extract detailed information from a listing detail page.

        Returns:
            Dict containing detailed listing data
        """
        details = {}

        try:
            # Extract title from h1 or page title
            title_elem = self.page.query_selector('h1')
            if title_elem:
                details['title'] = (title_elem.text_content() or '').strip()
            else:
                # Fallback to page title
                page_title = self.page.title()
                details['title'] = page_title.replace(' | Purple Wave', '').strip()

            # Get page text for regex searches
            page_text = self.page.text_content('body') or ''

            # Extract Item Details section
            # Wait for the item-details div to be present (it may be collapsed/expanded by JS)
            try:
                # Wait up to 5 seconds for the item details section to load
                self.page.wait_for_selector('div#item-details', timeout=5000)

                # Get the item details div
                item_details_elem = self.page.query_selector('div#item-details')
                if item_details_elem:
                    # Get the text content which includes all specs
                    item_details_text = item_details_elem.text_content() or ''

                    # Also get the header text (item ID + "Item Details")
                    header_elem = self.page.query_selector('a[href*="#item-details"]')
                    if header_elem:
                        header_text = header_elem.text_content() or ''
                        details['description'] = f"{header_text.strip()}\n{item_details_text.strip()}"
                    else:
                        details['description'] = item_details_text.strip()
                else:
                    # Fallback: try meta description
                    meta_desc = self.page.query_selector('meta[name="description"]')
                    if meta_desc:
                        details['description'] = (meta_desc.get_attribute('content') or '').strip()
                    else:
                        details['description'] = self.translator("**unspecified**")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error extracting item details: {e}")
                # Fallback: try meta description
                meta_desc = self.page.query_selector('meta[name="description"]')
                if meta_desc:
                    details['description'] = (meta_desc.get_attribute('content') or '').strip()
                else:
                    details['description'] = self.translator("**unspecified**")

            # Extract current bid (page_text already retrieved above)
            # Look for "Current Bid" or similar
            bid_match = re.search(r'Current\s+Bid[:\s]*\$?([\d,]+(?:\.\d{2})?)', page_text, re.IGNORECASE)
            if bid_match:
                details['current_bid'] = f"${bid_match.group(1)}"
            else:
                # Try to find any dollar amount
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', page_text)
                if price_match:
                    details['current_bid'] = price_match.group(0)

            # Extract bid count
            bid_count_match = re.search(r'(\d+)\s+Bids?', page_text, re.IGNORECASE)
            if bid_count_match:
                details['bid_count'] = bid_count_match.group(1)

            # Extract location
            # Look for location with city, state format
            location_match = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2}(?:\s+\d{5})?)', page_text)
            if location_match:
                details['location'] = location_match.group(1)
            else:
                details['location'] = self.translator("**unspecified**")

            # Extract seller/auctioneer
            # Look for seller or auctioneer name
            seller_elem = self.page.query_selector('a[href*="/seller/"], span[class*="seller"], div[class*="auctioneer"]')
            if seller_elem:
                details['seller'] = (seller_elem.text_content() or '').strip()

            if 'seller' not in details or not details['seller']:
                details['seller'] = "Purple Wave"

            # Extract auction ID and item ID from URL
            url = self.page.url
            auction_match = re.search(r'/auction/(\d+)/', url)
            item_match = re.search(r'/item/(\d+)', url)

            if auction_match:
                details['auction_id'] = auction_match.group(1)
            if item_match:
                details['item_id'] = item_match.group(1)

            # Extract lot number if present
            lot_match = re.search(r'Lot\s+#?(\d+)', page_text, re.IGNORECASE)
            if lot_match:
                details['lot_number'] = lot_match.group(1)

            # Extract time remaining
            time_match = re.search(r'(\d+)\s+(days?|hours?|minutes?)\s+remaining', page_text, re.IGNORECASE)
            if time_match:
                details['time_remaining'] = f"{time_match.group(1)} {time_match.group(2)}"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing Purple Wave detail page: {e}")

        return details


class PurpleWaveMarketplace(Marketplace):
    """Purple Wave marketplace implementation."""

    name = "purplewave"
    ItemConfigClass = PurpleWaveItemConfig

    def __init__(
        self: "PurpleWaveMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["PurpleWaveMarketplace"], **kwargs: Any) -> PurpleWaveMarketplaceConfig:
        return PurpleWaveMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["PurpleWaveMarketplace"], **kwargs: Any) -> PurpleWaveItemConfig:
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return PurpleWaveItemConfig(**filtered_kwargs)

    def _build_search_url(
        self: "PurpleWaveMarketplace",
        query: str,
        page: int = 1,
        zipcode: str | None = None,
        miles: int | None = None
    ) -> str:
        """Build search URL for Purple Wave.

        Args:
            query: Search term
            page: Page number (1-indexed)
            zipcode: Optional zip code for location-based search
            miles: Optional radius in miles

        Returns:
            Complete search URL
        """
        base_url = "https://www.purplewave.com/search"
        encoded_query = quote(query)

        params = [
            f"q={encoded_query}",
            f"page={page}",
            "perPage=100"
        ]

        if zipcode:
            params.append(f"zipCode={zipcode}")
        if miles:
            params.append(f"radius={miles}")

        return f"{base_url}?{'&'.join(params)}"

    def check_listing(
        self: "PurpleWaveMarketplace",
        item: PurpleWaveItemConfig,
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

    def search(self: "PurpleWaveMarketplace", item: PurpleWaveItemConfig) -> Generator[Listing, None, None]:
        """Search Purple Wave for items matching the configuration.

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
                f"{hilight('[Search]', 'info')} Searching Purple Wave for {hilight(item.name)}{location_info}"
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
                time.sleep(3)  # Extra time for Material-UI to render

                # Parse search results
                search_page = PurpleWaveSearchResultPage(self.page, self.translator, self.logger)
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
                    full_url = listing_data['url'] if listing_data['url'].startswith('http') else f"https://www.purplewave.com{listing_data['url']}"

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
                    time.sleep(2)  # Extra time for Material-UI

                    detail_page = PurpleWaveDetailPage(self.page, self.translator, self.logger)
                    details = detail_page.get_listing_details()

                    # Create Listing object
                    listing = Listing(
                        marketplace=self.name,
                        name=item.name,
                        id=listing_data['id'],
                        title=details.get('title', listing_data['title']),
                        image=listing_data['image'],
                        price=details.get('current_bid', listing_data['current_bid']),
                        post_url=full_url,
                        location=details.get('location', listing_data['location']),
                        seller=details.get('seller', "Purple Wave"),
                        condition=self.translator("**unspecified**"),
                        description=details.get('description', self.translator("**unspecified**")),
                        auction_end_time=None,
                        time_remaining=details.get('time_remaining', listing_data.get('time_remaining', '')),
                        bid_count=int(details['bid_count']) if 'bid_count' in details else None,
                        lot_number=details.get('lot_number'),
                        auction_id=details.get('auction_id', listing_data['auction_id']),
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
