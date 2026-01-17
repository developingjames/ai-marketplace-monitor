"""RB Auction marketplace implementation."""

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
class RBAuctionMarketItemCommonConfig(BaseConfig):
    """RB Auction-specific configuration options."""

    region: str | None = None  # rbaLocationLevelTwo parameter (e.g., "USA", "Canada", "Europe")

    def handle_region(self: "RBAuctionMarketItemCommonConfig") -> None:
        if self.region is None:
            return
        if not isinstance(self.region, str):
            raise ValueError(f"Item {hilight(self.name)} region must be a string.")


@dataclass
class RBAuctionMarketplaceConfig(MarketplaceConfig, RBAuctionMarketItemCommonConfig):
    """RB Auction marketplace configuration with regional filtering."""
    pass


@dataclass
class RBAuctionItemConfig(ItemConfig, RBAuctionMarketItemCommonConfig):
    """RB Auction item configuration with regional filtering."""
    pass


class RBAuctionSearchResultPage(WebPage):
    """Parser for RB Auction search results page."""

    def get_listings(self: "RBAuctionSearchResultPage") -> list[dict[str, str]]:
        """Extract all listing information from search results page.

        Returns:
            List of dicts containing listing data
        """
        listings = []

        # Try multiple selectors for item cards (Material-UI can vary)
        # Look for links or cards that contain auction/item information
        card_elements = self.page.query_selector_all('a[href*="/auctions/"], div[class*="ItemCard"], div[class*="item-card"]')

        if self.logger:
            self.logger.debug(f"Found {len(card_elements)} potential item elements on search page")

        for card_elem in card_elements:
            try:
                # Extract URL
                url = ''
                if card_elem.tag_name.lower() == 'a':
                    url = card_elem.get_attribute('href') or ''
                else:
                    # Find link inside the card
                    link_elem = card_elem.query_selector('a[href*="/auctions/"]')
                    if link_elem:
                        url = link_elem.get_attribute('href') or ''

                if not url:
                    continue

                # Extract item ID from URL
                # URL format: /auctions/{auction_id}/{item_id} or similar
                id_match = re.search(r'/auctions/(\d+)/(\d+)', url)
                item_id = ''
                auction_id = ''
                if id_match:
                    auction_id = id_match.group(1)
                    item_id = id_match.group(2)
                    combined_id = f"{auction_id}/{item_id}"
                else:
                    # Try other patterns
                    id_match2 = re.search(r'/item/(\d+)', url)
                    if id_match2:
                        item_id = id_match2.group(1)
                        combined_id = item_id
                    else:
                        continue

                # Extract title
                title = ''
                # Try h2, h3, or strong tags
                title_elem = card_elem.query_selector('h2, h3, h4, strong, span[class*="title"]')
                if title_elem:
                    title = (title_elem.text_content() or '').strip()
                else:
                    # Fallback to card text
                    title = (card_elem.text_content() or '').strip()[:100]

                # Extract image
                image_url = ''
                img_elem = card_elem.query_selector('img')
                if img_elem:
                    image_url = img_elem.get_attribute('src') or ''

                # Extract current bid/price
                current_bid = self.translator("**unspecified**")
                card_text = card_elem.text_content() or ''
                # Look for currency amounts
                price_match = re.search(r'[€$£][\d,]+(?:\.\d{2})?|\b[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|CAD)', card_text)
                if price_match:
                    current_bid = price_match.group(0)

                # Extract location
                location = self.translator("**unspecified**")
                location_match = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2,})', card_text)
                if location_match:
                    location = location_match.group(1)

                # Extract time remaining
                time_remaining = ''
                time_match = re.search(r'(\d+)\s+(days?|hours?|minutes?)', card_text, re.IGNORECASE)
                if time_match:
                    time_remaining = f"{time_match.group(1)} {time_match.group(2)}"

                # Only add if we have essential data
                if (item_id or combined_id) and url:
                    listings.append({
                        'id': combined_id if combined_id else item_id,
                        'auction_id': auction_id,
                        'item_id': item_id,
                        'title': title,
                        'url': url,
                        'image': image_url,
                        'current_bid': current_bid,
                        'location': location,
                        'time_remaining': time_remaining,
                    })

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error parsing item element: {e}")
                continue

        return listings

    def has_next_page(self: "RBAuctionSearchResultPage") -> bool:
        """Check if there is a next page available.

        Returns:
            True if next page exists, False otherwise
        """
        # Look for pagination button or "Load more" button
        # Material-UI pagination typically uses button elements
        load_more = self.page.query_selector('button[class*="load"], button[class*="more"]')
        if load_more:
            # Check if disabled
            disabled = load_more.get_attribute('disabled')
            if disabled is None:
                return True

        # Look for next page button
        pagination = self.page.query_selector('nav[aria-label*="pagination"]')
        if pagination:
            next_buttons = pagination.query_selector_all('button')
            for button in next_buttons:
                aria_label = button.get_attribute('aria-label') or ''
                if 'next' in aria_label.lower():
                    disabled = button.get_attribute('disabled')
                    if disabled is None:
                        return True

        # Check if we got results - if we got size (120) results, there may be more
        return False


