# Pokemon Scalping Bot

Automated checkout bot for Pokemon TCG products across all major retailers. Monitors for restocks via web scraping and Discord alerts, then auto-checkouts at maximum speed.

## Supported Retailers

| Retailer | Checkout Type | Features |
|---|---|---|
| Pokemon Center | Guest checkout | No account needed, address jigging |
| Target | Account-based | Store pickup + shipping |
| Walmart | Account-based | Walmart+ support |
| Amazon | 1-Click / Buy Now | Prime eligibility checking |
| Best Buy | Account-based | Queue/waiting room handling |
| TCGPlayer | Marketplace | Seller rating filtering, price optimization |
| eBay | BIN Sniper | Buy It Now sniping, feedback filtering |

## Features

- **Async monitoring** - Poll product pages every 3s with near-zero delay via aiohttp
- **Discord integration** - Listen to restock Discord channels for instant alerts
- **Auto-checkout** - Full automated checkout flow with Selenium
- **Anti-detection** - Undetected ChromeDriver + randomized browser fingerprints
- **Address jigging** - Generate profile variants to bypass purchase limits
- **CAPTCHA solving** - 2Captcha / CapMonster integration for reCAPTCHA and hCaptcha
- **Proxy rotation** - Round-robin, random, or sticky proxy strategies with health checks
- **IMAP monitoring** - Extract OTP codes from verification emails automatically
- **Encrypted profiles** - Payment data encrypted at rest with Fernet
- **Discord notifications** - Rich embeds for stock alerts, checkout results, errors
- **SMS alerts** - Optional Twilio SMS for critical notifications
- **Streamlit dashboard** - Real-time monitoring UI with stats and logs
- **Dry run mode** - Test the full flow without placing real orders

## Quick Start

```bash
# Clone the repo
git clone https://github.com/huntedtrader/pokemon-scalping-bot.git
cd pokemon-scalping-bot

# Install dependencies
pip install -r requirements.txt

# Copy and configure
cp config/config.yaml.example config/config.yaml
# Edit config/config.yaml with your profiles, products, and API keys

# Set up profile (interactive)
python bot.py --setup

# Test with dry run
python bot.py --dry-run

# Run the bot
python bot.py

# Monitor only (no checkout)
python bot.py --monitor-only

# Launch dashboard
python bot.py --dashboard
```

## Configuration

Edit `config/config.yaml`:

```yaml
general:
  dry_run: true              # Set false for real purchases
  monitor_interval: 3.0      # Seconds between stock checks
  max_concurrent_tasks: 5    # Parallel checkout attempts

profiles:
  - name: "My Profile"
    first_name: "John"
    last_name: "Doe"
    email: "john@gmail.com"
    # ... shipping, billing, payment details

products:
  - url: "https://www.pokemoncenter.com/product/..."
    retailer: "pokemon_center"
    max_price: 54.99
    enabled: true

discord:
  webhook_url: "https://discord.com/api/webhooks/..."
  bot_token: "your-bot-token"
  monitor_channels: ["123456789"]
```

## Architecture

```
pokemon-scalping-bot/
├── bot.py              # CLI entry point
├── dashboard.py        # Streamlit dashboard
├── config/
│   └── config.yaml     # Configuration
├── core/
│   ├── monitor.py      # Stock monitoring (scraper + Discord)
│   ├── checkout.py     # Base checkout class
│   ├── task_manager.py # Checkout orchestrator
│   ├── profile.py      # Profile management + encryption
│   ├── proxy_manager.py# Proxy pool + rotation
│   ├── imap_monitor.py # Email OTP extraction
│   └── notifier.py     # Discord + SMS notifications
├── retailers/
│   ├── pokemon_center.py
│   ├── target.py
│   ├── walmart.py
│   ├── amazon.py
│   ├── bestbuy.py
│   ├── tcgplayer.py
│   └── ebay.py
└── utils/
    ├── jig.py          # Address/name jigging
    ├── fingerprint.py  # Browser fingerprint randomization
    ├── captcha.py      # CAPTCHA solver integration
    └── logger.py       # Colored logging
```

## CLI Commands

```bash
python bot.py                                    # Full bot (monitor + checkout)
python bot.py --monitor-only                     # Monitor only, send alerts
python bot.py --dry-run                          # Test without placing orders
python bot.py --test-checkout URL RETAILER       # Test checkout flow
python bot.py --setup                            # Interactive profile setup
python bot.py --health-check                     # Check proxy health
python bot.py --dashboard                        # Launch Streamlit UI
python bot.py --log-level DEBUG                  # Verbose logging
```

## Dependencies

- `aiohttp` - Async HTTP for stock monitoring
- `selenium` + `undetected-chromedriver` - Browser automation
- `cryptography` - Profile encryption
- `pyyaml` - Configuration
- `streamlit` - Dashboard UI

## Disclaimer

This bot is for educational purposes. Use responsibly and in compliance with retailer terms of service.
