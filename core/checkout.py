"""Base checkout class and shared checkout logic.

All retailer modules inherit from BaseCheckout and implement
the retailer-specific checkout flow.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.profile import CheckoutProfile
from utils.captcha import CaptchaSolver
from utils.fingerprint import create_stealth_driver, BrowserFingerprint
from utils.logger import get_logger

log = get_logger("checkout")


class CheckoutStatus(Enum):
    PENDING = "pending"
    CARTING = "carting"
    FILLING_SHIPPING = "filling_shipping"
    FILLING_PAYMENT = "filling_payment"
    SUBMITTING = "submitting"
    SUCCESS = "success"
    FAILED = "failed"
    OOS = "out_of_stock"  # Went OOS during checkout
    DECLINED = "declined"  # Payment declined
    CAPTCHA = "captcha"  # Stuck on captcha


@dataclass
class CheckoutResult:
    """Result of a checkout attempt."""
    status: CheckoutStatus
    order_id: str = ""
    message: str = ""
    retailer: str = ""
    product_name: str = ""
    price: float = 0.0
    profile_name: str = ""
    elapsed_ms: int = 0


class BaseCheckout(ABC):
    """Abstract base class for retailer checkout modules."""

    RETAILER_NAME = "base"
    CHECKOUT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        config: dict,
        captcha_solver: CaptchaSolver = None,
        dry_run: bool = True,
    ):
        self.config = config
        self.captcha_solver = captcha_solver
        self.dry_run = dry_run
        self.driver = None
        self._log = get_logger(f"checkout.{self.RETAILER_NAME}", self.RETAILER_NAME)

    async def execute(
        self,
        url: str,
        profile: CheckoutProfile,
        proxy: str = None,
    ) -> CheckoutResult:
        """Execute the full checkout flow.

        Args:
            url: Product page URL
            profile: Checkout profile with shipping/payment info
            proxy: Optional proxy string

        Returns:
            CheckoutResult with status and details
        """
        start = time.time()

        try:
            # Initialize browser
            self._log.info(f"Starting checkout: {url}")
            self.driver = create_stealth_driver(
                BrowserFingerprint(), proxy=proxy, headless=False
            )
            self.driver.set_page_load_timeout(self.CHECKOUT_TIMEOUT)

            # Navigate to product
            self.driver.get(url)

            # Step 1: Add to cart
            self._log.info("Adding to cart...")
            success = await self.add_to_cart()
            if not success:
                return CheckoutResult(
                    status=CheckoutStatus.OOS,
                    message="Failed to add to cart (likely OOS)",
                    retailer=self.RETAILER_NAME,
                    profile_name=profile.name,
                    elapsed_ms=int((time.time() - start) * 1000),
                )

            # Step 2: Navigate to checkout
            self._log.info("Navigating to checkout...")
            await self.go_to_checkout()

            # Step 3: Fill shipping
            self._log.info("Filling shipping info...")
            await self.fill_shipping(profile)

            # Step 4: Fill payment
            self._log.info("Filling payment info...")
            await self.fill_payment(profile)

            # Step 5: Handle captcha if present
            if await self.has_captcha():
                self._log.info("Solving captcha...")
                await self.solve_captcha()

            # Step 6: Submit order
            if self.dry_run:
                self._log.info("DRY RUN - skipping order submission")
                return CheckoutResult(
                    status=CheckoutStatus.SUCCESS,
                    message="Dry run - order not submitted",
                    retailer=self.RETAILER_NAME,
                    product_name=await self.get_product_name(),
                    price=await self.get_total_price(),
                    profile_name=profile.name,
                    elapsed_ms=int((time.time() - start) * 1000),
                )

            self._log.info("Submitting order...")
            order_id = await self.submit_order()

            elapsed = int((time.time() - start) * 1000)
            self._log.info(
                f"CHECKOUT SUCCESS in {elapsed}ms - Order: {order_id}"
            )

            return CheckoutResult(
                status=CheckoutStatus.SUCCESS,
                order_id=order_id,
                retailer=self.RETAILER_NAME,
                product_name=await self.get_product_name(),
                price=await self.get_total_price(),
                profile_name=profile.name,
                elapsed_ms=elapsed,
            )

        except CheckoutDeclined as e:
            return CheckoutResult(
                status=CheckoutStatus.DECLINED,
                message=str(e),
                retailer=self.RETAILER_NAME,
                profile_name=profile.name,
                elapsed_ms=int((time.time() - start) * 1000),
            )

        except Exception as e:
            self._log.error(f"Checkout failed: {e}")
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                message=str(e),
                retailer=self.RETAILER_NAME,
                profile_name=profile.name,
                elapsed_ms=int((time.time() - start) * 1000),
            )

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

    # --- Abstract methods that each retailer must implement ---

    @abstractmethod
    async def add_to_cart(self) -> bool:
        """Add the product to cart. Return True if successful."""
        ...

    @abstractmethod
    async def go_to_checkout(self):
        """Navigate from cart to checkout page."""
        ...

    @abstractmethod
    async def fill_shipping(self, profile: CheckoutProfile):
        """Fill in shipping address fields."""
        ...

    @abstractmethod
    async def fill_payment(self, profile: CheckoutProfile):
        """Fill in payment card fields."""
        ...

    @abstractmethod
    async def submit_order(self) -> str:
        """Submit the order. Return order ID or confirmation number."""
        ...

    # --- Optional overrides ---

    async def has_captcha(self) -> bool:
        """Check if there's a captcha on the page."""
        try:
            # Check for reCAPTCHA iframe
            iframes = self.driver.find_elements(
                By.CSS_SELECTOR, 'iframe[src*="recaptcha"], iframe[src*="hcaptcha"]'
            )
            return len(iframes) > 0
        except Exception:
            return False

    async def solve_captcha(self):
        """Solve a captcha using the configured solver."""
        if not self.captcha_solver:
            raise CheckoutError("Captcha detected but no solver configured")

        # Detect captcha type
        page_source = self.driver.page_source

        if "recaptcha" in page_source.lower():
            site_key = self._extract_site_key(page_source, "recaptcha")
            token = await self.captcha_solver.solve_recaptcha_v2(
                site_key, self.driver.current_url
            )
            self.captcha_solver.inject_token(self.driver, token)

        elif "hcaptcha" in page_source.lower():
            site_key = self._extract_site_key(page_source, "hcaptcha")
            token = await self.captcha_solver.solve_hcaptcha(
                site_key, self.driver.current_url
            )
            self.captcha_solver.inject_token(self.driver, token)

    async def get_product_name(self) -> str:
        """Get the product name from the checkout page."""
        try:
            return self.driver.title
        except Exception:
            return "Unknown"

    async def get_total_price(self) -> float:
        """Get the order total from the checkout page."""
        return 0.0

    # --- Helper methods ---

    def wait_for(self, selector: str, by: str = By.CSS_SELECTOR, timeout: int = 10):
        """Wait for an element to be clickable."""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )

    def wait_for_visible(self, selector: str, by: str = By.CSS_SELECTOR, timeout: int = 10):
        """Wait for an element to be visible."""
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )

    def safe_click(self, selector: str, by: str = By.CSS_SELECTOR, timeout: int = 10):
        """Wait for element and click it."""
        elem = self.wait_for(selector, by, timeout)
        elem.click()
        return elem

    def safe_type(
        self, selector: str, text: str, by: str = By.CSS_SELECTOR,
        clear: bool = True, timeout: int = 10
    ):
        """Wait for input and type into it."""
        elem = self.wait_for(selector, by, timeout)
        if clear:
            elem.clear()
        elem.send_keys(text)
        return elem

    def _extract_site_key(self, html: str, captcha_type: str) -> str:
        """Extract captcha site key from page source."""
        import re
        if captcha_type == "recaptcha":
            match = re.search(r'data-sitekey="([^"]+)"', html)
            if not match:
                match = re.search(r"sitekey['\"]?\s*[:=]\s*['\"]([^'\"]+)", html)
        elif captcha_type == "hcaptcha":
            match = re.search(r'data-sitekey="([^"]+)"', html)

        return match.group(1) if match else ""


class CheckoutError(Exception):
    """General checkout error."""
    pass


class CheckoutDeclined(Exception):
    """Payment was declined."""
    pass