class RBAuctionDetailPage(WebPage):
    """Parser for RB Auction detail page."""

    def get_listing_details(self: "RBAuctionDetailPage") -> dict[str, str]:
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
                page_title = self.page.title()
                details['title'] = page_title.replace(' | Ritchie Bros.', '').replace(' | RB Auction', '').strip()

            # Extract description
            desc_elem = self.page.query_selector('div[class*="description"], section[class*="description"], div[class*="details"]')
            if desc_elem:
                desc_text = desc_elem.text_content() or ''
                details['description'] = desc_text.strip()
            else:
                details['description'] = self.translator("**unspecified**")

            # Extract current bid
            page_text = self.page.text_content('body') or ''

            # Look for current bid or price
            bid_match = re.search(r'Current\s+(?:Bid|Price)[:\s]*([€$£][\d,]+(?:\.\d{2})?)', page_text, re.IGNORECASE)
            if bid_match:
                details['current_bid'] = bid_match.group(1)
            else:
                # Try to find any currency amount
                price_match = re.search(r'[€$£][\d,]+(?:\.\d{2})?', page_text)
                if price_match:
                    details['current_bid'] = price_match.group(0)

            # Extract bid count
            bid_count_match = re.search(r'(\d+)\s+Bids?', page_text, re.IGNORECASE)
            if bid_count_match:
                details['bid_count'] = bid_count_match.group(1)

            # Extract location
            location_match = re.search(r'Location[:\s]*([A-Za-z\s,]+(?:USA|Canada|UK|Europe))', page_text, re.IGNORECASE)
            if location_match:
                details['location'] = location_match.group(1).strip()
            else:
                # Try simpler pattern
                location_match2 = re.search(r'([A-Z][a-z]+,\s*[A-Z]{2,})', page_text)
                if location_match2:
                    details['location'] = location_match2.group(1)
                else:
                    details['location'] = self.translator("**unspecified**")

            # Extract seller/auctioneer
            seller_elem = self.page.query_selector('span[class*="seller"], div[class*="auctioneer"]')
            if seller_elem:
                details['seller'] = (seller_elem.text_content() or '').strip()

            if 'seller' not in details or not details['seller']:
                details['seller'] = "RB Auction"

            # Extract auction ID and item ID from URL
            url = self.page.url
            auction_match = re.search(r'/auctions/(\d+)/', url)
            item_match = re.search(r'/auctions/\d+/(\d+)', url)

            if auction_match:
                details['auction_id'] = auction_match.group(1)
            if item_match:
                details['item_id'] = item_match.group(1)

            # Extract lot number
            lot_match = re.search(r'Lot[:\s#]*(\d+)', page_text, re.IGNORECASE)
            if lot_match:
                details['lot_number'] = lot_match.group(1)

            # Extract time remaining
            time_match = re.search(r'(\d+)\s+(days?|hours?|minutes?)\s+remaining', page_text, re.IGNORECASE)
            if time_match:
                details['time_remaining'] = f"{time_match.group(1)} {time_match.group(2)}"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing RB Auction detail page: {e}")

        return details


