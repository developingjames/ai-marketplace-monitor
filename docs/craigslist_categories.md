# Craigslist Category Codes

This document lists Craigslist category codes for use in the `category` configuration.

## What are Category Codes?

Craigslist organizes listings into categories. When you search, you can optionally specify a category to narrow down your results. If no category is specified, the default is `sss` (all for sale).

## How to Use Categories

In your configuration file:

```toml
[item.car]
marketplace = 'craigslist'
search_phrases = 'honda civic'
category = 'cta'  # Cars & Trucks
```

## Available Categories

### Vehicles

| Category | Code | Description |
|----------|------|-------------|
| Cars & Trucks | `cta` | Automobiles for sale |
| Motorcycles | `mca` | Motorcycles and scooters |
| Boats | `boa` | Boats and watercraft |
| RVs & Campers | `rva` | Recreational vehicles and campers |
| ATVs, UTVs, Snowmobiles | `sna` | Off-road vehicles |
| Auto Parts | `pta` | Car parts and accessories |
| Motorcycle Parts | `mpa` | Motorcycle parts and accessories |
| Boat Parts | `bpa` | Boat parts and accessories |
| Aviation | `ava` | Aircraft and aviation equipment |
| Heavy Equipment | `hva` | Construction and industrial equipment |
| Trailers | `tra` | Utility and cargo trailers |
| Wheels & Tires | `wta` | Wheels, tires, and related items |

### Electronics & Computers

| Category | Code | Description |
|----------|------|-------------|
| Computers | `sya` | Desktop and laptop computers |
| Computer Parts | `syp` | Computer components and accessories |
| Electronics | `ela` | Consumer electronics |
| Cell Phones | `moa` | Mobile phones and accessories |
| Photo & Video | `pha` | Cameras and video equipment |
| Video Gaming | `vga` | Gaming consoles and games |

### Home & Garden

| Category | Code | Description |
|----------|------|-------------|
| Furniture | `fua` | Home furniture |
| Appliances | `ppa` | Home appliances |
| Household Items | `hsa` | General household goods |
| Tools | `tla` | Hand and power tools |
| Materials | `maa` | Building materials |
| Farm & Garden | `gra` | Garden equipment and supplies |
| Home Improvement | N/A | (Use general or furniture categories) |

### Lifestyle & Hobbies

| Category | Code | Description |
|----------|------|-------------|
| Sporting Goods | `sga` | Sports equipment and gear |
| Bicycles | `bia` | Bikes and cycling equipment |
| Bicycle Parts | `bip` | Bike parts and accessories |
| Musical Instruments | `msa` | Instruments and music equipment |
| Arts & Crafts | `ara` | Art supplies and handmade items |
| Collectibles | `cba` | Collectible items |
| Antiques | `ata` | Antique items |
| Books | `bka` | Books and magazines |
| CDs, DVDs, VHS | `ema` | Media and entertainment |
| Toys & Games | `taa` | Children's toys and board games |

### Fashion & Accessories

| Category | Code | Description |
|----------|------|-------------|
| Clothing & Accessories | `cla` | Apparel and fashion items |
| Jewelry | `jwa` | Jewelry and watches |
| Health & Beauty | `haa` | Beauty and personal care products |

### Family & Kids

| Category | Code | Description |
|----------|------|-------------|
| Baby & Kid Stuff | `baa` | Baby items and children's goods |

### Other

| Category | Code | Description |
|----------|------|-------------|
| All For Sale | `sss` | Search all categories (default) |
| Free Stuff | `zip` | Free items |
| General For Sale | `foa` | General miscellaneous items |
| Garage Sales | `gms` | Multi-item garage/yard sales |
| Wanted | `waa` | Wanted to buy postings |
| Barter | `bar` | Trade/barter items |
| Business | `bfa` | Business equipment and supplies |
| Tickets | `tia` | Event tickets |
| Office Supplies | N/A | (Use business category) |

## Configuration Examples

### Single Category Search

```toml
[item.laptop]
marketplace = 'craigslist'
search_phrases = 'macbook pro'
category = 'sya'  # Computers
min_price = 500
max_price = 1500
```

### All Categories (Default)

```toml
[item.gopro]
marketplace = 'craigslist'
search_phrases = 'gopro'
# No category specified = searches all for sale categories (sss)
```

### Multiple Items, Different Categories

```toml
[item.bike]
marketplace = 'craigslist'
search_phrases = 'road bike'
category = 'bia'  # Bicycles

[item.car]
marketplace = 'craigslist'
search_phrases = 'toyota camry'
category = 'cta'  # Cars & Trucks

[item.furniture]
marketplace = 'craigslist'
search_phrases = 'dining table'
category = 'fua'  # Furniture
```

## Notes

- Using specific categories can significantly improve search relevance
- Some items might appear in multiple categories (e.g., exercise equipment could be in sporting goods or household)
- The `sss` (all for sale) category is used when no category is specified
- Free stuff (`zip`) is a popular category for finding free items
- Category codes are consistent across all Craigslist locations

## Finding Category Codes

To find additional category codes:

1. Visit your local Craigslist site
2. Navigate to the "for sale" section
3. Click on a category
4. Look at the URL: `https://CITY.craigslist.org/search/CATEGORY`
5. The `CATEGORY` part is the code to use in your configuration
