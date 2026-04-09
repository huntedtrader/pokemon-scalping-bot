"""Best Buy (bestbuy.com) checkout module.

API + Selenium hybrid. Handles queue/waiting room pages.
"""

import asyncio
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("bestbuy", "bestbuy")


class BestBuyCheckout(BaseCheckout):
    """Best Buy checkout implementation."""

    RETAILER_NAME = "bestbuy"
    CHECKOUT_TIMEOUT = 45  # Higher timeout for queue

    SELECTORS = {
        "add_to_cart": '.add-to-cart-button, button[data-button-state="ADD_TO_CART"]',
        "cart_icon": 'a[href="/cart"], .cart-link',
        "checkout_btn": '.checkout-buttons__checkout button, a[href*="/checkout"]',

        "email_input": '#fld-e, input[name="emailAddress"]',
        "password_input": '#fld-p1, input[name="password"]',
        "sign_in_btn": '.cia-form__controls button[type="submit"]',

        "first_name": '#consolidatedAddresses\\.ui_address_2\\.firstName, input[name="firstName"]',
        "last_name": '#consolidatedAddresses\\.ui_address_2\\.lastName, input[name="lastName"]',
        "address1": '#consolidatedAddresses\\.ui_address_2\\.street, input[name="addressLine1"]',
        "address2": '#consolidatedAddresses\\.ui_address_2\\.street2, input[name="addressLine2"]',
        "city": '#consolidatedAddresses\\.ui_address_2\\.city, input[name="city"]',
        "state": '#consolidatedAddresses\\.ui_address_2\\.state, select[name="state"]',
        "zip_code": '#consolidatedAddresses\\.ui_address_2\\.zipcode, input[name="zipCode"]',
        "phone": '#consolidatedAddresses\\.ui_address_2\\.middlePhoneNumber, input[name="phone"]',
        "continue_btn": '.button--continue, button[data-track="Checkout - Delivery - Continue"]',

        "card_number": '#optimized-cc-card-number, input[name="cardNumber"]',
        "exp_month": '#credit-card-expiration-month, select[name="expirationMonth"]',
        "exp_year": '#credit-card-expiration-year, select[name="expirationYear"]',
        "cvv": '#credit-card-cvv, input[name="cvv"]',
        "card_name": '#optimized-cc-card-name, input[name="cardholderName"]',

        "place_order": '.button--place-order, button[data-track="Checkout - Payment - Place Order"]',
    }

    async def add_to_cart(self) -> bool:
        try:
            await asyncio.sleep(1)

            # Handle queue page
            await self._handle_queue()

            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    log.info("Added to cart on Best Buy")
                    await asyncio.sleep(2)
                    return True
                except Exception:
                    continue

            # JS fallback
            result = self.driver.execute_script("""
                var btns = document.querySelectorAll('button');
                for (var btn of btns) {
                    if (btn.textContent.toLowerCase().includes('add to cart') &&
                        !btn.disabled) {
                        btn.click(); return true;
                    }
                }
                return false;
            """)
            await asyncio.sleep(2)
            return bool(result)
        except Exception:
            return False

    async def go_to_checkout(self):
        self.driver.get("https://www.bestbuy.com/checkout/r/fast-track")
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
            raise CheckoutError(f"Best Buy shipping failed: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            self._fill("card_number", profile.card_number)
            self._fill("card_name", profile.cardholder)
            self._try_select("exp_month", profile.exp_month)
            self._try_select("exp_year", profile.exp_year)
            self._fill("cvv", profile.cvv)
        except Exception as e:
            raise CheckoutError(f"Best Buy payment failed: {e}")

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
                raise CheckoutDeclined("Best Buy payment declined")

            match = re.search(r"BBY\d{2}-\d+|order.*?(\d{10,})", page_text, re.IGNORECASE)
            return match.group(0) if match else "BBY-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"Best Buy submit failed: {e}")

    async def _handle_queue(self):
        """Wait through Best Buy's queue/waiting room."""
        for _ in range(60):  # Wait up to 5 minutes
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "please wait" in page_text or "queue" in page_text or "waiting room" in page_text:
                log.info("In Best Buy queue, waiting...")
                await asyncio.sleep(5)
            else:
                return

    async def _sign_in_if_needed(self):
        account = self.config.get("retailer_accounts", {}).get("bestbuy", {})
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
            await asyncio.sleep(2)
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
                Select(self.wait_for(s, timeout=3)).select_by_value(value)
                return
            except Exception:
                continue
