# Multi-Marketplace Support Architecture Plan

## Problem Statement

The current architecture has a fundamental design flaw when supporting items that search across multiple marketplaces:

### Current Architecture
```
Item Config Storage: self.config.item[item_name] → Single ItemConfig object
```

When an item doesn't specify a marketplace (meaning it should search ALL configured marketplaces), the system:
1. Creates ONE item config using the FIRST marketplace's config class (e.g., FacebookItemConfig)
2. Passes this single config to ALL marketplaces during scheduling

### Why This Fails
- **FacebookItemConfig** has fields: `availability`, `delivery_method`, `date_listed` (Facebook-specific)
- **CraigslistItemConfig** has fields: `search_distance`, `posted_today`, `has_image`, `search_nearby`, `bundle_duplicates`, `crypto_ok` (Craigslist-specific)

When FacebookItemConfig is passed to Craigslist:
```python
TypeError: CraigslistItemConfig.__init__() got an unexpected keyword argument 'availability'
```

When CraigslistItemConfig is passed to Facebook:
```python
AttributeError: 'CraigslistItemConfig' object has no attribute 'availability'
```

## Root Cause Analysis

### Class Hierarchy
```
BaseConfig (base for all configs)
  ├─ MarketItemCommonConfig (common marketplace fields)
  │    ├─ MarketplaceConfig (adds market_type, language, monitor_config)
  │    │    ├─ FacebookMarketItemCommonConfig (FB-specific fields)
  │    │    │    └─ FacebookMarketplaceConfig
  │    │    └─ CraigslistMarketItemCommonConfig (CL-specific fields)
  │    │         └─ CraigslistMarketplaceConfig
  │    └─ ItemConfig (adds searched_count, search_phrases, keywords, etc)
  │         ├─ FacebookItemConfig (extends ItemConfig + FacebookMarketItemCommonConfig)
  │         └─ CraigslistItemConfig (extends ItemConfig + CraigslistMarketItemCommonConfig)
```

### Current Config Loading (config.py:186-197)
```python
for marketplace_name, markerplace_config in config["marketplace"].items():
    marketplace_class = supported_marketplaces[markerplace_config.get("market_type", "facebook")]
    if "marketplace" not in item_config or item_config["marketplace"] == marketplace_name:
        # PROBLEM: Creates config using first matching marketplace class
        self.item[item_name] = marketplace_class.get_item_config(
            name=item_name,
            marketplace=item_config.get("marketplace"),
            **{x: y for x, y in item_config.items() if x != "marketplace"},
        )
        break  # Only creates ONE config
```

### Current Scheduling (monitor.py:313-380)
```python
for item_config in self.config.item.values():  # ONE config per item
    if item_config.marketplace is None or item_config.marketplace == marketplace_config.name:
        # PROBLEM: Tries to use FacebookItemConfig for Craigslist searches
        marketplace_specific_item_config = marketplace_class.get_item_config(
            **dict(item_config.__dict__.items())  # Passes FB fields to CL
        )
```

## Design Options

### Option 1: Store Multiple Configs Per Item
**Approach**: Change `self.config.item` to store one config per marketplace per item

```python
# Current: self.config.item[item_name] → ItemConfig
# New:     self.config.item[item_name][marketplace_name] → ItemConfig

self.config.item = {
    "tractor": {
        "facebook": FacebookItemConfig(...),
        "craigslist": CraigslistItemConfig(...)
    }
}
```

**Pros**:
- Clean separation of marketplace-specific configs
- No need to convert configs at runtime
- Each marketplace gets exactly the config it expects

**Cons**:
- Breaks existing architecture significantly
- Would require changes to:
  - Config loading (config.py)
  - Item iteration throughout monitor.py
  - Statistics tracking
  - Any code that accesses `self.config.item[name]`

### Option 2: Create Configs On-Demand During Scheduling
**Approach**: Store TOML dict per item, create marketplace-specific configs when scheduling

```python
self.config.item_raw = {
    "tractor": {
        "search_phrases": "tractor loader backhoe",
        "keywords": "...",
        # Raw TOML data, no marketplace-specific fields
    }
}

# During scheduling:
for marketplace in marketplaces:
    item_config = marketplace_class.get_item_config(
        **self.config.item_raw[item_name]
    )
```

**Pros**:
- Configs are created with only valid fields for each marketplace
- Source of truth is the TOML data
- Marketplace-specific fields naturally filtered

**Cons**:
- Lose validation at config load time
- Statistics/state tracking (searched_count) becomes complex
- Would need to merge common fields + marketplace defaults

### Option 3: Base Config + Marketplace Extensions (RECOMMENDED)
**Approach**: Split item configs into common base + marketplace-specific extensions

