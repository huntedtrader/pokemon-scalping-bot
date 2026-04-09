# Pokemon Scalping Bot

Automated Checkout (ACO) service for Pokemon TCG products. Monitors for restocks via web scraping and Discord alerts, then auto-checkouts on behalf of customers at maximum speed across all major retailers.

Operates on a **PAS (Pay After Success)** model -- customers only pay fees after a successful checkout. All customer data is encrypted at rest and automatically deleted after fulfillment.

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

- **Customer management** - Register customers, store encrypted profiles, track orders and PAS fees
- **PAS billing** - Pay After Success fee model with Stripe integration and auto-suspension for non-payment
- **Async monitoring** - Poll product pages every 3s with near-zero delay via aiohttp
- **Discord integration** - Listen to restock Discord channels for instant alerts
- **Auto-checkout** - Full automated checkout flow with Selenium on behalf of customers
- **Anti-detection** - Undetected ChromeDriver + randomized browser fingerprints
- **Address jigging** - Generate profile variants to bypass purchase limits
- **CAPTCHA solving** - 2Captcha / CapMonster integration for reCAPTCHA and hCaptcha
- **Proxy rotation** - Round-robin, random, or sticky proxy strategies with health checks
- **Data security** - Fernet encryption at rest, automatic purge after checkout
- **Discord notifications** - Rich embeds for stock alerts, checkout results, errors
- **Streamlit dashboard** - Full operator UI with customer mgmt, orders, billing, live logs
- **Dry run mode** - Test the full flow without placing real orders

## PAS Fee Schedule

| Product Type | Fee Range |
|---|---|
| Tech Sticker / Blister | $1.50 - $3.00 |
| Booster Bundle | $2.00 - $7.00 |
| Tin | $2.00 - $5.00 |
| ETB (Elite Trainer Box) | $5.00 - $15.00 |
| Collection Box | $5.00 - $20.00 |
| Booster Box | $10.00 - $25.00 |
| PC ETB (Pokemon Center Exclusive) | $15.00 - $40.00 |
| UPC (Ultra Premium Collection) | $20.00 - $50.00 |

Bulk customers (5+ profiles) receive a 20% discount.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/huntedtrader/pokemon-scalping-bot.git
cd pokemon-scalping-bot

# Install dependencies
pip install -r requirements.txt

# Copy and configure
cp config/config.yaml.example config/config.yaml
# Edit config/config.yaml with your products and API keys

# Register a customer (interactive)
python bot.py --add-customer

# List customers
python bot.py --list-customers

# Test with dry run
python bot.py --dry-run

# Run the ACO service
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
├── dashboard.py        # Streamlit operator dashboard (7 pages)
├── config/
│   └── config.yaml     # Service configuration
├── core/
│   ├── customer.py     # Customer management + PAS billing
│   ├── monitor.py      # Stock monitoring (scraper + Discord)
│   ├── checkout.py     # Base checkout class
│   ├── task_manager.py # Checkout orchestrator
│   ├── profile.py      # Profile encryption
│   ├── proxy_manager.py# Proxy pool + rotation
│   └── notifier.py     # Discord + SMS notifications
├── retailers/
│   ├── pokemon_center.py
│   ├── target.py
│   ├── walmart.py
│   ├── amazon.py
│   ├── bestbuy.py
│   ├── tcgplayer.py
│   └── ebay.py
├── utils/
│   ├── jig.py          # Address/name jigging
│   ├── fingerprint.py  # Browser fingerprint randomization
│   ├── captcha.py      # CAPTCHA solver integration
│   └── logger.py       # Colored logging
└── data/
    └── customers.db    # SQLite (customers, profiles, orders)
```

## How It Works

1. **Customer onboarding** - Customer provides checkout info (card, address, login) via CLI or dashboard
2. **Data encrypted** - All sensitive data encrypted with Fernet at rest in SQLite
3. **Monitoring** - Bot monitors product pages + Discord channels for restocks
4. **Auto-checkout** - On restock, bot launches Selenium with stealth fingerprint, checks out using customer's profile
5. **PAS notification** - Customer notified of success via Discord webhook, 24h to acknowledge
6. **Payment** - Customer pays PAS fee via Stripe within 72h
7. **Data purge** - Customer's sensitive data automatically deleted after fulfillment

## CLI Commands

```bash
python bot.py                                    # Full ACO service
python bot.py --monitor-only                     # Monitor only, send alerts
python bot.py --dry-run                          # Test without placing orders
python bot.py --test-checkout URL RETAILER       # Test checkout flow
python bot.py --add-customer                     # Register new customer (interactive)
python bot.py --list-customers                   # List all customers
python bot.py --health-check                     # Check proxy health
python bot.py --dashboard                        # Launch Streamlit UI
python bot.py --log-level DEBUG                  # Verbose logging
```

## Dashboard Pages

| Page | Description |
|---|---|
| Dashboard | Service overview with KPIs, recent orders, monitored products |
| Customers | Customer list with status, tier, checkout count, fees |
| Orders | Full order history with status and fee tracking |
| Add Customer | Registration form with encrypted profile storage |
| PAS Billing | Fee schedule, overdue payments, revenue summary |
| Monitor Log | Live bot log with filtering |
| Settings | Service configuration viewer and quick actions |

## Dependencies

- `aiohttp` - Async HTTP for stock monitoring
- `selenium` + `undetected-chromedriver` - Browser automation
- `cryptography` - Profile encryption
- `pyyaml` - Configuration
- `streamlit` - Dashboard UI

## Disclaimer

This bot is for educational purposes. Use responsibly and in compliance with retailer terms of service.
