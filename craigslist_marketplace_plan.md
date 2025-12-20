# Plan: Adding Craigslist Support to AI Marketplace Monitor

## Executive Summary

This plan outlines the approach for adding Craigslist as a second marketplace alongside Facebook Marketplace in the AI Marketplace Monitor project. The existing architecture is well-designed for multi-marketplace support, requiring minimal changes to the core infrastructure. The primary work involves implementing Craigslist-specific scraping logic while reusing the existing monitoring, notification, AI evaluation, and caching systems.

## Current Architecture Analysis

### Strengths for Multi-Marketplace Support

The codebase is already designed with marketplace abstraction in mind:

1. **Generic Base Classes**: `Marketplace[TMarketplaceConfig, TItemConfig]` in `marketplace.py:454` provides a clean abstraction layer using Python generics
2. **Marketplace Registration**: Simple registration pattern in `config.py:22` via `supported_marketplaces` dictionary
3. **Flexible Configuration**: TOML-based configuration supports marketplace-specific and item-specific settings
4. **Shared Infrastructure**: All notification backends, AI evaluation, caching, scheduling, and user management work for any marketplace

### Current Limitations

1. **Hardcoded Marketplace Enum**: `MarketPlace` enum in `marketplace.py:21` only defines `FACEBOOK`
2. **Facebook Validation**: `MarketplaceConfig.handle_market_type()` in `marketplace.py:375` explicitly validates that `market_type` must be "facebook"
3. **Search City Validation**: Error messages in `marketplace.py:142-152` reference Facebook-specific URL format
4. **Project Description**: `pyproject.toml:5` describes the tool as "for monitoring facebook marketplace"

## Implementation Approach

### Phase 1: Core Infrastructure Updates

#### 1.1. Update Marketplace Enum
**File**: `src/ai_marketplace_monitor/marketplace.py`
**Location**: Line 21-22
**Change**:
```python
class MarketPlace(Enum):
    FACEBOOK = "facebook"
    CRAIGSLIST = "craigslist"
```

#### 1.2. Relax Market Type Validation
**File**: `src/ai_marketplace_monitor/marketplace.py`
**Location**: Lines 375-383
**Change**: Modify `MarketplaceConfig.handle_market_type()` to validate against all supported marketplaces in the registry rather than hardcoding Facebook
```python
def handle_market_type(self: "MarketplaceConfig") -> None:
    from .config import supported_marketplaces
    if self.market_type is None:
        return
    if not isinstance(self.market_type, str):
        raise ValueError(f"Marketplace {hilight(self.market_type)} market must be a string.")
    if self.market_type.lower() not in supported_marketplaces:
        raise ValueError(
            f"Marketplace {hilight(self.market_type)} is not supported. "
            f"Supported: {', '.join(supported_marketplaces.keys())}"
        )
```

#### 1.3. Make Search City Validation Marketplace-Agnostic
**File**: `src/ai_marketplace_monitor/marketplace.py`
**Location**: Lines 142-152
**Change**: Update error message to be generic or provide marketplace-specific guidance based on configuration

### Phase 2: Craigslist Implementation

#### 2.1. Create Craigslist Module
**New File**: `src/ai_marketplace_monitor/craigslist.py`

**Required Classes**:

1. **CraigslistMarketItemCommonConfig** (extends `MarketItemCommonConfig`)
   - Craigslist-specific filters:
     - `posted_today`: bool - Filter for listings posted today
     - `has_image`: bool - Only show listings with images
     - `search_nearby`: bool - Include nearby areas
     - `bundle_duplicates`: bool - Bundle duplicate listings
     - `search_distance`: int - Search radius in miles
     - `category`: str - Craigslist category (e.g., 'sss' for all, 'cta' for cars, 'bia' for bikes)
     - `condition`: List[str] - new, like new, excellent, good, fair, salvage