```python
# Store common config (works for all marketplaces)
self.config.item["tractor"] = ItemConfig(
    name="tractor",
    search_phrases=["tractor loader backhoe"],
    keywords=["..."],
    marketplace=None,
    # Only common MarketItemCommonConfig fields
)

# Store marketplace-specific overrides separately
self.config.item_marketplace_overrides["tractor"] = {
    "facebook": {"availability": ["in"], "delivery_method": ["local_pick_up"]},
    "craigslist": {"search_distance": 250, "posted_today": True}
}

# During scheduling, merge base + marketplace-specific:
base_config = self.config.item["tractor"]
fb_overrides = self.config.item_marketplace_overrides["tractor"].get("facebook", {})
fb_config = FacebookMarketplace.get_item_config(
    **base_config.to_dict(),  # Common fields
    **fb_overrides  # FB-specific fields
)
```

**Pros**:
- Validates common fields at load time
- Maintains single source for shared config
- Minimal changes to existing code structure
- Easy to understand user config

**Cons**:
- Need new storage for marketplace-specific overrides
- Slightly more complex config file format

### Option 4: Generic ItemConfig With Dynamic Fields
**Approach**: Single ItemConfig that holds all possible fields from all marketplaces

```python
@dataclass
class UniversalItemConfig(ItemConfig):
    # Facebook fields
    availability: List[str] | None = None
    delivery_method: List[str] | None = None
    date_listed: List[int] | None = None

    # Craigslist fields
    search_distance: int | None = None
    posted_today: bool | None = None
    has_image: bool | None = None
    search_nearby: bool | None = None
    bundle_duplicates: bool | None = None
    crypto_ok: bool | None = None

    # Future marketplace fields...
```

**Pros**:
- Simplest implementation
- No changes to storage structure
- Works with existing code flow

**Cons**:
- **TERRIBLE DESIGN**: Violates separation of concerns
- Every marketplace sees all fields from all other marketplaces
- Config bloat grows with each marketplace
- No type safety for marketplace-specific fields
- Confusing for users (why can I set `availability` for Craigslist?)

## Recommended Solution: Option 3 (Base + Extensions)

### Implementation Plan

#### 1. Update TOML Config Format

**Current format:**
```toml
[item.tractor]
search_phrases = "tractor loader backhoe"
keywords = "(Kubota AND ...)"
min_price = 5000
max_price = 30000
# marketplace not specified = search all
```

**New format (backward compatible):**
```toml
[item.tractor]
search_phrases = "tractor loader backhoe"
keywords = "(Kubota AND ...)"
min_price = 5000
max_price = 30000

# Optional marketplace-specific overrides
[item.tractor.facebook]
availability = ["in"]
delivery_method = ["local_pick_up"]
date_listed = [1]  # Past 24 hours

[item.tractor.craigslist]
search_distance = 250
posted_today = true
has_image = true
category = "cta"  # cars+trucks
```

#### 2. Update Config Class (config.py)

```python
@dataclass
class Config(BaseConfig):
    marketplace: Dict[str, MarketplaceConfig] = field(default_factory=dict)
    item: Dict[str, ItemConfig] = field(default_factory=dict)

    # NEW: Store marketplace-specific item overrides
    item_marketplace_config: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    # Structure: item_marketplace_config[item_name][marketplace_name] = {field: value}

    user: Dict[str, NotificationConfig] = field(default_factory=dict)
    ai: Dict[str, AIConfig] = field(default_factory=dict)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
```

#### 3. Update Config Loading

```python
def load_items(self, config):
    for item_name, item_config in config["item"].items():
        # Separate base config from marketplace-specific subsections
        base_config = {}
        marketplace_configs = {}

        for key, value in item_config.items():
            if isinstance(value, dict) and key in supported_marketplaces:
                # This is a marketplace-specific subsection
                marketplace_configs[key] = value
            else:
                # This is a base config field
                base_config[key] = value

        # Create base ItemConfig with only common fields
        # Use first marketplace class to create config, but only pass common fields
        first_marketplace_class = list(supported_marketplaces.values())[0]
        self.item[item_name] = first_marketplace_class.get_item_config(
            name=item_name,
            marketplace=base_config.get("marketplace"),
            **{k: v for k, v in base_config.items()
               if k in ItemConfig.__dataclass_fields__ or k in MarketItemCommonConfig.__dataclass_fields__}
        )

        # Store marketplace-specific overrides
        if marketplace_configs:
            self.item_marketplace_config[item_name] = marketplace_configs
```

#### 4. Update Scheduling (monitor.py)

