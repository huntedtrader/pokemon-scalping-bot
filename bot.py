"""Pokemon Scalping Bot - Main CLI Entry Point.

Usage:
    python bot.py                    # Start full bot (monitor + auto-checkout)
    python bot.py --monitor-only     # Monitor only (alerts, no checkout)
    python bot.py --dry-run          # Full flow but skip order submission
    python bot.py --test-checkout    # Test checkout flow on a specific URL
    python bot.py --dashboard        # Launch Streamlit dashboard
    python bot.py --setup            # Interactive profile setup
    python bot.py --health-check     # Check proxy health
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path

import yaml

from core.imap_monitor import ImapMonitor
from core.monitor import StockMonitor, DiscordMonitor, ProductAlert
from core.notifier import Notifier
from core.profile import ProfileManager
from core.proxy_manager import ProxyManager
from core.task_manager import TaskManager
from utils.logger import setup_logging, get_logger

log = get_logger("main", "system")

BANNER = r"""
 ____       _          ____            _
|  _ \ ___ | | _____  / ___|  ___ __ _| |_ __
| |_) / _ \| |/ / _ \ \___ \ / __/ _` | | '_ \
|  __/ (_) |   <  __/  ___) | (_| (_| | | |_) |
|_|   \___/|_|\_\___| |____/ \___\__,_|_| .__/
                                         |_|
    Pokemon TCG Scalping Bot v1.0
    Auto-checkout across all major retailers
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


class PokemonScalpBot:
    """Main bot orchestrator."""

    def __init__(self, config: dict, dry_run: bool = None):
        self.config = config

        if dry_run is not None:
            self.config["general"]["dry_run"] = dry_run

        # Initialize components
        self.proxy_manager = ProxyManager(config.get("proxies", {}))
        self.notifier = Notifier(config)
        self.profile_manager = ProfileManager(config)
        self.imap_monitor = ImapMonitor(config)

        self.task_manager = TaskManager(
            config=config,
            profile_manager=self.profile_manager,
            proxy_manager=self.proxy_manager,
            notifier=self.notifier,
            imap_monitor=self.imap_monitor,
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
        """Start the bot."""
        self._running = True
        dry_run = self.config.get("general", {}).get("dry_run", True)

        print(BANNER)
        log.info(f"Bot starting (dry_run={dry_run}, monitor_only={monitor_only})")
        log.info(f"Profiles loaded: {len(self.profile_manager.profiles)}")
        log.info(f"Products monitored: {len(self.stock_monitor.products)}")

        if self.proxy_manager.enabled:
            await self.proxy_manager.health_check()
            stats = self.proxy_manager.stats
            log.info(f"Proxies: {stats['active']}/{stats['total']} active")

        # Connect IMAP
        self.imap_monitor.connect()

        # Send startup notification
        await self.notifier.notify_status(
            f"Bot started - monitoring {len(self.stock_monitor.products)} products"
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
            log.info("Bot shutting down...")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot gracefully."""
        self._running = False
        await self.stock_monitor.stop()
        await self.discord_monitor.stop()
        self.imap_monitor.disconnect()

        # Print final stats
        stats = self.task_manager.get_stats()
        log.info(f"Final stats: {stats}")
        await self.notifier.notify_status(f"Bot stopped. Stats: {stats}")

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


def run_setup(config: dict):
    """Interactive profile setup."""
    print("\n=== Profile Setup ===\n")

    profile_mgr = ProfileManager(config)

    print("Enter your checkout profile details:")
    first = input("First Name: ").strip()
    last = input("Last Name: ").strip()
    email = input("Email: ").strip()
    phone = input("Phone: ").strip()
    addr1 = input("Address Line 1: ").strip()
    addr2 = input("Address Line 2 (optional): ").strip()
    city = input("City: ").strip()
    state = input("State (2-letter): ").strip().upper()
    zipcode = input("ZIP Code: ").strip()

    print("\nPayment Info (will be encrypted):")
    card = input("Card Number: ").strip()
    exp_m = input("Exp Month (MM): ").strip()
    exp_y = input("Exp Year (YYYY): ").strip()
    cvv = input("CVV: ").strip()
    holder = input("Cardholder Name: ").strip()

    # Encrypt sensitive data
    enc_card = profile_mgr.encrypt_value(card)
    enc_cvv = profile_mgr.encrypt_value(cvv)

    print(f"\nEncrypted card: {enc_card[:30]}...")
    print(f"Encrypted CVV:  {enc_cvv[:30]}...")
    print("\nPaste these encrypted values into config/config.yaml under payment.")
    print("Profile setup complete!")


def main():
    parser = argparse.ArgumentParser(description="Pokemon TCG Scalping Bot")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--monitor-only", action="store_true", help="Monitor only, no checkout")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing orders")
    parser.add_argument("--test-checkout", nargs=2, metavar=("URL", "RETAILER"), help="Test checkout on URL")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard")
    parser.add_argument("--setup", action="store_true", help="Interactive profile setup")
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

    # Handle setup
    if args.setup:
        run_setup(config)
        return

    # Handle health check
    if args.health_check:
        asyncio.run(run_health_check(config))
        return

    # Handle test checkout
    if args.test_checkout:
        url, retailer = args.test_checkout
        bot = PokemonScalpBot(config, dry_run=True)
        asyncio.run(bot.test_checkout(url, retailer))
        return

    # Main bot
    bot = PokemonScalpBot(config, dry_run=args.dry_run or None)

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
