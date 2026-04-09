"""Pokemon Center (pokemoncenter.com) checkout module.

Supports guest checkout with address jigging for multi-order bypass.
Uses Selenium for the full checkout flow since PKC has anti-bot measures.
"""

import asyncio
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("pokemon_center", "pokemon_center")


class PokemonCenterCheckout(BaseCheckout):
    """Pokemon Center guest checkout implementation."""

    RETAILER_NAME = "pokemon_center"
    CHECKOUT_TIMEOUT = 30

    # CSS selectors for PKC elements
    SELECTORS = {
        # Product page
        "add_to_cart": 'button[data-test="add-to-cart-button"], button.add-to-cart, button[aria-label*="Add to Cart"]',
        "size_select": 'select[data-test="size-selector"], select.product-size-select',

        # Cart
        "cart_icon": 'a[href*="/cart"], button[data-test="cart-icon"], .cart-icon',
        "checkout_btn": 'a[data-test="checkout-button"], button.checkout-button, a[href*="/checkout"]',

        # Shipping - Guest checkout
        "guest_checkout": 'button[data-test="guest-checkout"], a[href*="guest"], button:contains("Guest")',
        "email_input": 'input[name="email"], input[data-test="email-input"], input[type="email"]',
        "first_name": 'input[name="firstName"], input[data-test="first-name"], input[autocomplete="given-name"]',
        "last_name": 'input[name="lastName"], input[data-test="last-name"], input[autocomplete="family-name"]',
        "address1": 'input[name="address1"], input[data-test="address-line1"], input[autocomplete="address-line1"]',
        "address2": 'input[name="address2"], input[data-test="address-line2"], input[autocomplete="address-line2"]',
        "city": 'input[name="city"], input[data-test="city"], input[autocomplete="address-level2"]',
        "state": 'select[name="state"], select[data-test="state"], select[autocomplete="address-level1"]',
        "zip_code": 'input[name="zipCode"], input[data-test="zip-code"], input[autocomplete="postal-code"]',
        "phone": 'input[name="phone"], input[data-test="phone"], input[type="tel"]',
        "continue_shipping": 'button[data-test="continue-to-payment"], button.continue-button, button[type="submit"]',

        # Payment
        "card_number": 'input[name="cardNumber"], input[data-test="card-number"], input[autocomplete="cc-number"]',
        "card_name": 'input[name="nameOnCard"], input[data-test="cardholder-name"], input[autocomplete="cc-name"]',
        "exp_month": 'select[name="expirationMonth"], select[data-test="exp-month"], input[autocomplete="cc-exp-month"]',
        "exp_year": 'select[name="expirationYear"], select[data-test="exp-year"], input[autocomplete="cc-exp-year"]',
        "cvv": 'input[name="cvv"], input[data-test="cvv"], input[autocomplete="cc-csc"]',
        "payment_iframe": 'iframe[title*="payment"], iframe[name*="card"], iframe[src*="payment"]',

        # Order
        "place_order": 'button[data-test="place-order"], button.place-order, button[type="submit"]:contains("Place Order")',
        "order_confirm": '.order-confirmation, [data-test="order-number"], .confirmation-number',

        # Popups and overlays
        "cookie_accept": 'button[id*="cookie"], button[class*="cookie-accept"], button:contains("Accept")',
        "popup_close": 'button[class*="close"], button[aria-label="Close"], .modal-close',
    }

    async def add_to_cart(self) -> bool:
        """Add Pokemon Center product to cart."""
        try:
            # Dismiss any popups/cookie banners
            await self._dismiss_popups()

            # Wait for add to cart button
            await asyncio.sleep(1)  # Let page settle

            # Try multiple selector strategies
            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    btn.click()
                    log.info("Clicked Add to Cart")
                    await asyncio.sleep(1.5)
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue

            # Fallback: try JavaScript click
            try:
                self.driver.execute_script("""
                    var btns = document.querySelectorAll('button');
                    for (var btn of btns) {
                        if (btn.textContent.toLowerCase().includes('add to cart') ||
                            btn.textContent.toLowerCase().includes('add to bag')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                """)
                await asyncio.sleep(1.5)
                return True
            except Exception:
                pass

            log.error("Could not find Add to Cart button")
            return False

        except Exception as e:
            log.error(f"Add to cart failed: {e}")
            return False

    async def go_to_checkout(self):
        """Navigate from cart to checkout."""
        try:
            # First try going directly to checkout URL
            self.driver.get("https://www.pokemoncenter.com/checkout")
            await asyncio.sleep(2)

            # Check if we need to click guest checkout
            await self._try_guest_checkout()

        except Exception:
            # Fallback: click cart icon, then checkout button
            try:
                for selector in self.SELECTORS["cart_icon"].split(", "):
                    try:
                        self.safe_click(selector, timeout=5)
                        break
                    except Exception:
                        continue

                await asyncio.sleep(1)

                for selector in self.SELECTORS["checkout_btn"].split(", "):
                    try:
                        self.safe_click(selector, timeout=5)
                        break
                    except Exception:
                        continue

                await asyncio.sleep(2)
                await self._try_guest_checkout()

            except Exception as e:
                raise CheckoutError(f"Could not navigate to checkout: {e}")

    async def fill_shipping(self, profile: CheckoutProfile):
        """Fill shipping information."""
        try:
            await asyncio.sleep(1)

            # Email
            self._safe_fill("email_input", profile.email)

            # Name
            self._safe_fill("first_name", profile.first_name)
            self._safe_fill("last_name", profile.last_name)

            # Address
            self._safe_fill("address1", profile.address1)
            if profile.address2:
                self._safe_fill("address2", profile.address2)

            # City
            self._safe_fill("city", profile.city)

            # State (dropdown)
            self._safe_select("state", profile.state)

            # Zip
            self._safe_fill("zip_code", profile.zip_code)

            # Phone
            self._safe_fill("phone", profile.phone)

            # Continue to payment
            await asyncio.sleep(0.5)
            for selector in self.SELECTORS["continue_shipping"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(2)
            log.info("Shipping info filled")

        except Exception as e:
            raise CheckoutError(f"Failed to fill shipping: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        """Fill payment card information."""
        try:
            await asyncio.sleep(1)

            # Check if payment is in an iframe
            iframes = self.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["payment_iframe"])
            if iframes:
                self.driver.switch_to.frame(iframes[0])

            # Card number
            self._safe_fill("card_number", profile.card_number)

            # Cardholder name
            self._safe_fill("card_name", profile.cardholder)

            # Expiration
            self._safe_select_or_fill("exp_month", profile.exp_month)
            self._safe_select_or_fill("exp_year", profile.exp_year)

            # CVV
            self._safe_fill("cvv", profile.cvv)

            # Switch back to main frame if we were in iframe
            if iframes:
                self.driver.switch_to.default_content()

            log.info("Payment info filled")

        except Exception as e:
            if iframes:
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass
            raise CheckoutError(f"Failed to fill payment: {e}")

    async def submit_order(self) -> str:
        """Submit the order and return order ID."""
        try:
            # Click place order
            for selector in self.SELECTORS["place_order"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            # Also try JS click on any "Place Order" button
            self.driver.execute_script("""
                var btns = document.querySelectorAll('button');
                for (var btn of btns) {
                    if (btn.textContent.toLowerCase().includes('place order') ||
                        btn.textContent.toLowerCase().includes('submit order')) {
                        btn.click();
                        return;
                    }
                }
            """)

            # Wait for confirmation page
            await asyncio.sleep(5)

            # Extract order ID
            order_id = self._extract_order_id()

            if not order_id:
                # Check for decline
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if any(w in page_text for w in ["declined", "unable to process", "payment failed"]):
                    raise CheckoutDeclined("Payment was declined")

                order_id = "UNKNOWN"

            return order_id

        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"Failed to submit order: {e}")

    async def get_product_name(self) -> str:
        """Extract product name from page."""
        try:
            title = self.driver.title
            return title.replace(" | Pokemon Center", "").strip()
        except Exception:
            return "Pokemon Center Product"

    async def get_total_price(self) -> float:
        """Extract order total from checkout page."""
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r"(?:total|order total)[:\s]*\$?([\d.]+)", page_text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0

    # --- Private helpers ---

    async def _dismiss_popups(self):
        """Dismiss cookie banners and popups."""
        for key in ["cookie_accept", "popup_close"]:
            for selector in self.SELECTORS[key].split(", "):
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    elem.click()
                    await asyncio.sleep(0.3)
                except Exception:
                    continue

    async def _try_guest_checkout(self):
        """Try to select guest checkout option."""
        for selector in self.SELECTORS["guest_checkout"].split(", "):
            try:
                elem = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                elem.click()
                await asyncio.sleep(1)
                return
            except Exception:
                continue

        # Try JS click
        try:
            self.driver.execute_script("""
                var btns = document.querySelectorAll('button, a');
                for (var btn of btns) {
                    if (btn.textContent.toLowerCase().includes('guest') ||
                        btn.textContent.toLowerCase().includes('continue as guest')) {
                        btn.click();
                        return;
                    }
                }
            """)
        except Exception:
            pass

    def _safe_fill(self, selector_key: str, value: str):
        """Try multiple selectors to fill an input field."""
        if not value:
            return
        for selector in self.SELECTORS[selector_key].split(", "):
            try:
                self.safe_type(selector, value, timeout=3)
                return
            except Exception:
                continue
        log.warning(f"Could not fill field: {selector_key}")

    def _safe_select(self, selector_key: str, value: str):
        """Try to select a dropdown value."""
        if not value:
            return
        for selector in self.SELECTORS[selector_key].split(", "):
            try:
                elem = self.wait_for(selector, timeout=3)
                select = Select(elem)
                try:
                    select.select_by_value(value)
                except Exception:
                    select.select_by_visible_text(value)
                return
            except Exception:
                continue

    def _safe_select_or_fill(self, selector_key: str, value: str):
        """Try select dropdown first, fall back to typing."""
        try:
            self._safe_select(selector_key, value)
        except Exception:
            self._safe_fill(selector_key, value)

    def _extract_order_id(self) -> str:
        """Extract order ID from confirmation page."""
        try:
            # Try specific element
            for selector in self.SELECTORS["order_confirm"].split(", "):
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    match = re.search(r"[A-Z0-9]{6,20}", text)
                    if match:
                        return match.group(0)
                except Exception:
                    continue

            # Try page text
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(
                r"(?:order|confirmation)\s*(?:#|number|num)?[:\s]*([A-Z0-9-]{6,20})",
                page_text,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

        except Exception:
            pass

        return ""
