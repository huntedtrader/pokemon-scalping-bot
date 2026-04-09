"""Pokemon ACO (Automated Checkout) Service - Main CLI Entry Point.

Operates as a checkout service for customers. Customers submit their
profiles, we monitor for drops, auto-checkout on their behalf, and
charge a PAS (Pay After Success) fee.

Usage:
    python bot.py                    # Start full bot (monitor + auto-checkout)
    python bot.py --monitor-only     # Monitor only (alerts, no checkout)
    python bot.py --dry-run          # Full flow but skip order submission
    python bot.py --test-checkout    # Test checkout flow on a specific URL
    python bot.py --dashboard        # Launch Streamlit dashboard
    python bot.py --add-customer     # Register a new customer
    python bot.py --health-check     # Check proxy health
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path

import yaml

from core.customer import CustomerManager
from core.monitor import StockMonitor, DiscordMonitor, ProductAlert
from core.notifier import Notifier
from core.profile import ProfileManager
from core.proxy_manager import ProxyManager
from core.task_manager import TaskManager
from utils.logger import setup_logging, get_logger

log = get_logger("main", "system")

BANNER = r"""
 ____       _          _     ____ ___
|  _ \ ___ | | _____  / \   / ___/ _ \
| |_) / _ \| |/ / _ \/  _\ | |  | | | |
|  __/ (_) |   <  __/ /_\  \| |__| |_| |
|_|   \___/|_|\_\___/_/   \_\____\___/

    Pokemon TCG Automated Checkout Service v2.0
    Checkout-as-a-Service for customers
"""


def load_config(path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        print(f"Config not found at {path}")
        print("Copy config/config.yaml.example to config/config.yaml and fill in your details.")
        sys.exit(1)

    with open(config_path) as f:
        return yaml.safe_load(f)


class PokemonACOBot:
    """Main ACO service orchestrator."""

    def __init__(self, config: dict, dry_run: bool = None):
        self.config = config

        if dry_run is not None:
            self.config["general"]["dry_run"] = dry_run

        # Initialize components
        self.proxy_manager = ProxyManager(config.get("proxies", {}))
        self.notifier = Notifier(config)
        self.profile_manager = ProfileManager(config)
        self.customer_manager = CustomerManager()

        self.task_manager = TaskManager(
            config=config,
            profile_manager=self.profile_manager,
            proxy_manager=self.proxy_manager,
            notifier=self.notifier,
            customer_manager=self.customer_manager,
        )

        self.stock_monitor = StockMonitor(
            config=config,
            proxy_manager=self.proxy_manager,
            on_stock_alert=self._on_alert,
        )

        self.discord_monitor = DiscordMonitor(
            config=config,
            on_stock_alert=self._on_alert,
        )

        self._running = False

    async def _on_alert(self, alert: ProductAlert):
        """Handle incoming stock alerts."""
        log.info(
            f"Alert received: {alert.product_name} on {alert.retailer} "
            f"(${alert.price:.2f}) from {alert.source}"
        )
        await self.task_manager.handle_alert(alert)

    async def start(self, monitor_only: bool = False):
        """Start the ACO service."""
        self._running = True
        dry_run = self.config.get("general", {}).get("dry_run", True)

        print(BANNER)
        log.info(f"ACO service starting (dry_run={dry_run}, monitor_only={monitor_only})")
        log.info(f"Operator profiles loaded: {len(self.profile_manager.profiles)}")
        log.info(f"Products monitored: {len(self.stock_monitor.products)}")

        # Customer stats
        service_stats = self.customer_manager.get_service_stats()
        log.info(f"Active customers: {service_stats['active_customers']}")
        log.info(f"Total checkouts: {service_stats['total_checkouts']}")

        if self.proxy_manager.enabled:
            await self.proxy_manager.health_check()
            stats = self.proxy_manager.stats
            log.info(f"Proxies: {stats['active']}/{stats['total']} active")

        # Send startup notification
        await self.notifier.notify_status(
            f"ACO service started - {service_stats['active_customers']} customers, "
            f"monitoring {len(self.stock_monitor.products)} products"
            f" ({'DRY RUN' if dry_run else 'LIVE'})"
        )

        # Start monitors
        tasks = [
            asyncio.create_task(self.stock_monitor.start()),
            asyncio.create_task(self.discord_monitor.start()),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log.info("ACO service shutting down...")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the ACO service gracefully."""
        self._running = False
        await self.stock_monitor.stop()
        await self.discord_monitor.stop()

        # Print final stats
        stats = self.task_manager.get_stats()
        log.info(f"Final stats: {stats}")
        await self.notifier.notify_status(f"ACO service stopped. Stats: {stats}")

    async def test_checkout(self, url: str, retailer: str):
        """Test checkout on a specific URL."""
        log.info(f"Testing checkout: {url} ({retailer})")

        alert = ProductAlert(
            product_name="Test Product",
            retailer=retailer,
            url=url,
            price=0.0,
            in_stock=True,
            source="manual",
        )

        await self.task_manager.handle_alert(alert)
        stats = self.task_manager.get_stats()
        log.info(f"Test complete. Stats: {stats}")


