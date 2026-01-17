"""Auction Ohio marketplace implementation."""

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
    Translator,
    counter,
    hilight,
    is_substring,
)


@dataclass
class AuctionOhioMarketplaceConfig(MarketplaceConfig):
    """Auction Ohio marketplace configuration.

    No additional marketplace-specific config needed beyond base MarketplaceConfig.
    """
    pass


@dataclass
class AuctionOhioItemConfig(ItemConfig):
    """Auction Ohio item configuration.

    No additional item-specific config needed beyond base ItemConfig.
    """
    pass


class AuctionOhioSearchResultPage(WebPage):
    """Parser for Auction Ohio search results page."""

    def get_listings(self: "AuctionOhioSearchResultPage") -> list[dict[str, str]]:
        """Extract all listing information from search results page.

        Returns:
            List of dicts containing listing data (id, title, url, image, etc.)
        """
        listings = []

        # Find all lot elements: <div class="lot" data-lotid="..." data-lotnumber="...">
        lot_elements = self.page.query_selector_all('div.lot[data-lotid]')

        if self.logger:
            self.logger.debug(f"Found {len(lot_elements)} lot elements on search page")

        for lot_elem in lot_elements:
            try:
                # Extract lot ID and lot number from data attributes
                lot_id = lot_elem.get_attribute('data-lotid') or ''
                lot_number = lot_elem.get_attribute('data-lotnumber') or ''

                # Find the link to detail page
                link_elem = lot_elem.query_selector('a.imgContainer')
                url = ''
                if link_elem:
                    url = link_elem.get_attribute('href') or ''

                # Extract title from image alt attribute
                img_elem = lot_elem.query_selector('img.lot-img')
                title = ''
                image_url = ''
                if img_elem:
                    title = img_elem.get_attribute('alt') or ''
                    image_url = img_elem.get_attribute('src') or ''

                # Extract current bid from winning-bid-amount div
                bid_elem = lot_elem.query_selector('div.winning-bid-amount')
                current_bid = self.translator("**unspecified**")
                if bid_elem:
                    bid_text = bid_elem.text_content() or ''
                    current_bid = bid_text.strip()

                # Extract time remaining (hours and minutes)
                time_remaining = ''
                hours_elem = lot_elem.query_selector('span.hours > span')
                minutes_elem = lot_elem.query_selector('span.minutes > span')

                if hours_elem and minutes_elem:
                    hours = hours_elem.text_content() or '0'
                    minutes = minutes_elem.text_content() or '0'
                    time_remaining = f"{hours} Hours {minutes} Minutes"
                elif hours_elem:
                    hours = hours_elem.text_content() or '0'
                    time_remaining = f"{hours} Hours"

                # Only add if we have essential data
                if lot_id and url:
                    listings.append({
                        'id': lot_id,
                        'lot_number': lot_number,
                        'title': title,
                        'url': url,
                        'image': image_url,
                        'current_bid': current_bid,
                        'time_remaining': time_remaining,
                    })

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing lot element: {e}")
                continue

        return listings

    def has_next_page(self: "AuctionOhioSearchResultPage") -> bool:
        """Check if there is a next page available.

        Returns:
            True if next page exists, False otherwise
        """
        # Look for "Next Page" link that is not disabled
        next_button = self.page.query_selector('th.rdtNext')
        if next_button:
            # Check if it contains "Next Page" text
            text = next_button.text_content() or ''
            if 'Next' in text or 'next' in text.lower():
                return True
        return False


class AuctionOhioDetailPage(WebPage):
    """Parser for Auction Ohio detail page."""

    def get_listing_details(self: "AuctionOhioDetailPage") -> dict[str, str]:
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
                details['title'] = page_title.replace(' - Auction Ohio', '').strip()

            # Extract description from description div
            desc_elem = self.page.query_selector('div.description')
            if desc_elem:
                desc_text = desc_elem.text_content() or ''
                details['description'] = desc_text.strip()
            else:
                details['description'] = self.translator("**unspecified**")

            # Extract current bid
            bid_elem = self.page.query_selector('div.currentBid')
            if bid_elem:
                bid_text = bid_elem.text_content() or ''
                # Extract just the dollar amount
                bid_match = re.search(r'\$[\d,\.]+', bid_text)
                if bid_match:
                    details['current_bid'] = bid_match.group(0)
                else:
                    details['current_bid'] = bid_text.strip()
            else:
                details['current_bid'] = self.translator("**unspecified**")

            # Extract time remaining
            time_remaining = ''
            days_elem = self.page.query_selector('span.days > span')
            hours_elem = self.page.query_selector('span.hours > span')
            minutes_elem = self.page.query_selector('span.minutes > span')

            time_parts = []
            if days_elem:
                days = days_elem.text_content() or '0'
                time_parts.append(f"{days} Days")
            if hours_elem:
                hours = hours_elem.text_content() or '0'
                time_parts.append(f"{hours} Hours")
            if minutes_elem:
                minutes = minutes_elem.text_content() or '0'
                time_parts.append(f"{minutes} Minutes")

            details['time_remaining'] = ' '.join(time_parts) if time_parts else ''

            # Extract location
            location_elem = self.page.query_selector('div.value')
            if location_elem:
                parent = location_elem.evaluate_handle('el => el.parentElement')
                if parent:
                    parent_text = parent.as_element().text_content() or ''
                    if 'Location:' in parent_text:
                        details['location'] = (location_elem.text_content() or '').strip()

            if 'location' not in details:
                # Try alternate method - look for "City, State" pattern
                page_text = self.page.text_content('body') or ''
                location_match = re.search(r'([A-Z][a-z]+,\s*[A-Z][a-z]+)', page_text)
                if location_match:
                    details['location'] = location_match.group(1)
                else:
                    details['location'] = self.translator("**unspecified**")

            # Extract auction ID and lot ID from URL
            url = self.page.url
            auction_match = re.search(r'/auctions/(\d+)/', url)
            lot_match = re.search(r'/lot/(\d+)', url)

            if auction_match:
                details['auction_id'] = auction_match.group(1)
            if lot_match:
                details['lot_id'] = lot_match.group(1)

            # Extract seller/auctioneer from breadcrumb or auction name
            breadcrumb = self.page.query_selector('div.breadcrumb')
            if breadcrumb:
                # Get auction name from breadcrumb
                links = breadcrumb.query_selector_all('a')
                if len(links) > 2:
                    # Third link is typically the auction name
                    details['seller'] = (links[2].text_content() or '').strip()

            if 'seller' not in details:
                details['seller'] = "Auction Ohio"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing detail page: {e}")

        return details