```python
def schedule_jobs(self):
    for marketplace_config in self.config.marketplace.values():
        marketplace_class = supported_marketplaces[marketplace_config.market_type]
        marketplace = marketplace_class(...)

        for item_name, base_item_config in self.config.item.items():
            if base_item_config.marketplace is None or base_item_config.marketplace == marketplace_config.name:
                # Get marketplace-specific overrides if they exist
                marketplace_overrides = self.config.item_marketplace_config.get(
                    item_name, {}
                ).get(marketplace_config.name, {})

                # Merge base config + marketplace-specific config + marketplace defaults
                merged_config = {
                    **base_item_config.to_dict(),  # Base item config
                    **marketplace_overrides,  # Marketplace-specific overrides from TOML
                }

                # Filter to only include fields valid for this marketplace's ItemConfig
                valid_fields = set(marketplace_class.ItemConfigClass.__dataclass_fields__.keys())
                filtered_config = {k: v for k, v in merged_config.items() if k in valid_fields}

                # Create marketplace-specific config
                marketplace_item_config = marketplace_class.get_item_config(**filtered_config)

                # Schedule with the correct config type
                scheduled.do(
                    self.search_item,
                    marketplace_config,
                    marketplace,
                    marketplace_item_config,
                ).tag(marketplace_item_config.name)
```

#### 5. Add ItemConfigClass to Marketplace Classes

```python
class FacebookMarketplace(Marketplace[FacebookMarketplaceConfig, FacebookItemConfig]):
    ItemConfigClass = FacebookItemConfig

    @classmethod
    def get_item_config(cls, **kwargs) -> FacebookItemConfig:
        return FacebookItemConfig(**kwargs)

class CraigslistMarketplace(Marketplace[CraigslistMarketplaceConfig, CraigslistItemConfig]):
    ItemConfigClass = CraigslistItemConfig

    @classmethod
    def get_item_config(cls, **kwargs) -> CraigslistItemConfig:
        return CraigslistItemConfig(**kwargs)
```

### Migration Path

1. **Backward Compatibility**: Old config files (without marketplace subsections) continue to work
2. **Gradual Adoption**: Users can add marketplace-specific sections as needed
3. **Validation**: Warn users if they set marketplace-specific fields in base config that will be ignored

### Edge Cases to Handle

1. **Conflicting Fields**: What if user sets `category` in base AND in `[item.tractor.facebook]`?
   - **Resolution**: Marketplace-specific overrides take precedence

2. **Marketplace-Specific Fields in Base Config**: What if user sets `search_distance` in base `[item.tractor]`?
   - **Resolution**: Ignore with warning - only valid in `[item.tractor.craigslist]`

3. **searched_count Tracking**: How to track per-marketplace vs overall?
   - **Resolution**: Keep in base ItemConfig, increments each search regardless of marketplace

4. **Statistics**: Should stats be per-marketplace or combined?
   - **Resolution**: Current stats are per-item, keep that way. Consider adding marketplace breakdown.

## Alternative: Simpler Filtered Approach

If the above is too complex, a simpler approach:

### Filter Fields When Creating Marketplace Configs

```python
def get_valid_fields_for_marketplace(marketplace_class):
    """Get all valid field names for a marketplace's ItemConfig"""
    return set(marketplace_class.ItemConfigClass.__dataclass_fields__.keys())

def schedule_jobs(self):
    for item_config in self.config.item.values():
        if item_config.marketplace is None or item_config.marketplace == marketplace_config.name:
            # Get valid fields for this marketplace
            valid_fields = get_valid_fields_for_marketplace(marketplace_class)

            # Filter the config to only include valid fields
            filtered_dict = {
                k: v for k, v in item_config.__dict__.items()
                if k in valid_fields
            }

            # Create marketplace-specific config with only valid fields
            marketplace_item_config = marketplace_class.get_item_config(**filtered_dict)
```

**Pros**:
- Much simpler implementation
- Minimal changes to existing code
- No new config format needed

**Cons**:
- Can't set marketplace-specific fields in TOML (they'd be rejected at load time)
- Loss of flexibility for power users
- Silently ignores fields user might have intended

## Questions for Discussion

1. **Do we need marketplace-specific overrides in TOML?** Or is it acceptable to only use marketplace-level defaults?

2. **Should items inherit marketplace-specific fields from marketplace config?**
   - Example: If `[marketplace.craigslist]` sets `search_distance = 250`, should all items inherit it?
   - Current: YES (via defaults in marketplace config)
   - Proposal: Keep this behavior

3. **Statistics granularity**: Do we want per-marketplace stats or just per-item?

4. **Config validation**: Should we error/warn when marketplace-specific fields appear in base item config?

## Recommendation

**Start with the Simpler Filtered Approach**:
1. Keep current config format
2. Filter item config fields to only include valid ones for each marketplace
3. Users rely on marketplace-level defaults for marketplace-specific settings
4. If users need per-item marketplace customization, add Option 3 (subsections) later

This gives us:
- Quick fix to unblock development
- Minimal risk
- Clear upgrade path to full subsection support if needed

**Implementation steps:**
1. Add `ItemConfigClass` attribute to each Marketplace class
2. Create `get_valid_fields()` helper function
3. Update `schedule_jobs()` to filter fields before creating config
4. Test with current config (tractor item searching both marketplaces)
5. Document limitation: can't set marketplace-specific fields per-item (use marketplace defaults)