async def run_health_check(config: dict):
    """Run proxy health check."""
    proxy_manager = ProxyManager(config.get("proxies", {}))
    if not proxy_manager.enabled:
        print("Proxies not enabled in config")
        return
    await proxy_manager.health_check()
    stats = proxy_manager.stats
    print(f"\nProxy Health Check Results:")
    print(f"  Total:     {stats['total']}")
    print(f"  Active:    {stats['active']}")
    print(f"  Banned:    {stats['banned']}")
    print(f"  Avg Ping:  {stats['avg_latency_ms']:.0f}ms")


def run_add_customer():
    """Interactive customer onboarding."""
    print("\n=== Add New Customer ===\n")

    cm = CustomerManager()

    discord_id = input("Customer Discord ID: ").strip()
    discord_name = input("Customer Discord Name: ").strip()
    email = input("Customer Email: ").strip()

    print("\nTier options: standard, bulk (15+ profiles), vip")
    tier = input("Tier [standard]: ").strip() or "standard"

    customer = cm.add_customer(discord_id, discord_name, email, tier)
    print(f"\nCustomer registered! ID: {customer.customer_id}")

    # Collect checkout profiles
    print("\n--- Checkout Profile ---")
    print("Enter the customer's checkout details (encrypted at rest, deleted after use).\n")

    retailers = ["pokemon_center", "target", "walmart", "amazon", "bestbuy", "tcgplayer", "ebay"]
    print("Available retailers:", ", ".join(retailers))
    retailer = input("Retailer: ").strip().lower()

    first = input("First Name: ").strip()
    last = input("Last Name: ").strip()
    cust_email = input("Checkout Email: ").strip()
    phone = input("Phone: ").strip()
    addr1 = input("Address Line 1: ").strip()
    addr2 = input("Address Line 2 (optional): ").strip()
    city = input("City: ").strip()
    state = input("State (2-letter): ").strip().upper()
    zipcode = input("ZIP Code: ").strip()

    print("\nPayment Info (encrypted at rest, deleted after checkout):")
    card = input("Card Number: ").strip()
    exp_m = input("Exp Month (MM): ").strip()
    exp_y = input("Exp Year (YYYY): ").strip()
    cvv = input("CVV: ").strip()
    holder = input("Cardholder Name: ").strip()

    profile_data = {
        "first_name": first, "last_name": last, "email": cust_email,
        "phone": phone, "address1": addr1, "address2": addr2,
        "city": city, "state": state, "zip": zipcode, "country": "US",
        "card_number": card, "exp_month": exp_m, "exp_year": exp_y,
        "cvv": cvv, "cardholder": holder,
    }

    profile_id = cm.store_profile(customer.customer_id, retailer, profile_data)
    print(f"\nProfile stored (encrypted): {profile_id}")
    print(f"All sensitive data will be automatically deleted after checkout.")
    print(f"\nCustomer {discord_name} is ready for {retailer.upper()} checkouts!")


def main():
    parser = argparse.ArgumentParser(description="Pokemon TCG ACO Service")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--monitor-only", action="store_true", help="Monitor only, no checkout")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing orders")
    parser.add_argument("--test-checkout", nargs=2, metavar=("URL", "RETAILER"), help="Test checkout on URL")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard")
    parser.add_argument("--add-customer", action="store_true", help="Register a new customer")
    parser.add_argument("--list-customers", action="store_true", help="List all customers")
    parser.add_argument("--health-check", action="store_true", help="Check proxy health")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Load config
    config = load_config(args.config)

    # Handle dashboard launch
    if args.dashboard:
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.port", "8891"])
        return

    # Handle customer management
    if args.add_customer:
        run_add_customer()
        return

    if args.list_customers:
        cm = CustomerManager()
        customers = cm.list_customers()
        if not customers:
            print("No customers registered yet.")
        for c in customers:
            print(
                f"  [{c.status.upper():>9}] {c.customer_id} | {c.discord_name} | "
                f"{c.tier} | checkouts: {c.total_checkouts} | "
                f"owed: ${c.total_fees_owed:.2f}"
            )
        stats = cm.get_service_stats()
        print(f"\nService stats: {stats['active_customers']} active, "
              f"{stats['total_checkouts']} checkouts, "
              f"${stats['total_revenue']:.2f} revenue")
        return

    # Handle health check
    if args.health_check:
        asyncio.run(run_health_check(config))
        return

    # Handle test checkout
    if args.test_checkout:
        url, retailer = args.test_checkout
        bot = PokemonACOBot(config, dry_run=True)
        asyncio.run(bot.test_checkout(url, retailer))
        return

    # Main bot
    bot = PokemonACOBot(config, dry_run=args.dry_run or None)

    # Graceful shutdown
    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        log.info(f"Received signal {sig}, shutting down...")
        loop.create_task(bot.stop())

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(bot.start(monitor_only=args.monitor_only))
    except KeyboardInterrupt:
        log.info("Interrupted, shutting down...")
        loop.run_until_complete(bot.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