class AuctionOhioMarketplace(Marketplace):
    """Auction Ohio marketplace implementation."""

    name = "auctionohio"
    ItemConfigClass = AuctionOhioItemConfig

    def __init__(
        self: "AuctionOhioMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["AuctionOhioMarketplace"], **kwargs: Any) -> AuctionOhioMarketplaceConfig:
        return AuctionOhioMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["AuctionOhioMarketplace"], **kwargs: Any) -> AuctionOhioItemConfig:
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return AuctionOhioItemConfig(**filtered_kwargs)

    def _build_search_url(self: "AuctionOhioMarketplace", query: str, page: int = 1) -> str:
        """Build search URL for Auction Ohio.

        Args:
            query: Search term
            page: Page number (1-indexed)

        Returns:
            Complete search URL
        """
        # URL pattern: https://www.auctionohio.com/search?page=1&pageSize=125&search={query}&filter=(auction_type:online;auction_lot_status:100)&sort=(c:end_time;d:asc)
        base_url = "https://www.auctionohio.com/search"
        encoded_query = quote(query)

        params = [
            f"page={page}",
            "pageSize=125",
            f"search={encoded_query}",
            "filter=(auction_type:online;auction_lot_status:100)",
            "sort=(c:end_time;d:asc)"
        ]

        return f"{base_url}?{'&'.join(params)}"

    def check_listing(
        self: "AuctionOhioMarketplace",
        item: AuctionOhioItemConfig,
        listing: Listing,
    ) -> bool:
        """Check if listing matches item criteria (keywords/antikeywords).

        Args:
            item: Item configuration
            listing: Listing to check

        Returns:
            True if listing passes filters, False otherwise
        """
        # Check antikeywords first (if any keyword matches, exclude)
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

        # Check keywords (if specified, at least one must match)
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

        # Listing passed all filters
        return True

    def search(self: "AuctionOhioMarketplace", item: AuctionOhioItemConfig) -> Generator[Listing, None, None]:
        """Search Auction Ohio for items matching the configuration.

        Args:
            item: Item configuration with search phrases and filters

        Yields:
            Listing objects that match the criteria
        """
        assert self.browser is not None
        counter.increment(CounterItem.SEARCH_PERFORMED, item.name)

        if self.logger:
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching Auction Ohio for {hilight(item.name)}"
            )

        self.page = self.create_page()

        # Track seen listings to avoid duplicates across pages
        found: dict[str, bool] = {}

        # Iterate through search phrases
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.debug(f"Searching for phrase: {hilight(search_phrase)}")

            page_num = 1

            while True:
                # Build and navigate to search URL
                search_url = self._build_search_url(search_phrase, page_num)

                if self.logger:
                    self.logger.debug(f"Fetching page {page_num}: {search_url}")

                self.goto_url(search_url)
                time.sleep(2)  # Brief delay to let page load

                # Parse search results
                search_page = AuctionOhioSearchResultPage(self.page, self.translator, self.logger)
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
                        if self.logger:
                            self.logger.debug(f"Skipping duplicate: {listing_data['title'][:50]}")
                        continue

                    found[normalized_url] = True

                    # Get full details from detail page
                    if self.logger:
                        self.logger.debug(f"Fetching details for: {listing_data['title'][:50]}")

                    counter.increment(CounterItem.LISTING_QUERY, item.name)

                    # Check cache first
                    full_url = f"https://www.auctionohio.com{listing_data['url']}" if not listing_data['url'].startswith('http') else listing_data['url']
                    cached_listing = Listing.from_cache(full_url)

                    if cached_listing:
                        if self.logger:
                            self.logger.debug(f"Using cached listing for {listing_data['title'][:50]}")

                        # Check if listing passes filters
                        if self.check_listing(item, cached_listing):
                            yield cached_listing
                        continue

                    # Fetch detail page
                    self.goto_url(full_url)
                    time.sleep(1)

                    detail_page = AuctionOhioDetailPage(self.page, self.translator, self.logger)
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
                        location=details.get('location', self.translator("**unspecified**")),
                        seller=details.get('seller', "Auction Ohio"),
                        condition=self.translator("**unspecified**"),
                        description=details.get('description', self.translator("**unspecified**")),
                        auction_end_time=None,  # Could be extracted if needed
                        time_remaining=details.get('time_remaining', listing_data.get('time_remaining', '')),
                        bid_count=None,  # Not available on Auction Ohio
                        lot_number=listing_data.get('lot_number'),
                        auction_id=details.get('auction_id'),
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
