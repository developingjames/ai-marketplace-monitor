# Implementation Plan: Add 5 New Auction Marketplace Integrations

## Overview
Add support for 5 new auction house marketplaces modeled after the existing Facebook marketplace implementation. Each marketplace requires parsing search results pages, detail pages, pagination support, and integration with the existing keyword/antikeyword filtering, caching, and logging infrastructure.

## Marketplaces to Add
1. **Auction Ohio** (auctionohio.com)
2. **GovDeals** (govdeals.com)
3. **Proxibid** (proxibid.com)
4. **Purple Wave** (purplewave.com)
5. **RB Auction** / Ritchie Bros (rbauction.com)

## Architecture Overview
Each marketplace implementation follows this pattern:
- Marketplace-specific config classes extending `MarketplaceConfig` and `ItemConfig`
- Main marketplace class extending `Marketplace` base class
- WebPage parsers for search results and detail pages
- Integration with existing keyword filtering, caching, and notification systems

---

## Phase 1: Core Infrastructure Setup

### Task 1.1: Update MarketPlace Enum
**File:** `src/ai_marketplace_monitor/marketplace.py`
- Add 5 new marketplace entries to the `MarketPlace` enum:
  - AUCTION_OHIO = "auctionohio"
  - GOVDEALS = "govdeals"
  - PROXIBID = "proxibid"
  - PURPLE_WAVE = "purplewave"
  - RBAUCTION = "rbauction"

### Task 1.2: Register Marketplaces in Config
**File:** `src/ai_marketplace_monitor/config.py`
- Update `supported_marketplaces` dictionary to include all 5 new marketplaces
- Map each marketplace name to its corresponding class

---

## Phase 2: Auction Ohio Implementation

### Task 2.1: Create Auction Ohio Module
**File:** `src/ai_marketplace_monitor/auctionohio.py`

**URL Pattern Analysis:**
- Search: `https://www.auctionohio.com/search?page=1&pageSize=125&search={query}&filter=(auction_type:online;auction_lot_status:100)&sort=(c:end_time;d:asc)`
- Detail: `https://www.auctionohio.com/auctions/{auction_id}/lot/{lot_id}`
- Pagination: `page` parameter (1-indexed)

**Required Components:**
- `AuctionOhioMarketplaceConfig(MarketplaceConfig)` - marketplace-level config
- `AuctionOhioItemConfig(ItemConfig)` - item-level config
- `AuctionOhioMarketplace(Marketplace)` - main marketplace class with:
  - `search()` method to iterate through search results
  - `get_listing_details()` method to fetch detail pages
  - `check_listing()` method for keyword/antikeyword filtering
- `AuctionOhioSearchResultPage(WebPage)` - parser for search results
  - Extract: title, current bid, lot ID, auction ID, thumbnail, time remaining
  - Handle pagination
- `AuctionOhioDetailPage(WebPage)` - parser for detail pages
  - Extract: full description, auction info (start/end time), location, bidding history, images

### Task 2.2: HTML Analysis for Auction Ohio
- Analyze `Search Results - Auction Ohio.html` for listing structure
- Analyze `Pyrex - Early American designs - Auction Ohio.html` for detail page structure
- Document CSS selectors/XPath patterns needed for parsing

---

## Phase 3: GovDeals Implementation

### Task 3.1: Create GovDeals Module
**File:** `src/ai_marketplace_monitor/govdeals.py`

**URL Pattern Analysis:**
- Search: `https://www.govdeals.com/en/search?kWord={query}&zipcode={zip}&miles={radius}`
- Pagination: `https://www.govdeals.com/en/search/filters?kWord={query}&zipcode={zip}&miles={radius}&pn={page}`
- Detail: `https://www.govdeals.com/en/asset/{seller_id}/{item_id}`
- **Supports radius-based search** from zip code

**Required Components:**
- `GovDealsMarketplaceConfig(MarketplaceConfig)` - with zip code and radius support
- `GovDealsItemConfig(ItemConfig)` - item-level config
- `GovDealsMarketplace(Marketplace)` - main marketplace class
- `GovDealsSearchResultPage(WebPage)` - search results parser
  - Extract: title, current bid/price, item ID, seller ID, location, thumbnail
  - Handle pagination (pn parameter)
- `GovDealsDetailPage(WebPage)` - detail page parser
  - Extract: full description, auction end time, location, agency/seller info, bid history

### Task 3.2: HTML Analysis for GovDeals
- Analyze `trailer _ GovDeals.html` and Page 2 for listing structure
- Analyze detail page HTML for extraction patterns
- Handle radius/location filtering

---

## Phase 4: Proxibid Implementation

