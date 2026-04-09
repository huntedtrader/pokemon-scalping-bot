"""Target (target.com) checkout module.

Account-based checkout with API + Selenium hybrid approach.
Supports both shipping and store pickup options.
"""

import asyncio
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("target", "target")


class TargetCheckout(BaseCheckout):
    """Target.com checkout implementation."""

    RETAILER_NAME = "target"
    CHECKOUT_TIMEOUT = 30

    SELECTORS = {
        "add_to_cart": '[data-test="shipItButton"], [data-test="addToCartButton"], button[aria-label*="Add to cart"]',
        "cart_icon": 'a[href="/cart"], [data-test="@web/CartLink"]',
        "checkout_btn": '[data-test="checkout-button"], button[data-test="checkout"]',

        # Auth
        "email_input": '#username, input[name="username"], input[type="email"]',
        "password_input": '#password, input[name="password"], input[type="password"]',
        "sign_in_btn": '#login, button[type="submit"]',

        # Shipping
        "first_name": 'input[name="firstName"], #first-name',
        "last_name": 'input[name="lastName"], #last-name',
        "address1": 'input[name="addressLine1"], #address-line-1',
        "address2": 'input[name="addressLine2"], #address-line-2',
        "city": 'input[name="city"], #city',
        "state": 'select[name="state"], #state',
        "zip_code": 'input[name="zipCode"], #zip-code',
        "phone": 'input[name="phone"], #phone',
        "save_address": '[data-test="save-address-button"], button[type="submit"]',

        # Payment
        "card_number": 'input[name="cardNumber"], #credit-card-number',
        "exp_date": 'input[name="expiration"], #expiration',
        "cvv": 'input[name="cvv"], #cvv',
        "card_name": 'input[name="cardName"], #name-on-card',

        # Order
        "place_order": '[data-test="placeOrderButton"], button[data-test="place-order"]',
        "order_confirm": '[data-test="order-number"], .order-confirmation-number',
    }

    async def add_to_cart(self) -> bool:
        try:
            await asyncio.sleep(1)
            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    log.info("Added to cart on Target")
                    await asyncio.sleep(1.5)
                    return True
                except Exception:
                    continue

            # JS fallback
            result = self.driver.execute_script("""
                var btns = document.querySelectorAll('button');
                for (var btn of btns) {
                    var text = btn.textContent.toLowerCase();
                    if (text.includes('add to cart') || text.includes('ship it')) {
                        btn.click(); return true;
                    }
                }
                return false;
            """)
            await asyncio.sleep(1.5)
            return bool(result)
        except Exception as e:
            log.error(f"Target add to cart failed: {e}")
            return False

    async def go_to_checkout(self):
        try:
            self.driver.get("https://www.target.com/co-cart")
            await asyncio.sleep(2)

            for selector in self.SELECTORS["checkout_btn"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(2)

            # Sign in if required
            await self._sign_in_if_needed()
        except Exception as e:
            raise CheckoutError(f"Target checkout navigation failed: {e}")

    async def fill_shipping(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            self._fill_field("first_name", profile.first_name)
            self._fill_field("last_name", profile.last_name)
            self._fill_field("address1", profile.address1)
            if profile.address2:
                self._fill_field("address2", profile.address2)
            self._fill_field("city", profile.city)
            self._select_field("state", profile.state)
            self._fill_field("zip_code", profile.zip_code)
            self._fill_field("phone", profile.phone)

            for selector in self.SELECTORS["save_address"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(2)
            log.info("Target shipping info filled")
        except Exception as e:
            raise CheckoutError(f"Target shipping failed: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)

            # Check for payment iframe
            iframes = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[title*="payment"], iframe[name*="card"]')
            if iframes:
                self.driver.switch_to.frame(iframes[0])

            self._fill_field("card_number", profile.card_number)
            self._fill_field("exp_date", f"{profile.exp_month}/{profile.exp_year[-2:]}")
            self._fill_field("cvv", profile.cvv)
            self._fill_field("card_name", profile.cardholder)

            if iframes:
                self.driver.switch_to.default_content()

            log.info("Target payment info filled")
        except Exception as e:
            raise CheckoutError(f"Target payment failed: {e}")

    async def submit_order(self) -> str:
        try:
            for selector in self.SELECTORS["place_order"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(5)

            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            if any(w in page_text.lower() for w in ["declined", "payment failed"]):
                raise CheckoutDeclined("Target payment declined")

            match = re.search(r"(?:order)\s*#?\s*(\d{10,15})", page_text, re.IGNORECASE)
            return match.group(1) if match else "TARGET-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"Target submit failed: {e}")

    async def _sign_in_if_needed(self):
        """Sign in with Target account if prompted."""
        account = self.config.get("retailer_accounts", {}).get("target", {})
        if not account.get("email"):
            return

        try:
            self._fill_field("email_input", account["email"])
            self._fill_field("password_input", account["password"])
            for selector in self.SELECTORS["sign_in_btn"].split(", "):
                try:
                    self.safe_click(selector, timeout=3)
                    break
                except Exception:
                    continue
            await asyncio.sleep(2)
        except Exception:
            pass  # May not need sign in

    def _fill_field(self, key: str, value: str):
        if not value:
            return
        for selector in self.SELECTORS[key].split(", "):
            try:
                self.safe_type(selector, value, timeout=3)
                return
            except Exception:
                continue

    def _select_field(self, key: str, value: str):
        if not value:
            return
        for selector in self.SELECTORS[key].split(", "):
            try:
                elem = self.wait_for(selector, timeout=3)
                Select(elem).select_by_value(value)
                return
            except Exception:
                continue
