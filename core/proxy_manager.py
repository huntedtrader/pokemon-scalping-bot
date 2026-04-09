"""Rotating proxy pool with health checks and ban detection."""

import asyncio
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

from utils.logger import get_logger

log = get_logger("proxy")


@dataclass
class Proxy:
    """A single proxy with health tracking."""
    host: str
    port: int
    username: str = ""
    password: str = ""
    failures: int = 0
    last_used: float = 0.0
    banned: bool = False
    latency_ms: float = 0.0

    @property
    def url(self) -> str:
        if self.username:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    @property
    def aiohttp_proxy(self) -> str:
        return self.url

    @property
    def selenium_arg(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def requests_dict(self) -> dict:
        return {"http": self.url, "https": self.url}


class ProxyManager:
    """Manages a pool of rotating proxies with health monitoring."""

    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.rotation = config.get("rotation", "round_robin")
        self.ban_threshold = config.get("ban_threshold", 3)
        self.proxies: list[Proxy] = []
        self._index = 0
        self._lock = asyncio.Lock()
        self._sticky_map: dict[str, Proxy] = {}  # retailer -> proxy

        if self.enabled:
            self._load_proxies(config.get("file", "config/proxies.txt"))

    def _load_proxies(self, filepath: str):
        """Load proxies from file."""
        path = Path(filepath)
        if not path.exists():
            log.warning(f"Proxy file not found: {filepath}")
            return

        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            proxy = self._parse_proxy(line)
            if proxy:
                self.proxies.append(proxy)

        log.info(f"Loaded {len(self.proxies)} proxies")

    def _parse_proxy(self, line: str) -> Proxy:
        """Parse a proxy string into a Proxy object."""
        line = line.replace("http://", "").replace("https://", "")

        # Format: user:pass@host:port
        if "@" in line:
            auth, hostport = line.split("@", 1)
            user, passwd = auth.split(":", 1)
            host, port = hostport.split(":", 1)
            return Proxy(host=host, port=int(port), username=user, password=passwd)

        parts = line.split(":")
        if len(parts) == 2:
            return Proxy(host=parts[0], port=int(parts[1]))
        elif len(parts) == 4:
            return Proxy(
                host=parts[0], port=int(parts[1]),
                username=parts[2], password=parts[3],
            )

        log.warning(f"Could not parse proxy: {line}")
        return None

    async def get_proxy(self, retailer: str = None) -> Proxy:
        """Get the next proxy based on rotation strategy.

        Args:
            retailer: Optional retailer name for sticky rotation

        Returns:
            A Proxy object, or None if no proxies available
        """
        if not self.enabled or not self.proxies:
            return None

        async with self._lock:
            active = [p for p in self.proxies if not p.banned]
            if not active:
                log.error("All proxies banned! Resetting...")
                for p in self.proxies:
                    p.banned = False
                    p.failures = 0
                active = self.proxies

            if self.rotation == "sticky" and retailer:
                if retailer in self._sticky_map:
                    proxy = self._sticky_map[retailer]
                    if not proxy.banned:
                        proxy.last_used = time.time()
                        return proxy
                proxy = random.choice(active)
                self._sticky_map[retailer] = proxy
                proxy.last_used = time.time()
                return proxy

            if self.rotation == "random":
                proxy = random.choice(active)
            else:
                # Round robin
                self._index = self._index % len(active)
                proxy = active[self._index]
                self._index += 1

            proxy.last_used = time.time()
            return proxy

    async def report_failure(self, proxy: Proxy):
        """Report a proxy failure (timeout, ban, block)."""
        async with self._lock:
            proxy.failures += 1
            if proxy.failures >= self.ban_threshold:
                proxy.banned = True
                log.warning(
                    f"Proxy banned after {proxy.failures} failures: {proxy.host}:{proxy.port}"
                )
            else:
                log.info(
                    f"Proxy failure ({proxy.failures}/{self.ban_threshold}): "
                    f"{proxy.host}:{proxy.port}"
                )

    async def report_success(self, proxy: Proxy):
        """Report successful proxy use (reset failure counter)."""
        async with self._lock:
            proxy.failures = max(0, proxy.failures - 1)

    async def health_check(self):
        """Check all proxies for connectivity."""
        log.info(f"Running health check on {len(self.proxies)} proxies...")
        tasks = [self._check_proxy(p) for p in self.proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        alive = sum(1 for r in results if r is True)
        log.info(f"Health check complete: {alive}/{len(self.proxies)} proxies alive")

    async def _check_proxy(self, proxy: Proxy) -> bool:
        """Check if a single proxy is working."""
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy.aiohttp_proxy,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        proxy.latency_ms = (time.time() - start) * 1000
                        proxy.banned = False
                        return True
        except Exception:
            proxy.banned = True
            return False

    @property
    def stats(self) -> dict:
        """Get proxy pool statistics."""
        return {
            "total": len(self.proxies),
            "active": sum(1 for p in self.proxies if not p.banned),
            "banned": sum(1 for p in self.proxies if p.banned),
            "avg_latency_ms": (
                sum(p.latency_ms for p in self.proxies if p.latency_ms > 0)
                / max(1, sum(1 for p in self.proxies if p.latency_ms > 0))
            ),
        }
