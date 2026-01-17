![AI Marketplace Monitor](docs/AIMM_neutral.png)

<div align="center">

[![PyPI - Version](https://img.shields.io/pypi/v/ai-marketplace-monitor.svg)](https://pypi.python.org/pypi/ai-marketplace-monitor)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ai-marketplace-monitor.svg)](https://pypi.python.org/pypi/ai-marketplace-monitor)
[![Tests](https://github.com/BoPeng/ai-marketplace-monitor/workflows/tests/badge.svg)](https://github.com/BoPeng/ai-marketplace-monitor/actions?workflow=tests)
[![Codecov](https://codecov.io/gh/BoPeng/ai-marketplace-monitor/branch/main/graph/badge.svg)](https://codecov.io/gh/BoPeng/ai-marketplace-monitor)
[![Read the Docs](https://readthedocs.org/projects/ai-marketplace-monitor/badge/)](https://ai-marketplace-monitor.readthedocs.io/)
[![PyPI - License](https://img.shields.io/pypi/l/ai-marketplace-monitor.svg)](https://pypi.python.org/pypi/ai-marketplace-monitor)

[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)

</div>

An intelligent tool that monitors multiple online marketplaces using AI to help you find the best deals. Get instant notifications when items matching your criteria are posted, with AI-powered analysis of each listing.

**Supported Marketplaces:**
- 🛍️ Facebook Marketplace
- 📋 Craigslist
- 🚜 TractorHouse
- 🔨 Auction Ohio
- 🏛️ GovDeals (Government Auctions)
- 📦 Proxibid
- 🌾 Purple Wave
- 🏗️ RB Auction (Ritchie Bros)

**📚 [Read the Full Documentation](https://ai-marketplace-monitor.readthedocs.io/)**

![Search In Action](docs/search_in_action.png)

Example notification from PushBullet:

```
Found 1 new gopro from facebook
[Great deal (5)] Go Pro hero 12
$180, Houston, TX
https://facebook.com/marketplace/item/1234567890
AI: Great deal; A well-priced, well-maintained camera meets all search criteria, with extra battery and charger.
```

**Table of Contents:**

- [✨ Key Features](#-key-features)
- [🚀 Quick Start](#-quick-start)
- [💡 Example Usage](#-example-usage)
- [📚 Documentation](#-documentation)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)
- [💬 Support](#-support)
- [🙏 Credits](#-credits)

## ✨ Key Features

🔍 **Smart Search**

- Search 8 different marketplaces simultaneously
- Support for general marketplaces (Facebook, Craigslist) and specialized auction sites
- Search multiple products using keywords with Boolean logic
- Filter by price, location, and auction-specific criteria
- Exclude irrelevant results and spammers
- Support for marketplace-specific categories and filters
- Track auction end times and bid counts

🤖 **AI-Powered**

- Intelligent listing evaluation
- Smart recommendations
- Multiple AI service providers supported
- Self-hosted model option (Ollama)

📱 **Notifications**

- PushBullet, PushOver, Telegram, or Ntfy notifications
- HTML email notifications with images
- Markdown file output for each listing
- Customizable notification levels
- Repeated notification options

🌎 **Location Support**

- Multi-city search
- Pre-defined regions (USA, Canada, etc.)
- Customizable search radius (Facebook, Craigslist, GovDeals, Purple Wave)
- Regional filtering (RB Auction)
- Flexible seller location filtering
- Zip code + radius search for auction marketplaces

## 🚀 Quick Start

> **⚠️ Legal Notice**: Facebook's EULA prohibits automated data collection without authorization. This tool was developed for personal, hobbyist use only. You are solely responsible for ensuring compliance with platform terms and applicable laws.

### Installation

```bash
pip install ai-marketplace-monitor
playwright install
```

### Basic Configuration

Create a configuration file at:
- **Linux/Mac**: `~/.ai-marketplace-monitor/config.toml`
- **Windows**: `C:\Users\<username>\.ai-marketplace-monitor\config.toml`

```toml
[marketplace.facebook]
search_city = 'houston'  # Replace with your city

[item.gopro]
search_phrases = 'Go Pro Hero 11'
min_price = 100
max_price = 300

[user.me]
pushbullet_token = 'your_token_here'  # Get from pushbullet.com
```

> **Note**: The config file, cache database, and logs are all stored in the `.ai-marketplace-monitor` directory in your home folder.

### Run the Monitor

**Production (from PyPI):**
```bash
ai-marketplace-monitor
```

**Development (from source):**
```bash
# Install in editable/development mode (recommended - changes take effect immediately)
cd /path/to/ai-marketplace-monitor
pip install -e .
ai-marketplace-monitor

# Alternative: Using Python directly without install
python -m ai_marketplace_monitor.cli
```

The program will open a browser, search marketplaces, and notify you of matching items.

## 💡 Example Usage

**Find GoPro cameras under $300:**

```toml
[item.gopro]
search_phrases = 'Go Pro Hero'
keywords = "('Go Pro' OR gopro) AND (11 OR 12 OR 13)"
min_price = 100
max_price = 300
```

**Search nationwide with shipping:**

```toml
[item.rare_item]
search_phrases = 'vintage collectible'
search_region = 'usa'
delivery_method = 'shipping'
seller_locations = []
```

**AI-powered filtering:**

```toml
[ai.openai]
api_key = 'your_openai_key'

[item.camera]
description = '''High-quality DSLR camera in good condition.
Exclude listings with water damage or missing parts.'''
rating = 4  # Only notify for 4+ star AI ratings
```

**Save listings as markdown files:**

```toml
[user.me]
markdown_output_dir = 'D:/marketplace-listings'
markdown_include_frontmatter = true  # Add YAML frontmatter for Obsidian/Logseq
notify_with = ['markdown']  # Or combine: ['markdown', 'email', 'telegram']
```

Each listing is saved as a separate markdown file with title, price, description, seller info, images, and AI evaluation. Perfect for building a searchable database in tools like Obsidian or for offline browsing.

### Auction Marketplace Examples

**Search Government Auctions (GovDeals):**

```toml
[marketplace.govdeals_ohio]
market_type = "govdeals"
enabled = true
zipcode = "43311"  # Ohio zip code
miles = 250        # Search within 250 miles

[item.govt_equipment]
enabled = true
marketplace = ["govdeals_ohio"]
search_phrases = ["trailer", "truck", "equipment"]
keywords = "trailer OR truck OR equipment"
antikeywords = "parts salvage"
min_price = 500
max_price = 25000
```

**Search Online Auctions (Auction Ohio, Proxibid):**

```toml
[marketplace.auctionohio]
market_type = "auctionohio"
enabled = true

[marketplace.proxibid]
market_type = "proxibid"
enabled = true

[item.farm_equipment]
enabled = true
marketplace = ["auctionohio", "proxibid"]
search_phrases = ["tractor", "farm equipment"]
keywords = "tractor AND (Kubota OR 'John Deere' OR Mahindra)"
antikeywords = "toy model parts"
min_price = 5000
max_price = 50000
```

**Search Construction Equipment (Purple Wave):**

```toml
[marketplace.purplewave_midwest]
market_type = "purplewave"
enabled = true
zipcode = "66062"  # Kansas zip code
miles = 300        # Search within 300 miles

[item.excavator]
enabled = true
marketplace = ["purplewave_midwest"]
search_phrases = ["excavator", "backhoe", "skid steer"]
keywords = "excavator OR backhoe OR 'skid steer'"
antikeywords = "attachment bucket"
min_price = 10000
max_price = 100000
```

**Search Heavy Equipment (RB Auction):**

```toml
[marketplace.rbauction_usa]
market_type = "rbauction"
enabled = true
region = "USA"  # Regional filtering

[item.heavy_equipment]
enabled = true
marketplace = ["rbauction_usa"]
search_phrases = ["dozer", "crane", "forklift"]
keywords = "dozer OR crane OR forklift"
min_price = 20000
max_price = 200000
```

**Search Multiple Marketplaces at Once:**

```toml
[item.general_tractor]
enabled = true
# Search across all auction marketplaces simultaneously
marketplace = ["auctionohio", "govdeals_ohio", "proxibid", "purplewave_midwest", "rbauction_usa"]
search_phrases = ["tractor"]
keywords = "tractor"
antikeywords = "garden lawn toy"
min_price = 1000
max_price = 30000
cache_ignore_price_changes = true
```

**Marketplace-Specific Features:**

- **GovDeals & Purple Wave**: Support `zipcode` and `miles` parameters for radius-based search
- **RB Auction**: Supports `region` parameter (e.g., "USA", "Canada", "Europe")
- **Auction Ohio, Proxibid**: No location filtering required
- **All auction marketplaces**: Track auction end times, time remaining, bid counts, and lot numbers

## 📚 Documentation

For detailed information on setup and advanced features, see the comprehensive documentation:

- **[📖 Full Documentation](https://ai-marketplace-monitor.readthedocs.io/)** - Complete guide and reference
- **[🚀 Quick Start Guide](https://ai-marketplace-monitor.readthedocs.io/en/latest/quickstart.html)** - Get up and running in 10 minutes
- **[🔍 Features Overview](https://ai-marketplace-monitor.readthedocs.io/en/latest/features.html)** - Complete feature list
- **[📱 Usage Guide](https://ai-marketplace-monitor.readthedocs.io/en/latest/usage.html)** - Command-line options and tips
- **[🔧 Configuration Guide](https://ai-marketplace-monitor.readthedocs.io/en/latest/configuration-guide.html)** - Notifications, AI prompts, multi-location search
- **[⚙️ Configuration Reference](https://ai-marketplace-monitor.readthedocs.io/en/latest/configuration.html)** - Complete configuration reference

### Key Topics Covered in Documentation

**Notification Setup:**

- Email (SMTP), PushBullet, PushOver, Telegram, Ntfy
- Markdown file output with optional YAML frontmatter
- Multi-user configurations
- HTML email templates

**AI Integration:**

- OpenAI, DeepSeek, Ollama setup
- Custom prompt configuration
- Rating thresholds and filtering

**Advanced Search:**

- Multi-city and region search
- Currency conversion
- Keyword filtering with Boolean logic
- Proxy/anonymous searching

**Configuration:**

- TOML file structure
- Environment variables
- Multiple marketplace support
- Language/translation support

## 🤝 Contributing

Contributions are welcome! Here are some ways you can contribute:

- 🐛 Report bugs and issues
- 💡 Suggest new features
- 🔧 Submit pull requests
- 📚 Improve documentation
- 🏪 Add support for new marketplaces
- 🌍 Add support for new regions and languages
- 🤖 Add support for new AI providers
- 📱 Add new notification methods

Please read our [Contributing Guidelines](https://ai-marketplace-monitor.readthedocs.io/en/latest/contributing.html) before submitting a Pull Request.

## 📜 License

This project is licensed under the **Affero General Public License (AGPL)**. For the full terms and conditions, please refer to the official [GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.en.html).

## 💬 Support

We provide multiple ways to access support and contribute to AI Marketplace Monitor:

- 📖 [Documentation](https://ai-marketplace-monitor.readthedocs.io/) - Comprehensive guides and instructions
- 🤝 [Discussions](https://github.com/BoPeng/ai-marketplace-monitor/discussions) - Community support and ideas
- 🐛 [Issues](https://github.com/BoPeng/ai-marketplace-monitor/issues) - Bug reports and feature requests
- 💖 [Become a sponsor](https://github.com/sponsors/BoPeng) - Support development
- 💰 [Donate via PayPal](https://www.paypal.com/donate/?hosted_button_id=3WT5JPQ2793BN) - Alternative donation method

**Important Note:** Due to time constraints, priority support is provided to sponsors and donors. For general questions, please use the GitHub Discussions or Issues.

## 🙏 Credits

- Some of the code was copied from [facebook-marketplace-scraper](https://github.com/passivebot/facebook-marketplace-scraper).
- Region definitions were copied from [facebook-marketplace-nationwide](https://github.com/gmoz22/facebook-marketplace-nationwide/), which is released under an MIT license as of Jan 2025.
- This package was created with [Cookiecutter](https://github.com/cookiecutter/cookiecutter) and the [cookiecutter-modern-pypackage](https://github.com/fedejaure/cookiecutter-modern-pypackage) project template.
