"""Task manager - orchestrates checkout tasks across retailers.

Routes stock alerts to the correct retailer checkout module,
manages concurrent checkouts, and prevents duplicate purchases.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

from core.checkout import BaseCheckout, CheckoutResult, CheckoutStatus
from core.imap_monitor import ImapMonitor
from core.monitor import ProductAlert
from core.notifier import Notifier
from core.profile import ProfileManager, CheckoutProfile
from core.proxy_manager import ProxyManager
from utils.captcha import CaptchaSolver
from utils.logger import get_logger

log = get_logger("task_manager")


@dataclass
class TaskStats:
    """Aggregated checkout statistics."""
    total_attempts: int = 0
    successes: int = 0
    failures: int = 0
    declines: int = 0
    oos: int = 0
    total_spent: float = 0.0
    avg_checkout_ms: float = 0.0
    fastest_checkout_ms: int = 999999
    _checkout_times: list = field(default_factory=list)

    def record(self, result: CheckoutResult):
        self.total_attempts += 1
        if result.status == CheckoutStatus.SUCCESS:
            self.successes += 1
            self.total_spent += result.price
        elif result.status == CheckoutStatus.DECLINED:
            self.declines += 1
        elif result.status == CheckoutStatus.OOS:
            self.oos += 1
        else:
            self.failures += 1

        self._checkout_times.append(result.elapsed_ms)
        self.avg_checkout_ms = sum(self._checkout_times) / len(self._checkout_times)
        self.fastest_checkout_ms = min(self.fastest_checkout_ms, result.elapsed_ms)


class TaskManager:
    """Orchestrates checkout tasks across all retailers."""

    def __init__(
        self,
        config: dict,
        profile_manager: ProfileManager,
        proxy_manager: ProxyManager,
        notifier: Notifier,
        imap_monitor: ImapMonitor,
    ):
        self.config = config
        self.profiles = profile_manager
        self.proxies = proxy_manager
        self.notifier = notifier
        self.imap = imap_monitor
        self.dry_run = config.get("general", {}).get("dry_run", True)
        self.max_concurrent = config.get("general", {}).get("max_concurrent_tasks", 5)
        self.stats = TaskStats()

        # Deduplication: track recently processed URLs
        self._recent_checkouts: dict[str, float] = {}
        self._dedup_window = 300  # 5 minutes

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        # Rate limiting per retailer
        self._retailer_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._retailer_last_checkout: dict[str, float] = {}
        self._retailer_cooldown = 5.0  # seconds between checkouts per retailer

        # CAPTCHA solver
        captcha_config = config.get("captcha", {})
        self.captcha_solver = None
        if captcha_config.get("api_key"):
            self.captcha_solver = CaptchaSolver(
                provider=captcha_config.get("provider", "2captcha"),
                api_key=captcha_config["api_key"],
            )

        # Import retailer modules
        self._checkout_classes: dict[str, type] = {}
        self._load_retailers()

    def _load_retailers(self):
        """Dynamically load retailer checkout modules."""
        from retailers.pokemon_center import PokemonCenterCheckout
        from retailers.target import TargetCheckout
        from retailers.walmart import WalmartCheckout
        from retailers.amazon import AmazonCheckout
        from retailers.bestbuy import BestBuyCheckout
        from retailers.tcgplayer import TCGPlayerCheckout
        from retailers.ebay import EbayCheckout

        self._checkout_classes = {
            "pokemon_center": PokemonCenterCheckout,
            "target": TargetCheckout,
            "walmart": WalmartCheckout,
            "amazon": AmazonCheckout,
            "bestbuy": BestBuyCheckout,
            "tcgplayer": TCGPlayerCheckout,
            "ebay": EbayCheckout,
        }
        log.info(f"Loaded {len(self._checkout_classes)} retailer modules")

    async def handle_alert(self, alert: ProductAlert):
        """Handle a stock alert by spawning checkout task(s).

        Args:
            alert: ProductAlert from the monitor
        """
        # Dedup check
        if self._is_duplicate(alert.url):
            log.info(f"Skipping duplicate alert: {alert.url}")
            return

        self._recent_checkouts[alert.url] = time.time()

        # Get checkout class
        checkout_cls = self._checkout_classes.get(alert.retailer)
        if not checkout_cls:
            log.error(f"No checkout module for retailer: {alert.retailer}")
            return

        # Notify stock found
        await self.notifier.notify_stock_found(
            alert.product_name, alert.retailer, alert.price, alert.url
        )

        # Spawn checkout task for each profile
        tasks = []
        profiles = self.profiles.profiles
        for i, profile in enumerate(profiles):
            task = asyncio.create_task(
                self._checkout_task(checkout_cls, alert, profile)
            )
            tasks.append(task)

        # Wait for all checkout attempts
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                log.error(f"Checkout task error: {result}")
                continue
            if isinstance(result, CheckoutResult):
                self.stats.record(result)

    async def _checkout_task(
        self,
        checkout_cls: type,
        alert: ProductAlert,
        profile: CheckoutProfile,
    ) -> CheckoutResult:
        """Execute a single checkout attempt with concurrency control."""
        async with self._semaphore:
            # Rate limit per retailer
            async with self._retailer_locks[alert.retailer]:
                last = self._retailer_last_checkout.get(alert.retailer, 0)
                wait = self._retailer_cooldown - (time.time() - last)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._retailer_last_checkout[alert.retailer] = time.time()

            # Get proxy
            proxy_obj = await self.proxies.get_proxy(alert.retailer)
            proxy_str = proxy_obj.selenium_arg if proxy_obj else None

            # Create checkout instance
            checkout: BaseCheckout = checkout_cls(
                config=self.config,
                captcha_solver=self.captcha_solver,
                dry_run=self.dry_run,
            )

            # Execute checkout
            result = await checkout.execute(
                url=alert.url,
                profile=profile,
                proxy=proxy_str,
            )

            # Send notification
            if result.status == CheckoutStatus.SUCCESS:
                await self.notifier.notify_checkout_success(
                    product_name=result.product_name or alert.product_name,
                    retailer=alert.retailer,
                    price=result.price or alert.price,
                    order_id=result.order_id,
                    profile_name=profile.name,
                )
            else:
                await self.notifier.notify_checkout_failed(
                    product_name=alert.product_name,
                    retailer=alert.retailer,
                    reason=result.message,
                    profile_name=profile.name,
                )

            return result

    def _is_duplicate(self, url: str) -> bool:
        """Check if this URL was recently processed."""
        now = time.time()
        # Clean old entries
        self._recent_checkouts = {
            k: v for k, v in self._recent_checkouts.items()
            if now - v < self._dedup_window
        }
        return url in self._recent_checkouts

    def get_stats(self) -> dict:
        """Get formatted stats."""
        return {
            "total_attempts": self.stats.total_attempts,
            "successes": self.stats.successes,
            "failures": self.stats.failures,
            "declines": self.stats.declines,
            "oos": self.stats.oos,
            "success_rate": (
                f"{self.stats.successes / max(1, self.stats.total_attempts) * 100:.1f}%"
            ),
            "total_spent": f"${self.stats.total_spent:.2f}",
            "avg_checkout_ms": f"{self.stats.avg_checkout_ms:.0f}ms",
            "fastest_checkout_ms": f"{self.stats.fastest_checkout_ms}ms",
        }