### Task 4.1: Create Proxibid Module
**File:** `src/ai_marketplace_monitor/proxibid.py`

**URL Pattern Analysis:**
- Search: `https://www.proxibid.com/asp/SearchAdvanced_i.asp?searchTerm={query}&category=all%20categories#searchid=...&type=lot&search={query}&sort=relevance&view=gallery&length=100&start=1&refine=Selling%20Format|Timed+Events`
- Pagination: `start` parameter (1-indexed, increments by `length`)
- Detail: `https://www.proxibid.com/Industrial-Machinery-Equipment/.../lotInformation/{lot_id}`
- **Note:** Set `length=100` for max results per page

**Required Components:**
- `ProxibidMarketplaceConfig(MarketplaceConfig)` - marketplace config
- `ProxibidItemConfig(ItemConfig)` - item config
- `ProxibidMarketplace(Marketplace)` - main class
- `ProxibidSearchResultPage(WebPage)` - search parser
  - Handle complex URL structure with hash fragments
  - Extract: title, current bid, lot ID, thumbnail, auction end time
  - Pagination: increment `start` by `length` (100)
- `ProxibidDetailPage(WebPage)` - detail parser
  - Extract: description, location, auction details, bidding info

### Task 4.2: HTML Analysis for Proxibid
- Analyze search result HTML structure
- Analyze detail page HTML
- Handle JavaScript-heavy page structure (may need wait conditions)

---

## Phase 5: Purple Wave Implementation

### Task 5.1: Create Purple Wave Module
**File:** `src/ai_marketplace_monitor/purplewave.py`

**URL Pattern Analysis:**
- Search: `https://www.purplewave.com/search/{query}?searchType=all&dateType=upcoming&zipcode={zip}&zipcodeRange={radius}&sortBy=current_bid-desc&perPage=100&grouped=true&viewtype=compressed`
- Pagination: `page` parameter
- Detail: `https://www.purplewave.com/auction/{auction_id}/item/{item_id}/{slug}`
- **Supports radius-based search** from zip code

**Required Components:**
- `PurpleWaveMarketplaceConfig(MarketplaceConfig)` - with zip code and radius support
- `PurpleWaveItemConfig(ItemConfig)` - item config
- `PurpleWaveMarketplace(Marketplace)` - main class
- `PurpleWaveSearchResultPage(WebPage)` - search parser
  - Extract: title, current bid, item ID, auction ID, location, thumbnail, auction date
  - Handle pagination
  - Support `perPage=100` for efficiency
- `PurpleWaveDetailPage(WebPage)` - detail parser
  - Extract: full description, location, auction details, bid history, images

### Task 5.2: HTML Analysis for Purple Wave
- Analyze search result structures
- Analyze detail page HTML
- Handle auction timing/status information

---

## Phase 6: RB Auction (Ritchie Bros) Implementation

### Task 6.1: Create RB Auction Module
**File:** `src/ai_marketplace_monitor/rbauction.py`

**URL Pattern Analysis:**
- Search: `https://www.rbauction.com/search?freeText={query}&rbaLocationLevelTwo=US-MDW&size=120&from=0`
- Pagination: `from` parameter (offset-based, increments by `size`)
- Detail: `https://www.rbauction.com/pdp/{slug}/{item_id}`
- **Supports regional filtering** via `rbaLocationLevelTwo` parameter

**Required Components:**
- `RBAuctionMarketplaceConfig(MarketplaceConfig)` - with region support
- `RBAuctionItemConfig(ItemConfig)` - item config
- `RBAuctionMarketplace(Marketplace)` - main class
- `RBAuctionSearchResultPage(WebPage)` - search parser
  - Extract: title, current bid/price, item ID, location, thumbnail, auction date
  - Pagination: offset-based (`from` increments by `size=120`)
- `RBAuctionDetailPage(WebPage)` - detail parser
  - Extract: description, location, auction details, equipment specs

### Task 6.2: HTML Analysis for RB Auction
- Analyze search result structure
- Analyze detail page HTML
- Handle regional filtering options

---

## Phase 7: Integration and Common Features

### Task 7.1: Implement Common Auction Features
For all 5 marketplaces, ensure support for:

**Filtering & Search:**
- Keywords filtering (Boolean logic support from `is_substring()`)
- Antikeywords filtering
- Price range filtering (min_price, max_price)
- Location/radius filtering (where supported)
- Search phrase iteration

**Caching:**
- Use `Listing.from_cache()` and `Listing.to_cache()`
- Support `cache_ignore_price_changes` option
- Cache listing details to avoid re-fetching unchanged items

**Pagination:**
- Implement proper pagination for each marketplace's URL pattern
- Handle "no more results" detection
- Log pagination progress