class RBAuctionMarketplace(Marketplace):
    """RB Auction marketplace implementation."""

    name = "rbauction"
    ItemConfigClass = RBAuctionItemConfig

    def __init__(
        self: "RBAuctionMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["RBAuctionMarketplace"], **kwargs: Any) -> RBAuctionMarketplaceConfig:
        return RBAuctionMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["RBAuctionMarketplace"], **kwargs: Any) -> RBAuctionItemConfig:
        valid_fields = set(cls.ItemConfigClass.__dataclass_fields__.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        return RBAuctionItemConfig(**filtered_kwargs)

    def _build_search_url(
        self: "RBAuctionMarketplace",
        query: str,
        offset: int = 0,
        region: str | None = None
    ) -> str:
        """Build search URL for RB Auction.

        Args:
            query: Search term
            offset: Offset for pagination (0, 120, 240, etc.)
            region: Optional region filter (rbaLocationLevelTwo parameter)

        Returns:
            Complete search URL
        """
        base_url = "https://www.rbauction.com/search"
        encoded_query = quote(query)

        params = [
            f"freeText={encoded_query}",
            "size=120",
            f"from={offset}"
        ]

        if region:
            params.append(f"rbaLocationLevelTwo={quote(region)}")

        return f"{base_url}?{'&'.join(params)}"

    def check_listing(
        self: "RBAuctionMarketplace",
        item: RBAuctionItemConfig,
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

    def search(self: "RBAuctionMarketplace", item: RBAuctionItemConfig) -> Generator[Listing, None, None]:
        """Search RB Auction for items matching the configuration.

        Args:
            item: Item configuration with search phrases and filters

        Yields:
            Listing objects that match the criteria
        """
        assert self.browser is not None
        counter.increment(CounterItem.SEARCH_PERFORMED, item.name)

        if self.logger:
            region_info = ""
            if item.region:
                region_info = f" in region {item.region}"
            self.logger.info(
                f"{hilight('[Search]', 'info')} Searching RB Auction for {hilight(item.name)}{region_info}"
            )

        self.page = self.create_page()

        # Track seen listings
        found: dict[str, bool] = {}

        # Iterate through search phrases
        for search_phrase in item.search_phrases:
            if self.logger:
                self.logger.debug(f"Searching for phrase: {hilight(search_phrase)}")

            offset = 0
            page_size = 120

            while True:
                # Build and navigate to search URL
                search_url = self._build_search_url(
                    search_phrase,
                    offset,
                    item.region
                )

                if self.logger:
                    self.logger.debug(f"Fetching results with offset {offset}: {search_url}")

                self.goto_url(search_url)
                time.sleep(3)  # Extra time for Material-UI to render

                # Parse search results
                search_page = RBAuctionSearchResultPage(self.page, self.translator, self.logger)
                listings_data = search_page.get_listings()

                if not listings_data:
                    if self.logger:
                        self.logger.debug(f"No listings found at offset {offset}")
                    break

                if self.logger:
                    self.logger.debug(f"Found {len(listings_data)} listings at offset {offset}")

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
                    full_url = listing_data['url'] if listing_data['url'].startswith('http') else f"https://www.rbauction.com{listing_data['url']}"

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

                    detail_page = RBAuctionDetailPage(self.page, self.translator, self.logger)
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
                        seller=details.get('seller', "RB Auction"),
                        condition=self.translator("**unspecified**"),
                        description=details.get('description', self.translator("**unspecified**")),
                        auction_end_time=None,
                        time_remaining=details.get('time_remaining', listing_data.get('time_remaining', '')),
                        bid_count=int(details['bid_count']) if 'bid_count' in details else None,
                        lot_number=details.get('lot_number'),
                        auction_id=details.get('auction_id', listing_data.get('auction_id')),
                    )

                    # Cache the listing
                    listing.to_cache(full_url)

                    # Check if listing passes filters
                    if self.check_listing(item, listing):
                        yield listing

                # Check for next page
                # If we got page_size results, there might be more
                if len(listings_data) >= page_size:
                    offset += page_size
                    if self.logger:
                        self.logger.debug(f"Moving to offset {offset}")
                else:
                    if self.logger:
                        self.logger.debug("No more pages available")
                    break
