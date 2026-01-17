"""Proxibid marketplace implementation."""

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
    CounterItem,
    KeyboardMonitor,
    counter,
    hilight,
    is_substring,
)


@dataclass
class ProxibidMarketplaceConfig(MarketplaceConfig):
    """Proxibid marketplace configuration.

    No additional marketplace-specific config needed beyond base MarketplaceConfig.
    """
    pass


@dataclass
class ProxibidItemConfig(ItemConfig):
    """Proxibid item configuration.

    No additional item-specific config needed beyond base ItemConfig.
    """
    pass


class ProxibidSearchResultPage(WebPage):
    """Parser for Proxibid search results page."""

    def get_listings(self: "ProxibidSearchResultPage") -> list[dict[str, str]]:
        """Extract all listing information from search results page.

        Returns:
            List of dicts containing listing data
        """
        listings = []

        # Find all gallery card elements
        gallery_cards = self.page.query_selector_all('div.gallery-card')

        if self.logger:
            self.logger.debug(f"Found {len(gallery_cards)} gallery cards on search page")

        for card in gallery_cards:
            try:
                # Find the clickable link with lot details
                link_elem = card.query_selector('a.clickable')
                if not link_elem:
                    continue

                # Extract URL and lot ID
                url = link_elem.get_attribute('href') or ''
                lot_id = ''
                if 'lid=' in url:
                    lid_match = re.search(r'lid=(\d+)', url)
                    if lid_match:
                        lot_id = lid_match.group(1)

                # Extract title
                title = ''
                title_elem = card.query_selector('div.lotTitle')
                if title_elem:
                    title = title_elem.get_attribute('title') or ''
                    if not title:
                        title = (title_elem.text_content() or '').strip()

                # Extract image
                image_url = ''
                img_elem = card.query_selector('img.itemImage')
                if img_elem:
                    image_url = img_elem.get_attribute('src') or ''

                # Extract current price
                current_price = self.translator("**unspecified**")
                price_elem = card.query_selector('span.price_dollar_val')
                if price_elem:
                    current_price = (price_elem.text_content() or '').strip()

                # Extract time remaining
                time_remaining = ''
                countdown_elem = card.query_selector('div.countdownTimer')
                if countdown_elem:
                    time_text = (countdown_elem.text_content() or '').strip()
                    # Extract days and hours
                    days_match = re.search(r'(\d+)\s+days?', time_text)
                    hours_match = re.search(r'(\d+)\s+hours?', time_text)

                    time_parts = []
                    if days_match:
                        time_parts.append(f"{days_match.group(1)} days")
                    if hours_match:
                        time_parts.append(f"{hours_match.group(1)} hours")

                    time_remaining = ' '.join(time_parts)

                # Only add if we have essential data
                if lot_id and url:
                    listings.append({
                        'id': lot_id,
                        'title': title,
                        'url': url,
                        'image': image_url,
                        'current_price': current_price,
                        'time_remaining': time_remaining,
                    })

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing gallery card: {e}")
                continue

        return listings

    def has_next_page(self: "ProxibidSearchResultPage") -> bool:
        """Check if there is a next page available.

        Returns:
            True if next page exists, False otherwise
        """
        # Look for pagination with page numbers
        pagination = self.page.query_selector('div#pageNumbersDiv')
        if pagination:
            # Check for active page and see if there are more pages
            page_items = pagination.query_selector_all('li.pageNumber')
            if page_items:
                # If there are page numbers after the active one, there's a next page
                for i, item in enumerate(page_items):
                    classes = item.get_attribute('class') or ''
                    if 'active' in classes:
                        # Check if there's a page after this one
                        if i < len(page_items) - 1:
                            return True
                        break
        return False


class ProxibidDetailPage(WebPage):
    """Parser for Proxibid detail page."""

    def get_listing_details(self: "ProxibidDetailPage") -> dict[str, str]:
        """Extract detailed information from a listing detail page.

        Returns:
            Dict containing detailed listing data
        """
        details = {}

        try:
            # Extract title
            title_elem = self.page.query_selector('span#moreInfoLotTitle')
            if title_elem:
                details['title'] = (title_elem.text_content() or '').strip()
            else:
                # Fallback to page title
                page_title = self.page.title()
                details['title'] = page_title.split('|')[0].strip()

            # Extract lot number
            lot_num_elem = self.page.query_selector('span#moreInfoLotNumber')
            if lot_num_elem:
                details['lot_number'] = (lot_num_elem.text_content() or '').strip()

            # Extract lot ID from hidden input
            page_html = self.page.content()
            lot_id_match = re.search(r'id="LotStatus:(\d+)"', page_html)
            if lot_id_match:
                details['lot_id'] = lot_id_match.group(1)

            # Extract seller/auctioneer name
            seller_elem = self.page.query_selector('span#moreInfoSellerName')
            if seller_elem:
                details['seller'] = (seller_elem.text_content() or '').strip()
            else:
                details['seller'] = "Proxibid"

            # Extract event name
            event_elem = self.page.query_selector('span#moreInfoEventName')
            if event_elem:
                details['event_name'] = (event_elem.text_content() or '').strip()

            # Extract description
            desc_elem = self.page.query_selector('div#lotDescription')
            if desc_elem:
                details['description'] = (desc_elem.text_content() or '').strip()
            else:
                details['description'] = self.translator("**unspecified**")

            # Extract location (City, ST ZIP format)
            page_text = self.page.text_content('body') or ''
            location_match = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2}\s*\d{5})', page_text)
            if location_match:
                details['location'] = location_match.group(1)
            else:
                # Try City, ST format
                location_match2 = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2})\b', page_text)
                if location_match2:
                    details['location'] = location_match2.group(1)
                else:
                    details['location'] = self.translator("**unspecified**")

            # Extract current bid (if visible)
            # Look for price information in the bid section
            bid_elem = self.page.query_selector('div.lotDetailBidInfo')
            if bid_elem:
                bid_text = bid_elem.text_content() or ''
                # Look for dollar amounts
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', bid_text)
                if price_match:
                    details['current_bid'] = price_match.group(0)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing Proxibid detail page: {e}")

        return details


