"""eBay (ebay.com) BIN (Buy It Now) sniper module.

Searches for underpriced Pokemon TCG listings and auto-purchases
Buy It Now listings that meet price and seller criteria.
"""

import asyncio
import re
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("ebay", "ebay")


class EbayCheckout(BaseCheckout):
    """eBay BIN sniper checkout implementation."""

    RETAILER_NAME = "ebay"
    CHECKOUT_TIMEOUT = 30

    SELECTORS = {
        "buy_it_now": '#binBtn_btn, a[data-testid="ux-call-to-action"], .ux-call-to-action--BIN',
        "commit_buy": '#commit-btn, button[data-testid="ux-cta-commit"], #binBtn_btn_1',

        "email_input": '#userid, input[name="userid"]',
        "password_input": '#pass, input[name="pass"]',
        "sign_in_btn": '#sgnBt, button[name="sgnBt"]',

        # eBay checkout uses saved info
        "change_address": '#changeAddressBtn, a[data-testid="address-change"]',
        "first_name": '#firstName, input[name="firstName"]',
        "last_name": '#lastName, input[name="lastName"]',
        "address1": '#addressLine1, input[name="addressLine1"]',
        "address2": '#addressLine2, input[name="addressLine2"]',
        "city": '#city, input[name="city"]',
        "state": '#stateOrProvince, select[name="stateOrProvince"]',
        "zip_code": '#postalCode, input[name="postalCode"]',
        "phone": '#phoneNumber, input[name="phoneNumber"]',

        "confirm_pay": '#confirmAddress, button[data-testid="confirm-and-pay"]',
        "order_confirm": '.confirm-text, [data-testid="order-confirmation"]',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._search_url = ""

    async def add_to_cart(self) -> bool:
        """Click Buy It Now on an eBay listing."""
        try:
            await asyncio.sleep(1)

            # If URL is empty, this is a keyword search - find a listing first
            if not self.driver.current_url or "ebay.com/itm" not in self.driver.current_url:
                found = await self._find_best_listing()
                if not found:
                    return False

            for selector in self.SELECTORS["buy_it_now"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    log.info("Clicked Buy It Now on eBay")
                    await asyncio.sleep(2)
                    return True
                except Exception:
                    continue

            # JS fallback
            result = self.driver.execute_script("""
                var btns = document.querySelectorAll('a, button, input');
                for (var btn of btns) {
                    var text = (btn.textContent || btn.value || '').toLowerCase();
                    if (text.includes('buy it now')) {
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
        """eBay BIN goes directly to checkout after clicking Buy It Now."""
        await asyncio.sleep(2)
        await self._sign_in_if_needed()

        # Click commit/confirm purchase
        for selector in self.SELECTORS["commit_buy"].split(", "):
            try:
                self.safe_click(selector, timeout=5)
                break
            except Exception:
                continue
        await asyncio.sleep(2)

    async def fill_shipping(self, profile: CheckoutProfile):
        """eBay uses saved addresses - only fill if needed."""
        try:
            # Check if we need to add a new address
            try:
                self.safe_click(self.SELECTORS["change_address"].split(", ")[0], timeout=3)
                await asyncio.sleep(1)

                self._fill("first_name", profile.first_name)
                self._fill("last_name", profile.last_name)
                self._fill("address1", profile.address1)
                self._fill("city", profile.city)
                self._fill("zip_code", profile.zip_code)
                self._fill("phone", profile.phone)
            except Exception:
                pass  # Saved address already selected
        except Exception as e:
            log.warning(f"eBay shipping: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        """eBay uses saved payment - PayPal or card on file."""
        # eBay typically uses PayPal or saved payment methods
        # No additional input needed if payment is on file
        await asyncio.sleep(1)
        log.info("Using saved eBay payment method")

    async def submit_order(self) -> str:
        try:
            for s in self.SELECTORS["confirm_pay"].split(", "):
                try:
                    self.safe_click(s, timeout=5)
                    break
                except Exception:
                    continue

            # Also try generic confirm button
            self.driver.execute_script("""
                var btns = document.querySelectorAll('button, input');
                for (var btn of btns) {
                    var text = (btn.textContent || btn.value || '').toLowerCase();
                    if (text.includes('confirm') || text.includes('pay') || text.includes('commit')) {
                        btn.click(); return;
                    }
                }
            """)

            await asyncio.sleep(5)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            if "declined" in page_text.lower() or "problem" in page_text.lower():
                raise CheckoutDeclined("eBay payment issue")

            # eBay order ID format
            match = re.search(r"(\d{2}-\d{5}-\d{5})", page_text)
            if not match:
                match = re.search(r"(?:order|transaction)\s*#?\s*(\d+)", page_text, re.IGNORECASE)
            return match.group(1) if match else "EBAY-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"eBay submit failed: {e}")

    async def _find_best_listing(self) -> bool:
        """Search eBay for the best BIN listing matching keywords."""
        products = self.config.get("products", [])
        ebay_product = None
        for p in products:
            if p.get("retailer") == "ebay":
                ebay_product = p
                break

        if not ebay_product or not ebay_product.get("keywords"):
            return False

        keywords = " ".join(ebay_product["keywords"])
        max_price = ebay_product.get("max_price", 999)
        min_feedback = ebay_product.get("min_seller_feedback", 95)

        # Build eBay search URL with BIN filter
        search_url = (
            f"https://www.ebay.com/sch/i.html?"
            f"_nkw={quote_plus(keywords)}"
            f"&LH_BIN=1"  # Buy It Now only
            f"&_udhi={max_price}"  # Max price
            f"&LH_ItemCondition=1000"  # New only
            f"&_sop=15"  # Sort by price + shipping lowest first
            f"&rt=nc"
        )

        self.driver.get(search_url)
        await asyncio.sleep(2)

        # Find first listing that meets criteria
        try:
            listings = self.driver.find_elements(By.CSS_SELECTOR, '.s-item, .srp-results .s-item__wrapper')

            for listing in listings[:10]:
                try:
                    # Get price
                    price_elem = listing.find_element(By.CSS_SELECTOR, '.s-item__price')
                    price_text = price_elem.text.replace("$", "").replace(",", "").split(" ")[0]
                    price = float(price_text)

                    if price > max_price:
                        continue

                    # Click into listing
                    link = listing.find_element(By.CSS_SELECTOR, 'a.s-item__link')
                    link.click()
                    await asyncio.sleep(2)

                    # Verify seller feedback
                    try:
                        feedback_elem = self.driver.find_element(
                            By.CSS_SELECTOR, '.ux-seller-section__item--seller a, #feedback-score'
                        )
                        feedback_text = feedback_elem.text.replace("%", "").strip()
                        if float(feedback_text) < min_feedback:
                            self.driver.back()
                            await asyncio.sleep(1)
                            continue
                    except Exception:
                        pass  # Assume OK if can't find

                    log.info(f"Found eBay listing @ ${price:.2f}")
                    return True

                except Exception:
                    continue

        except Exception as e:
            log.error(f"eBay search failed: {e}")

        return False

    async def _sign_in_if_needed(self):
        account = self.config.get("retailer_accounts", {}).get("ebay", {})
        if not account.get("email"):
            return
        try:
            self._fill("email_input", account["email"])
            for s in self.SELECTORS["sign_in_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=3)
                    break
                except Exception:
                    continue
            await asyncio.sleep(1)

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
