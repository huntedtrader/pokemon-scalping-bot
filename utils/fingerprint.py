"""Browser fingerprint randomization for Selenium sessions.

Uses undetected-chromedriver and randomized browser properties to
avoid bot detection on retailer sites.
"""

import random
from dataclasses import dataclass, field

import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
    (2560, 1440),
    (1680, 1050),
]

WEBGL_VENDORS = [
    "Google Inc. (NVIDIA)",
    "Google Inc. (AMD)",
    "Google Inc. (Intel)",
    "Google Inc.",
]

WEBGL_RENDERERS = [
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)",
]

LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,es;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.8",
]

PLATFORMS = ["Win32", "MacIntel", "Linux x86_64"]


@dataclass
class BrowserFingerprint:
    """Randomized browser fingerprint for a Selenium session."""
    user_agent: str = ""
    viewport: tuple = (1920, 1080)
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    language: str = ""
    platform: str = ""
    timezone_offset: int = 0
    hardware_concurrency: int = 8
    device_memory: int = 8
    max_touch_points: int = 0

    def __post_init__(self):
        if not self.user_agent:
            self.user_agent = random.choice(USER_AGENTS)
        if not self.webgl_vendor:
            self.webgl_vendor = random.choice(WEBGL_VENDORS)
        if not self.webgl_renderer:
            self.webgl_renderer = random.choice(WEBGL_RENDERERS)
        if not self.language:
            self.language = random.choice(LANGUAGES)
        if not self.platform:
            self.platform = random.choice(PLATFORMS)
        self.viewport = random.choice(VIEWPORTS)
        self.timezone_offset = random.choice([300, 360, 420, 480, 240, 180])  # US timezones
        self.hardware_concurrency = random.choice([4, 8, 12, 16])
        self.device_memory = random.choice([4, 8, 16, 32])


def create_stealth_driver(
    fingerprint: BrowserFingerprint = None,
    proxy: str = None,
    headless: bool = False,
) -> uc.Chrome:
    """Create an undetected Chrome driver with randomized fingerprint.

    Args:
        fingerprint: Browser fingerprint to apply. Random if None.
        proxy: Proxy string (ip:port or ip:port:user:pass)
        headless: Run browser in headless mode

    Returns:
        Configured undetected Chrome WebDriver instance
    """
    if fingerprint is None:
        fingerprint = BrowserFingerprint()

    options = uc.ChromeOptions()

    # Window size
    w, h = fingerprint.viewport
    options.add_argument(f"--window-size={w},{h}")

    # Language
    options.add_argument(f"--lang={fingerprint.language.split(',')[0]}")

    # Proxy
    if proxy:
        parts = proxy.replace("http://", "").replace("https://", "").split(":")
        if len(parts) == 2:
            options.add_argument(f"--proxy-server=http://{parts[0]}:{parts[1]}")
        elif len(parts) == 4:
            # Auth proxy needs extension or selenium-wire
            options.add_argument(f"--proxy-server=http://{parts[0]}:{parts[1]}")

    if headless:
        options.add_argument("--headless=new")

    # Anti-detection flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")

    driver = uc.Chrome(options=options, version_main=None)

    # Inject fingerprint overrides via CDP
    _inject_fingerprint(driver, fingerprint)

    return driver


def _inject_fingerprint(driver: uc.Chrome, fp: BrowserFingerprint):
    """Inject JavaScript fingerprint overrides into the page."""
    script = f"""
    // Override navigator properties
    Object.defineProperty(navigator, 'platform', {{get: () => '{fp.platform}'}});
    Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {fp.hardware_concurrency}}});
    Object.defineProperty(navigator, 'deviceMemory', {{get: () => {fp.device_memory}}});
    Object.defineProperty(navigator, 'maxTouchPoints', {{get: () => {fp.max_touch_points}}});
    Object.defineProperty(navigator, 'languages', {{get: () => {fp.language.split(',')}}});

    // Override WebGL
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) return '{fp.webgl_vendor}';
        if (parameter === 37446) return '{fp.webgl_renderer}';
        return getParameter.call(this, parameter);
    }};

    // Override timezone
    const origDateTZO = Date.prototype.getTimezoneOffset;
    Date.prototype.getTimezoneOffset = function() {{ return {fp.timezone_offset}; }};

    // Override Notification/Permission queries
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({{state: Notification.permission}}) :
        originalQuery(parameters)
    );
    """

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})


def create_driver_pool(count: int, proxy_list: list = None, headless: bool = False) -> list:
    """Pre-warm a pool of stealth browser instances.

    Args:
        count: Number of browsers to create
        proxy_list: Optional list of proxies to distribute
        headless: Run browsers headless

    Returns:
        List of (driver, fingerprint) tuples
    """
    pool = []
    for i in range(count):
        fp = BrowserFingerprint()
        proxy = proxy_list[i % len(proxy_list)] if proxy_list else None
        driver = create_stealth_driver(fp, proxy, headless)
        pool.append((driver, fp))
    return pool