class ProxibidMarketplace(Marketplace):
    """Proxibid marketplace implementation."""

    name = "proxibid"
    ItemConfigClass = ProxibidItemConfig

    def __init__(
        self: "ProxibidMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["ProxibidMarketplace"], **kwargs: Any) -> ProxibidMarketplaceConfig:
        return ProxibidMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["ProxibidMarketplace"], **kwargs: Any) -> ProxibidItemConfig:
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return ProxibidItemConfig(**filtered_kwargs)

    def _build_search_url(self: "ProxibidMarketplace", query: str, start: int = 1) -> str:
        """Build search URL for Proxibid.

        Args:
            query: Search term
            start: Start position (1-indexed, increments by length)

        Returns:
            Complete search URL with hash fragment
        """
        # Complex URL with hash fragment
        # Base URL with initial parameters
        base_url = "https://www.proxibid.com/asp/SearchAdvanced_i.asp"
        encoded_query = quote(query)

        # Initial query parameters
        params = [
            f"searchTerm={encoded_query}",
            "category=all%20categories",
        ]

        # Hash fragment parameters (the actual search parameters)
        hash_params = [
            f"search={encoded_query}",
            "type=lot",
            "sort=relevance",
            "view=gallery",
            "length=100",
            f"start={start}",
            "refine=Selling%20Format|Timed+Events"
        ]

        return f"{base_url}?{'&'.join(params)}#{'&'.join(hash_params)}"

    def check_listing(
        self: "ProxibidMarketplace",
        item: ProxibidItemConfig,
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

    def search(self: "ProxibidMarketplace", item: ProxibidItemConfig) -> Generator[Listing, None, None]:
        """Search Proxibid for items matching the configuration.

        Args:
            item: Item configuration with search phrases and filters

        Yields:
            Listing objects that match the criteria
        """
        assert self.browser is not None
        counter.increment(CounterItem.SEARCH_PERFORMED, item.name)

        if self.logger:
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching Proxibid for {hilight(item.name)}"
            )

        self.page = self.create_page()

        # Track seen listings
        found: dict[str, bool] = {}

        # Iterate through search phrases
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.debug(f"Searching for phrase: {hilight(search_phrase)}")

            start = 1  # Proxibid uses 1-indexed start position

            while True:
                # Build and navigate to search URL
                search_url = self._build_search_url(search_phrase, start)

                if self.logger:
                    self.logger.debug(f"Fetching results starting at {start}: {search_url}")

                self.goto_url(search_url)
                time.sleep(3)  # Proxibid may need extra time for JavaScript rendering

                # Parse search results
                search_page = ProxibidSearchResultPage(self.page, self.translator, self.logger)
                listings_data = search_page.get_listings()

                if not listings_data:
                    if self.logger:
                        self.logger.debug(f"No listings found starting at position {start}")
                    break

                if self.logger:
                    self.logger.debug(f"Found {len(listings_data)} listings starting at position {start}")

                # Process each listing
                for listing_data in listings_data:
                    counter.increment(CounterItem.LISTING_EXAMINED, item.name)

                    # Normalize URL for deduplication
                    normalized_url = listing_data['url'].split('?')[0].split('#')[0]

                    if normalized_url in found:
                        continue

                    found[normalized_url] = True

                    # Get full details from detail page
                    counter.increment(CounterItem.LISTING_QUERY, item.name)

                    # Construct full URL
                    full_url = listing_data['url'] if listing_data['url'].startswith('http') else f"https://www.proxibid.com{listing_data['url']}"

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
                    time.sleep(2)  # Extra time for JavaScript

                    detail_page = ProxibidDetailPage(self.page, self.translator, self.logger)
                    details = detail_page.get_listing_details()

                    # Create Listing object
                    listing = Listing(
                        marketplace=self.name,
                        name=item.name,
                        id=listing_data['id'],
                        title=details.get('title', listing_data['title']),
                        image=listing_data['image'],
                        price=details.get('current_bid', listing_data['current_price']),
                        post_url=full_url,
                        location=details.get('location', self.translator("**unspecified**")),
                        seller=details.get('seller', "Proxibid"),
                        condition=self.translator("**unspecified**"),
                        description=details.get('description', self.translator("**unspecified**")),
                        auction_end_time=None,
                        time_remaining=listing_data.get('time_remaining', ''),
                        bid_count=None,
                        lot_number=details.get('lot_number'),
                        auction_id=None,
                    )

                    # Cache the listing
                    listing.to_cache(full_url)

                    # Check if listing passes filters
                    if self.check_listing(item, listing):
                        yield listing

                # Check for next page
                # Proxibid uses length=100, so if we got 100 results, there might be more
                if len(listings_data) >= 100 and search_page.has_next_page():
                    start += 100  # Increment by length
                    if self.logger:
                        self.logger.debug(f"Moving to start position {start}")
                else:
                    if self.logger:
                        self.logger.debug("No more pages available")
                    break