2. **CraigslistMarketplaceConfig** (extends `MarketplaceConfig` + `CraigslistMarketItemCommonConfig`)
   - No authentication required (Craigslist doesn't need login)
   - Use inherited configuration options

3. **CraigslistItemConfig** (extends `ItemConfig` + `CraigslistMarketItemCommonConfig`)
   - Item-specific search configuration
   - Inherit Craigslist-specific filters

4. **CraigslistMarketplace** (extends `Marketplace[CraigslistMarketplaceConfig, CraigslistItemConfig]`)
   - Implement required abstract methods:
     - `get_config(cls, **kwargs) -> CraigslistMarketplaceConfig`
     - `get_item_config(cls, **kwargs) -> CraigslistItemConfig`
     - `search(item_config) -> Generator[Listing, None, None]`
   - Helper methods:
     - `build_search_url(item_config, city, search_phrase) -> str`
     - `parse_search_results(page) -> List[Listing]`
     - `get_listing_details(post_url) -> Listing`

**Craigslist URL Structure**:
- Search URL: `https://{city}.craigslist.org/search/{category}?query={search_phrase}&min_price={min}&max_price={max}&search_distance={dist}`
- City format: Subdomain-based (e.g., `houston.craigslist.org`, `sfbay.craigslist.org`)

**HTML Parsing Strategy**:
- Craigslist uses a simpler, more stable HTML structure than Facebook
- Search results: `<li class="cl-search-result">` elements
- Title: `<div class="title">`
- Price: `<div class="price">`
- Location: `<div class="location">`
- Image: `<img>` tags (may need to handle lazy loading)
- Listing page: More structured with consistent class names

#### 2.2. Register Craigslist Marketplace
**File**: `src/ai_marketplace_monitor/config.py`
**Location**: Line 22
**Change**:
```python
from .craigslist import CraigslistMarketplace
from .facebook import FacebookMarketplace

supported_marketplaces = {
    "facebook": FacebookMarketplace,
    "craigslist": CraigslistMarketplace
}
```

### Phase 3: Configuration Support

#### 3.1. Update Default Market Type
**File**: `src/ai_marketplace_monitor/marketplace.py`
**Location**: Line 371
**Change**: Keep default as Facebook for backward compatibility, but make it clear that Craigslist is also supported

#### 3.2. Configuration Examples

**Multi-Marketplace Configuration**:
```toml
# Facebook Marketplace
[marketplace.facebook]
market_type = 'facebook'
search_city = 'houston'
username = 'user@email.com'
password = 'password'
search_interval = '30m'

# Craigslist
[marketplace.craigslist]
market_type = 'craigslist'
search_city = 'houston'
search_interval = '15m'

# Items can target specific marketplaces
[item.gopro_facebook]
marketplace = 'facebook'
search_phrases = 'Go Pro Hero 11'
min_price = 100
max_price = 300

[item.gopro_craigslist]
marketplace = 'craigslist'
search_phrases = 'GoPro Hero 11'
min_price = 100
max_price = 300
has_image = true
posted_today = true

# Or search both marketplaces (omit marketplace field)
[item.bike]
search_phrases = 'road bike'
min_price = 200
max_price = 800
# This will search both facebook and craigslist
```

### Phase 4: City Mapping

#### 4.1. Craigslist City Format
Craigslist uses subdomain-based city identifiers that differ from Facebook:
- Houston: `houston.craigslist.org`
- San Francisco Bay Area: `sfbay.craigslist.org`
- New York: `newyork.craigslist.org`

#### 4.2. Implementation Strategy
Two options:

**Option A: Separate City Fields** (Recommended)
- Add `craigslist_city` field to configurations
- Keep `search_city` for Facebook
- Example:
  ```toml
  [marketplace.facebook]
  search_city = 'houston'

  [marketplace.craigslist]
  craigslist_city = 'houston'  # Maps to houston.craigslist.org
  ```

**Option B: City Mapping Table**
- Create a mapping from Facebook city codes to Craigslist subdomains
- Maintain in `config.toml` or a separate mapping file
- Example:
  ```toml
  [city_mapping]
  houston = {facebook = 'houston', craigslist = 'houston'}
  sanfrancisco = {facebook = 'sanfrancisco', craigslist = 'sfbay'}
  ```

**Recommendation**: Use Option A for simplicity and avoid maintaining mappings for hundreds of cities

### Phase 5: Testing Strategy

#### 5.1. Unit Tests
**New File**: `tests/test_craigslist.py`

Test coverage:
1. Configuration validation (CraigslistMarketplaceConfig, CraigslistItemConfig)
2. URL building with various filter combinations
3. HTML parsing for search results
4. HTML parsing for listing details
5. Integration with shared caching system
6. Error handling for network issues

#### 5.2. Integration Tests
1. End-to-end search with real Craigslist pages (using Playwright)
2. Multi-marketplace configuration parsing
3. Item routing to correct marketplace
4. Notification system with Craigslist listings

### Phase 6: Documentation Updates

#### 6.1. README.md Updates
- Change description from "monitors Facebook Marketplace" to "monitors Facebook Marketplace and Craigslist"
- Add Craigslist configuration examples
- Document Craigslist-specific filters
- Add city subdomain reference table (common cities)

#### 6.2. Documentation Files
- Update `docs/example_config.toml` with Craigslist examples
- Create `docs/craigslist_cities.md` with city subdomain mappings
- Update any Facebook-specific documentation to be marketplace-agnostic

#### 6.3. Code Documentation
- Docstrings for all Craigslist classes and methods
- Inline comments for Craigslist-specific HTML parsing logic

## Implementation Challenges & Solutions

### Challenge 1: Different HTML Structures
**Issue**: Facebook has multiple layout variations; Craigslist may have its own variations
**Solution**:
- Implement multiple parser classes similar to Facebook's approach (FacebookRegularItemPage, FacebookRentalItemPage, etc.)
- Start with most common Craigslist layout and expand as needed
- Add logging for unparseable pages to identify new layouts

### Challenge 2: No Authentication
**Issue**: Craigslist doesn't require login, but may have rate limiting
**Solution**:
- Respect Craigslist's robots.txt
- Implement configurable delays between requests
- Support proxy rotation (already implemented in monitor_config)
- Consider adding User-Agent rotation

### Challenge 3: Location Format Differences
**Issue**: Facebook uses city codes, Craigslist uses subdomains
**Solution**: Use marketplace-specific city configuration fields to avoid confusion

### Challenge 4: Category Systems
**Issue**: Facebook and Craigslist have different category taxonomies
**Solution**:
- Make category field marketplace-specific (in MarketItemCommonConfig subclasses)
- Provide clear documentation for Craigslist category codes
- Consider adding category aliases for common items

### Challenge 5: Search Radius
**Issue**: Different marketplaces may handle radius differently
**Solution**:
- Keep radius in shared config but allow marketplace implementations to interpret it
- Craigslist can use `search_distance` parameter in URL

## Risk Assessment

### Low Risk
- Adding new marketplace without changing existing Facebook functionality
- Configuration system already supports multiple marketplaces
- All shared infrastructure is marketplace-agnostic

### Medium Risk
- Craigslist HTML structure changes requiring parser updates
- Rate limiting or blocking by Craigslist
- City subdomain mapping maintenance

### High Risk
- None identified (architecture is well-suited for this change)

## Migration Path for Users

### Backward Compatibility
All existing configurations will continue to work without changes:
- Default `market_type` remains "facebook"
- Existing items without `marketplace` field will use first available marketplace (Facebook if configured)
- No breaking changes to configuration format

### Opt-in Adoption
Users can add Craigslist by:
1. Adding a `[marketplace.craigslist]` section
2. Optionally specifying `marketplace = 'craigslist'` in items
3. Configuring Craigslist-specific filters as needed

## Success Criteria

1. **Functionality**: Successfully search Craigslist for listings with various filters
2. **Integration**: Craigslist listings flow through AI evaluation, caching, and notification systems
3. **Configuration**: Users can configure both marketplaces and route items to either or both
4. **Testing**: All tests pass including new Craigslist-specific tests
5. **Documentation**: Clear examples and guidance for Craigslist configuration
6. **Performance**: No degradation to Facebook Marketplace monitoring
7. **Code Quality**: Maintains existing code standards (passes ruff, mypy, black checks)
