"""Discord webhook and SMS notification system."""

import asyncio
from datetime import datetime

import aiohttp

from utils.logger import get_logger

log = get_logger("notifier")


class Notifier:
    """Sends alerts via Discord webhooks and optional SMS."""

    def __init__(self, config: dict):
        self.discord_url = config.get("discord", {}).get("webhook_url", "")
        self.sms_enabled = config.get("notifications", {}).get("sms", False)
        self.twilio_config = {
            "sid": config.get("notifications", {}).get("twilio_sid", ""),
            "token": config.get("notifications", {}).get("twilio_token", ""),
            "from": config.get("notifications", {}).get("twilio_from", ""),
            "to": config.get("notifications", {}).get("twilio_to", ""),
        }

    async def notify_stock_found(
        self, product_name: str, retailer: str, price: float, url: str
    ):
        """Alert that a product is in stock."""
        embed = {
            "title": "IN STOCK",
            "description": f"**{product_name}**",
            "color": 0x00FF00,  # Green
            "fields": [
                {"name": "Retailer", "value": retailer.upper(), "inline": True},
                {"name": "Price", "value": f"${price:.2f}", "inline": True},
                {"name": "URL", "value": f"[Link]({url})", "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Scalping Bot"},
        }
        await self._send_discord(embed=embed)

        if self.sms_enabled:
            await self._send_sms(
                f"IN STOCK: {product_name} @ ${price:.2f} on {retailer} - {url}"
            )

    async def notify_checkout_success(
        self, product_name: str, retailer: str, price: float, order_id: str, profile_name: str
    ):
        """Alert successful checkout."""
        embed = {
            "title": "CHECKOUT SUCCESS",
            "description": f"**{product_name}**",
            "color": 0x00BFFF,  # Blue
            "fields": [
                {"name": "Retailer", "value": retailer.upper(), "inline": True},
                {"name": "Price", "value": f"${price:.2f}", "inline": True},
                {"name": "Order ID", "value": order_id or "N/A", "inline": True},
                {"name": "Profile", "value": profile_name, "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Scalping Bot"},
        }
        await self._send_discord(embed=embed)

        if self.sms_enabled:
            await self._send_sms(
                f"CHECKOUT: {product_name} @ ${price:.2f} - Order: {order_id}"
            )

    async def notify_checkout_failed(
        self, product_name: str, retailer: str, reason: str, profile_name: str
    ):
        """Alert failed checkout attempt."""
        embed = {
            "title": "CHECKOUT FAILED",
            "description": f"**{product_name}**",
            "color": 0xFF0000,  # Red
            "fields": [
                {"name": "Retailer", "value": retailer.upper(), "inline": True},
                {"name": "Reason", "value": reason, "inline": True},
                {"name": "Profile", "value": profile_name, "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Scalping Bot"},
        }
        await self._send_discord(embed=embed)

    async def notify_price_drop(
        self, product_name: str, retailer: str, old_price: float, new_price: float, url: str
    ):
        """Alert a price drop below threshold."""
        savings = old_price - new_price
        embed = {
            "title": "PRICE DROP",
            "description": f"**{product_name}**",
            "color": 0xFFD700,  # Gold
            "fields": [
                {"name": "Retailer", "value": retailer.upper(), "inline": True},
                {"name": "Old Price", "value": f"~~${old_price:.2f}~~", "inline": True},
                {"name": "New Price", "value": f"**${new_price:.2f}**", "inline": True},
                {"name": "Savings", "value": f"-${savings:.2f}", "inline": True},
                {"name": "URL", "value": f"[Link]({url})", "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Scalping Bot"},
        }
        await self._send_discord(embed=embed)

    async def notify_error(self, message: str):
        """Send an error notification."""
        embed = {
            "title": "BOT ERROR",
            "description": message,
            "color": 0x8B0000,  # Dark red
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Scalping Bot"},
        }
        await self._send_discord(embed=embed)

    async def notify_status(self, message: str):
        """Send a status update."""
        await self._send_discord(content=f"[STATUS] {message}")

    async def _send_discord(self, content: str = None, embed: dict = None):
        """Send a message to the Discord webhook."""
        if not self.discord_url:
            return

        payload = {}
        if content:
            payload["content"] = content
        if embed:
            payload["embeds"] = [embed]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.discord_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 429:
                        retry_after = (await resp.json()).get("retry_after", 1)
                        log.warning(f"Discord rate limited, retry in {retry_after}s")
                        await asyncio.sleep(retry_after)
                        await self._send_discord(content, embed)
                    elif resp.status not in (200, 204):
                        log.error(f"Discord webhook failed: {resp.status}")
        except Exception as e:
            log.error(f"Discord notification error: {e}")

    async def _send_sms(self, message: str):
        """Send an SMS via Twilio."""
        if not all(self.twilio_config.values()):
            return

        try:
            url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{self.twilio_config['sid']}/Messages.json"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    auth=aiohttp.BasicAuth(
                        self.twilio_config["sid"], self.twilio_config["token"]
                    ),
                    data={
                        "To": self.twilio_config["to"],
                        "From": self.twilio_config["from"],
                        "Body": message,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status not in (200, 201):
                        log.error(f"Twilio SMS failed: {resp.status}")
                    else:
                        log.info("SMS sent successfully")
        except Exception as e:
            log.error(f"SMS error: {e}")