**Data Extraction:**
- Title (required)
- Price/Current Bid (required, use "**unspecified**" if missing)
- Description (required)
- Location (required)
- Auction timing info (start time, end time, time remaining)
- Seller/Agency info (if available)
- Images (at least primary image)
- Unique item ID

**Logging:**
- Search initiated
- Listings examined vs excluded
- Cache hits vs fetches
- Parsing errors
- Pagination progress

### Task 7.2: Error Handling
- Handle missing data gracefully (use "**unspecified**")
- Catch and log parsing errors without crashing
- Handle network timeouts
- Handle pagination edge cases (last page, empty results)

---

## Phase 8: Configuration Support

### Task 8.1: Update Config Schema
**File:** `config.toml` (example updates)

Add example configurations for each new marketplace:
```toml
# [marketplace.auctionohio]
# market_type = "auctionohio"

# [marketplace.govdeals]
# market_type = "govdeals"
# zipcode = "43311"
# miles = 250

# [marketplace.proxibid]
# market_type = "proxibid"

# [marketplace.purplewave]
# market_type = "purplewave"
# zipcode = "43311"
# zipcodeRange = 250

# [marketplace.rbauction]
# market_type = "rbauction"
# region = "US-MDW"  # US Midwest
```

### Task 8.2: Document Configuration Options
Create/update documentation for:
- Each marketplace's required and optional config parameters
- URL patterns and search parameters
- Location/radius support (where applicable)
- Region codes (for RB Auction)

---

## Phase 9: Testing

### Task 9.1: Create Test Files
**Files:** `tests/test_auctionohio.py`, `tests/test_govdeals.py`, etc.

For each marketplace:
- Test search result parsing
- Test detail page parsing
- Test pagination logic
- Test keyword/antikeyword filtering
- Test caching behavior
- Test error handling

### Task 9.2: Manual Testing
- Run actual searches against each marketplace
- Verify correct data extraction
- Test with various search terms and filters
- Validate URL construction
- Check pagination works correctly

---

## Phase 10: Documentation and Cleanup

### Task 10.1: Update README
- Add documentation for the 5 new marketplaces
- Include example configurations
- Document any marketplace-specific features (radius, regions, etc.)
- Add notes about pagination and rate limiting

### Task 10.2: Code Review Checklist
- All marketplaces follow consistent patterns
- Error handling is comprehensive
- Logging is appropriate and helpful
- Code is well-commented
- Unused imports removed
- Type hints are correct

---

## Implementation Order

**Recommended sequence:**
1. Start with **Purple Wave** (cleanest URL structure, good documentation in links.txt)
2. Then **GovDeals** (similar to Purple Wave, has radius support)
3. Then **Auction Ohio** (simpler pagination)
4. Then **RB Auction** (offset-based pagination)
5. Finally **Proxibid** (most complex with hash fragments and JavaScript)

This order allows building confidence with simpler implementations before tackling the more complex ones.

---

## Success Criteria

For each marketplace implementation:
- ✅ Can successfully search with a query term
- ✅ Parses search results correctly (title, price, ID, location)
- ✅ Pagination works and retrieves all available results
- ✅ Detail pages load and parse correctly
- ✅ Caching works (avoid re-fetching unchanged listings)
- ✅ Keyword/antikeyword filtering works
- ✅ Integrates with existing notification system
- ✅ Logging provides useful debugging information
- ✅ Error handling prevents crashes
- ✅ Tests pass

---

## Notes and Considerations

1. **HTML Structure Changes:** Marketplaces may update their HTML structure. Implementations should be resilient and log clear errors when parsing fails.

2. **Rate Limiting:** Consider adding delays between requests to avoid being blocked. Use existing `time.sleep()` patterns from Facebook implementation.

3. **Authentication:** Currently none of the 5 marketplaces appear to require login. If any do in the future, follow the Facebook `login()` pattern.

4. **JavaScript Rendering:** Some marketplaces (especially Proxibid) may require waiting for JavaScript. Use Playwright's `wait_for_load_state()` and `wait_for_selector()` appropriately.

5. **Location Filtering:** GovDeals and Purple Wave support zip code + radius. RB Auction uses regional codes. Auction Ohio appears location-independent. Proxibid is unclear.

6. **Auction Timing:** All marketplaces have auction end times. Extract and display this in listings for user awareness.

7. **Currency:** All appear to be USD-based. Handle gracefully if international listings appear.

8. **Images:** Extract at least one image URL per listing for the markdown output.

9. **Listing IDs:** Ensure IDs are unique and stable for caching. Combine auction_id + lot_id where necessary.

10. **Pagination Detection:** Implement robust "no more results" detection to avoid infinite loops.
