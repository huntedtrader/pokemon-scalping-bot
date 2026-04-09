"""Walmart (walmart.com) checkout module.

Account-based checkout with API-assisted cart management.
"""

import asyncio
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("walmart", "walmart")


class WalmartCheckout(BaseCheckout):
    """Walmart.com checkout implementation."""

    RETAILER_NAME = "walmart"
    CHECKOUT_TIMEOUT = 30

    SELECTORS = {
        "add_to_cart": '[data-tl-id="ProductPrimaryCTA-normal"], button[data-automation-id="add-to-cart"], button[aria-label*="Add to cart"]',
        "checkout_btn": '[data-automation-id="checkout"], a[href*="/checkout"]',

        "email_input": 'input[name="email"], #email',
        "password_input": 'input[name="password"], #password',
        "sign_in_btn": 'button[data-automation-id="signin-submit"], button[type="submit"]',

        "first_name": 'input[name="firstName"], #firstName',
        "last_name": 'input[name="lastName"], #lastName',
        "address1": 'input[name="addressLineOne"], #addressLineOne',
        "address2": 'input[name="addressLineTwo"], #addressLineTwo',
        "city": 'input[name="city"], #city',
        "state": 'select[name="state"], #state',
        "zip_code": 'input[name="postalCode"], #postalCode',
        "phone": 'input[name="phone"], #phone',
        "continue_btn": 'button[data-automation-id="address-book-action-buttons-on-continue"]',

        "card_number": 'input[name="cardNumber"], #cardNumber',
        "exp_month": 'select[name="month"], #month',
        "exp_year": 'select[name="year"], #year',
        "cvv": 'input[name="cvv"], #cvv',
        "card_name": 'input[name="firstName"], #first-name',

        "place_order": 'button[data-automation-id="submit-payment-btn"], button[aria-label*="Place order"]',
    }

    async def add_to_cart(self) -> bool:
        try:
            await asyncio.sleep(1)
            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    log.info("Added to cart on Walmart")
                    await asyncio.sleep(2)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    async def go_to_checkout(self):
        self.driver.get("https://www.walmart.com/checkout")
        await asyncio.sleep(3)
        await self._sign_in_if_needed()

    async def fill_shipping(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            self._fill("first_name", profile.first_name)
            self._fill("last_name", profile.last_name)
            self._fill("address1", profile.address1)
            if profile.address2:
                self._fill("address2", profile.address2)
            self._fill("city", profile.city)
            self._try_select("state", profile.state)
            self._fill("zip_code", profile.zip_code)
            self._fill("phone", profile.phone)

            for s in self.SELECTORS["continue_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=5)
                    break
                except Exception:
                    continue
            await asyncio.sleep(2)
        except Exception as e:
            raise CheckoutError(f"Walmart shipping failed: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            iframes = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[title*="payment"], iframe[name*="card"]')
            if iframes:
                self.driver.switch_to.frame(iframes[0])

            self._fill("card_number", profile.card_number)
            self._try_select("exp_month", profile.exp_month)
            self._try_select("exp_year", profile.exp_year)
            self._fill("cvv", profile.cvv)

            if iframes:
                self.driver.switch_to.default_content()
        except Exception as e:
            raise CheckoutError(f"Walmart payment failed: {e}")

    async def submit_order(self) -> str:
        try:
            for s in self.SELECTORS["place_order"].split(", "):
                try:
                    self.safe_click(s, timeout=5)
                    break
                except Exception:
                    continue
            await asyncio.sleep(5)

            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "declined" in page_text.lower():
                raise CheckoutDeclined("Walmart payment declined")

            match = re.search(r"(?:order)\s*#?\s*(\d{10,})", page_text, re.IGNORECASE)
            return match.group(1) if match else "WMT-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"Walmart submit failed: {e}")

    async def _sign_in_if_needed(self):
        account = self.config.get("retailer_accounts", {}).get("walmart", {})
        if not account.get("email"):
            return
        try:
            self._fill("email_input", account["email"])
            self._fill("password_input", account["password"])
            for s in self.SELECTORS["sign_in_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=3)
                    break
                except Exception:
                    continue
            await asyncio.sleep(3)
        except Exception:
            pass

    def _fill(self, key: str, value: str):
        if not value:
            return
        for s in self.SELECTORS[key].split(", "):
            try:
                self.safe_type(s, value, timeout=3)
                return
            except Exception:
                continue

    def _try_select(self, key: str, value: str):
        if not value:
            return
        for s in self.SELECTORS[key].split(", "):
            try:
                elem = self.wait_for(s, timeout=3)
                Select(elem).select_by_value(value)
                return
            except Exception:
                continue
