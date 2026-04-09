"""Product monitoring engine - Discord listener + async web scraper.

Polls product pages for stock availability and price changes,
and listens to Discord restock channels for instant alerts.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import aiohttp

from core.proxy_manager import ProxyManager
from utils.logger import get_logger

log = get_logger("monitor")


@dataclass
class ProductAlert:
    """A detected stock event."""
    product_name: str
    retailer: str
    url: str
    price: float
    in_stock: bool
    timestamp: float = field(default_factory=time.time)
    source: str = "scraper"  # "scraper" or "discord"
    keywords_matched: list = field(default_factory=list)


@dataclass
class MonitoredProduct:
    """A product being tracked."""
    url: str
    retailer: str
    max_price: float
    keywords: list = field(default_factory=list)
    enabled: bool = True
    last_price: float = 0.0
    last_stock: bool = False
    last_check: float = 0.0
    min_seller_rating: float = 0.0
    min_seller_feedback: float = 0.0


# Retailer-specific stock detection patterns
STOCK_PATTERNS = {
    "pokemon_center": {
        "in_stock": [r'"availability":\s*"InStock"', r'Add to Cart', r'add-to-cart'],
        "out_of_stock": [r'"availability":\s*"OutOfStock"', r'Out of Stock', r'Sold Out'],
        "price": [r'"price":\s*"?([\d.]+)"?', r'class="product-price[^"]*"[^>]*>\$?([\d.]+)'],
    },
    "target": {
        "in_stock": [r'"availability_status":"IN_STOCK"', r'Add to cart', r'Ship it'],
        "out_of_stock": [r'"availability_status":"OUT_OF_STOCK"', r'Out of stock', r'Sold out'],
        "price": [r'"current_retail":\s*([\d.]+)', r'"price":\s*([\d.]+)'],
    },
    "walmart": {
        "in_stock": [r'"availabilityStatus":"IN_STOCK"', r'Add to cart'],
        "out_of_stock": [r'"availabilityStatus":"OUT_OF_STOCK"', r'Out of stock'],
        "price": [r'"priceInfo".*?"currentPrice".*?"price":\s*([\d.]+)', r'"price":\s*([\d.]+)'],
    },
    "amazon": {
        "in_stock": [r'id="add-to-cart-button"', r'In Stock'],
        "out_of_stock": [r'Currently unavailable', r'Out of Stock'],
        "price": [r'"priceAmount":\s*([\d.]+)', r'class="a-price-whole">([\d,]+)'],
    },
    "bestbuy": {
        "in_stock": [r'"addToCartUrl"', r'Add to Cart'],
        "out_of_stock": [r'Sold Out', r'"buttonState":"SOLD_OUT"'],
        "price": [r'"currentPrice":\s*([\d.]+)', r'"customerPrice":\s*([\d.]+)'],
    },
    "tcgplayer": {
        "in_stock": [r'Add to Cart', r'listing-item__listing-data'],
        "out_of_stock": [r'Out of Stock', r'No listings'],
        "price": [r'"price":\s*"?\$?([\d.]+)"?', r'class="listing-item__listing-data__info__price">\$?([\d.]+)'],
    },
    "ebay": {
        "in_stock": [r'Buy It Now', r'"BIN"'],
        "out_of_stock": [r'This listing has ended'],
        "price": [r'"price":\s*"?([\d.]+)"?', r'id="prcIsum".*?\$?([\d.]+)'],
    },
}

# Default headers for scraping
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}


class StockMonitor:
    """Async stock monitoring engine."""

    def __init__(
        self,
        config: dict,
        proxy_manager: ProxyManager,
        on_stock_alert: Callable[[ProductAlert], None] = None,
    ):
        self.interval = config.get("general", {}).get("monitor_interval", 3.0)
        self.proxy_manager = proxy_manager
        self.on_stock_alert = on_stock_alert
        self.products: list[MonitoredProduct] = []
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

        # Load products from config
        for p in config.get("products", []):
            if p.get("enabled", True):
                self.products.append(MonitoredProduct(
                    url=p.get("url", ""),
                    retailer=p.get("retailer", ""),
                    max_price=p.get("max_price", 999.99),
                    keywords=p.get("keywords", []),
                    min_seller_rating=p.get("min_seller_rating", 0),
                    min_seller_feedback=p.get("min_seller_feedback", 0),
                ))

        log.info(f"Monitoring {len(self.products)} products")

    async def start(self):
        """Start the monitoring loop."""
        self._running = True
        self._session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
        log.info(f"Monitor started (interval: {self.interval}s)")

        while self._running:
            tasks = [self._check_product(p) for p in self.products if p.enabled and p.url]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.interval)

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._session:
            await self._session.close()
        log.info("Monitor stopped")

    async def _check_product(self, product: MonitoredProduct):
        """Check a single product for stock/price changes."""
        try:
            proxy = await self.proxy_manager.get_proxy(product.retailer)
            proxy_url = proxy.aiohttp_proxy if proxy else None

            async with self._session.get(
                product.url,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False,
            ) as resp:
                if resp.status != 200:
                    if proxy:
                        await self.proxy_manager.report_failure(proxy)
                    return

                html = await resp.text()
                if proxy:
                    await self.proxy_manager.report_success(proxy)

            # Parse stock status and price
            in_stock = self._check_stock(html, product.retailer)
            price = self._extract_price(html, product.retailer)
            product.last_check = time.time()

            # Detect transitions
            became_available = in_stock and not product.last_stock
            price_dropped = (
                price > 0
                and product.last_price > 0
                and price < product.last_price
                and price <= product.max_price
            )

            product.last_stock = in_stock
            if price > 0:
                product.last_price = price

            # Fire alerts
            if became_available and price <= product.max_price:
                alert = ProductAlert(
                    product_name=self._extract_title(html),
                    retailer=product.retailer,
                    url=product.url,
                    price=price,
                    in_stock=True,
                    source="scraper",
                )
                log.info(
                    f"STOCK ALERT: {alert.product_name} @ ${price:.2f} on {product.retailer}",
                    extra={"retailer": product.retailer},
                )
                if self.on_stock_alert:
                    await self.on_stock_alert(alert)

            elif price_dropped:
                alert = ProductAlert(
                    product_name=self._extract_title(html),
                    retailer=product.retailer,
                    url=product.url,
                    price=price,
                    in_stock=in_stock,
                    source="scraper",
                )
                log.info(
                    f"PRICE DROP: ${product.last_price:.2f} -> ${price:.2f} on {product.retailer}",
                    extra={"retailer": product.retailer},
                )
                if self.on_stock_alert:
                    await self.on_stock_alert(alert)

        except asyncio.TimeoutError:
            log.warning(f"Timeout checking {product.retailer}: {product.url}")
        except Exception as e:
            log.error(f"Error checking {product.retailer}: {e}")

    def _check_stock(self, html: str, retailer: str) -> bool:
        """Check if a product is in stock based on HTML patterns."""
        patterns = STOCK_PATTERNS.get(retailer, {})

        # Check out-of-stock patterns first
        for pattern in patterns.get("out_of_stock", []):
            if re.search(pattern, html, re.IGNORECASE):
                return False

        # Check in-stock patterns
        for pattern in patterns.get("in_stock", []):
            if re.search(pattern, html, re.IGNORECASE):
                return True

        return False

    def _extract_price(self, html: str, retailer: str) -> float:
        """Extract product price from HTML."""
        patterns = STOCK_PATTERNS.get(retailer, {}).get("price", [])

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(",", "")
                    return float(price_str)
                except (ValueError, IndexError):
                    continue

        return 0.0

    def _extract_title(self, html: str) -> str:
        """Extract product title from HTML."""
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            # Clean up common suffixes
            for sep in [" | ", " - ", " : "]:
                if sep in title:
                    title = title.split(sep)[0].strip()
            return title[:100]
        return "Unknown Product"


class DiscordMonitor:
    """Monitors Discord channels for restock alerts.

    Listens via a Discord bot token to specified channels
    and parses messages for product drop notifications.
    """

    def __init__(
        self,
        config: dict,
        on_stock_alert: Callable[[ProductAlert], None] = None,
    ):
        discord_config = config.get("discord", {})
        self.bot_token = discord_config.get("bot_token", "")
        self.channel_ids = discord_config.get("monitor_channels", [])
        self.on_stock_alert = on_stock_alert
        self._running = False

        # Keywords that indicate a restock alert
        self.alert_keywords = [
            "in stock", "restock", "live now", "go go go",
            "available now", "just dropped", "drop alert",
            "pokemon center", "pokemoncenter",
        ]

        # Retailer URL patterns
        self.url_patterns = {
            "pokemon_center": r"pokemoncenter\.com",
            "target": r"target\.com",
            "walmart": r"walmart\.com",
            "amazon": r"amazon\.com",
            "bestbuy": r"bestbuy\.com",
            "tcgplayer": r"tcgplayer\.com",
            "ebay": r"ebay\.com",
        }

    async def start(self):
        """Start listening to Discord channels via Gateway API."""
        if not self.bot_token or not self.channel_ids:
            log.warning("Discord monitoring not configured (no token or channels)")
            return

        self._running = True
        log.info(f"Discord monitor started for {len(self.channel_ids)} channels")

        gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"

        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(gateway_url) as ws:
                        # Receive Hello
                        hello = await ws.receive_json()
                        heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000

                        # Send Identify
                        await ws.send_json({
                            "op": 2,
                            "d": {
                                "token": self.bot_token,
                                "intents": 512 | 32768,  # GUILD_MESSAGES + MESSAGE_CONTENT
                                "properties": {
                                    "os": "windows",
                                    "browser": "pokescalp",
                                    "device": "pokescalp",
                                },
                            },
                        })

                        # Start heartbeat and message loop
                        heartbeat_task = asyncio.create_task(
                            self._heartbeat_loop(ws, heartbeat_interval)
                        )

                        try:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = msg.json()
                                    if data.get("t") == "MESSAGE_CREATE":
                                        await self._handle_message(data["d"])
                                elif msg.type in (
                                    aiohttp.WSMsgType.CLOSED,
                                    aiohttp.WSMsgType.ERROR,
                                ):
                                    break
                        finally:
                            heartbeat_task.cancel()

            except Exception as e:
                log.error(f"Discord connection error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the Discord monitor."""
        self._running = False

    async def _heartbeat_loop(self, ws, interval: float):
        """Send periodic heartbeats to keep the connection alive."""
        while True:
            await asyncio.sleep(interval)
            await ws.send_json({"op": 1, "d": None})

    async def _handle_message(self, message: dict):
        """Process a Discord message for restock alerts."""
        channel_id = message.get("channel_id", "")
        if channel_id not in [str(c) for c in self.channel_ids]:
            return

        content = message.get("content", "").lower()
        embeds = message.get("embeds", [])

        # Check embeds too
        for embed in embeds:
            content += " " + (embed.get("title", "") or "").lower()
            content += " " + (embed.get("description", "") or "").lower()
            for field_obj in embed.get("fields", []):
                content += " " + (field_obj.get("value", "") or "").lower()

        # Check for alert keywords
        is_alert = any(kw in content for kw in self.alert_keywords)
        if not is_alert:
            return

        # Extract URLs and determine retailer
        urls = re.findall(r'https?://[^\s<>"]+', content + " " + message.get("content", ""))

        for url in urls:
            retailer = None
            for name, pattern in self.url_patterns.items():
                if re.search(pattern, url):
                    retailer = name
                    break

            if retailer:
                alert = ProductAlert(
                    product_name=self._extract_product_name(content),
                    retailer=retailer,
                    url=url,
                    price=0.0,  # Will be fetched during checkout
                    in_stock=True,
                    source="discord",
                )
                log.info(
                    f"DISCORD ALERT: {alert.product_name} on {retailer}",
                    extra={"retailer": retailer},
                )
                if self.on_stock_alert:
                    await self.on_stock_alert(alert)

    def _extract_product_name(self, content: str) -> str:
        """Try to extract a product name from the alert message."""
        # Look for common Pokemon product names
        pokemon_products = [
            r"([\w\s]+ (?:ETB|Elite Trainer Box))",
            r"([\w\s]+ Booster (?:Box|Bundle|Pack))",
            r"([\w\s]+ (?:Collection|Premium|UPC))",
            r"([\w\s]+ (?:Tin|Blister|Tech Sticker))",
        ]
        for pattern in pokemon_products:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()

        return "Pokemon TCG Product"
