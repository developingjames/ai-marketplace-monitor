# Craigslist City Codes

This document lists common Craigslist city codes (subdomains) for use in the `search_city` configuration.

## How to Find Your City Code

1. Visit [Craigslist](https://www.craigslist.org/)
2. Select your city from the list
3. Look at the URL in your browser: `https://CITYCODE.craigslist.org/`
4. Use the `CITYCODE` part in your configuration

For example, if the URL is `https://houston.craigslist.org/`, use `search_city = 'houston'`.

## Major US Cities

| City | Code | URL |
|------|------|-----|
| Atlanta, GA | atlanta | https://atlanta.craigslist.org/ |
| Austin, TX | austin | https://austin.craigslist.org/ |
| Boston, MA | boston | https://boston.craigslist.org/ |
| Chicago, IL | chicago | https://chicago.craigslist.org/ |
| Dallas, TX | dallas | https://dallas.craigslist.org/ |
| Denver, CO | denver | https://denver.craigslist.org/ |
| Detroit, MI | detroit | https://detroit.craigslist.org/ |
| Houston, TX | houston | https://houston.craigslist.org/ |
| Las Vegas, NV | lasvegas | https://lasvegas.craigslist.org/ |
| Los Angeles, CA | losangeles | https://losangeles.craigslist.org/ |
| Miami, FL | miami | https://miami.craigslist.org/ |
| Minneapolis, MN | minneapolis | https://minneapolis.craigslist.org/ |
| New York, NY | newyork | https://newyork.craigslist.org/ |
| Philadelphia, PA | philadelphia | https://philadelphia.craigslist.org/ |
| Phoenix, AZ | phoenix | https://phoenix.craigslist.org/ |
| Portland, OR | portland | https://portland.craigslist.org/ |
| San Antonio, TX | sanantonio | https://sanantonio.craigslist.org/ |
| San Diego, CA | sandiego | https://sandiego.craigslist.org/ |
| San Francisco, CA | sfbay | https://sfbay.craigslist.org/ |
| Seattle, WA | seattle | https://seattle.craigslist.org/ |
| Washington, DC | washingtondc | https://washingtondc.craigslist.org/ |

## Canadian Cities

| City | Code | URL |
|------|------|-----|
| Calgary, AB | calgary | https://calgary.craigslist.org/ |
| Edmonton, AB | edmonton | https://edmonton.craigslist.org/ |
| Montreal, QC | montreal | https://montreal.craigslist.org/ |
| Ottawa, ON | ottawa | https://ottawa.craigslist.org/ |
| Toronto, ON | toronto | https://toronto.craigslist.org/ |
| Vancouver, BC | vancouver | https://vancouver.craigslist.org/ |
| Winnipeg, MB | winnipeg | https://winnipeg.craigslist.org/ |

## Other Major Cities

For a complete list of all Craigslist sites worldwide, visit: https://www.craigslist.org/about/sites

## Configuration Example

```toml
[marketplace.craigslist]
market_type = 'craigslist'
search_city = 'houston'  # Use the city code from the table above

[item.example]
marketplace = 'craigslist'
search_phrases = 'example item'
# search_city can also be specified per item to override marketplace config
# search_city = 'austin'
```

## Multiple Cities

You can search multiple cities by using a list:

```toml
[marketplace.craigslist]
market_type = 'craigslist'
search_city = ['houston', 'austin', 'dallas']  # Search multiple cities
```

## Regional Search

For region-based searches across multiple cities, use the `search_region` configuration:

```toml
[region.texas]
search_city = ['houston', 'austin', 'dallas', 'sanantonio']

[marketplace.craigslist]
market_type = 'craigslist'

[item.example]
marketplace = 'craigslist'
search_phrases = 'example item'
search_region = 'texas'  # Will search all cities in the texas region
```
