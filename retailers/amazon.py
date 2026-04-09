"""Amazon (amazon.com) checkout module.

Account-based with 1-Click checkout support via Selenium.
Monitors Buy Box pricing for best deals.
"""

import asyncio
import re

from selenium.webdriver.common.by import By

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("amazon", "amazon")


class AmazonCheckout(BaseCheckout):
    """Amazon.com checkout implementation with 1-Click support."""

    RETAILER_NAME = "amazon"
    CHECKOUT_TIMEOUT = 30

    SELECTORS = {
        "add_to_cart": '#add-to-cart-button, input[name="submit.add-to-cart"]',
        "buy_now": '#buy-now-button, input[name="submit.buy-now"]',
        "one_click": '#one-click-button',
        "cart_btn": '#nav-cart, a[href="/gp/cart/view.html"]',
        "proceed_checkout": 'input[name="proceedToRetailCheckout"], [data-feature-id="proceed-to-checkout-action"]',

        "email_input": '#ap_email, input[name="email"]',
        "password_input": '#ap_password, input[name="password"]',
        "continue_btn": '#continue, input[id="continue"]',
        "sign_in_btn": '#signInSubmit',

        "address_select": '#address-book-entry-0, .ship-to-this-address',
        "payment_select": '.payment-method-default, #payment-method-0',
        "gift_card_skip": '#gc-promo-skip-link, [data-testid="skip"]',

        "place_order": '#submitOrderButtonId input, #placeYourOrder input, [name="placeYourOrder1"]',
        "order_confirm": '#thankyou-main, .a-box.order-info',
    }

    async def add_to_cart(self) -> bool:
        try:
            await asyncio.sleep(1)

            # Try Buy Now for fastest checkout
            for selector in self.SELECTORS["buy_now"].split(", "):
                try:
                    self.safe_click(selector, timeout=3)
                    log.info("Clicked Buy Now on Amazon")
                    await asyncio.sleep(2)
                    return True
                except Exception:
                    continue

            # Fall back to Add to Cart
            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    log.info("Added to cart on Amazon")
                    await asyncio.sleep(1.5)
                    return True
                except Exception:
                    continue

            return False
        except Exception:
            return False

    async def go_to_checkout(self):
        try:
            # If Buy Now was used, we may already be at checkout
            if "buy" in self.driver.current_url.lower() or "checkout" in self.driver.current_url.lower():
                await self._sign_in_if_needed()
                return

            # Otherwise navigate cart -> checkout
            self.driver.get("https://www.amazon.com/gp/cart/view.html")
            await asyncio.sleep(2)

            for selector in self.SELECTORS["proceed_checkout"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(2)
            await self._sign_in_if_needed()
        except Exception as e:
            raise CheckoutError(f"Amazon checkout navigation failed: {e}")

    async def fill_shipping(self, profile: CheckoutProfile):
        """Amazon uses saved addresses - select the default one."""
        try:
            await asyncio.sleep(1)
            # Try to select saved address
            for selector in self.SELECTORS["address_select"].split(", "):
                try:
                    self.safe_click(selector, timeout=3)
                    log.info("Selected saved shipping address")
                    await asyncio.sleep(1)
                    return
                except Exception:
                    continue

            # If no saved address, check if we need to click continue
            self.driver.execute_script("""
                var btns = document.querySelectorAll('input, button, a');
                for (var btn of btns) {
                    var text = (btn.value || btn.textContent || '').toLowerCase();
                    if (text.includes('use this address') || text.includes('deliver to this address')) {
                        btn.click(); return;
                    }
                }
            """)
            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"Amazon shipping selection: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        """Amazon uses saved payment methods."""
        try:
            await asyncio.sleep(1)
            # Select default payment
            for selector in self.SELECTORS["payment_select"].split(", "):
                try:
                    self.safe_click(selector, timeout=3)
                    break
                except Exception:
                    continue

            # Skip gift card promo if shown
            for selector in self.SELECTORS["gift_card_skip"].split(", "):
                try:
                    self.safe_click(selector, timeout=2)
                except Exception:
                    continue

            # Continue
            self.driver.execute_script("""
                var btns = document.querySelectorAll('input, button, a, span');
                for (var btn of btns) {
                    var text = (btn.value || btn.textContent || '').toLowerCase();
                    if (text.includes('continue') || text.includes('use this payment')) {
                        btn.click(); return;
                    }
                }
            """)
            await asyncio.sleep(1)
        except Exception as e:
            log.warning(f"Amazon payment selection: {e}")

    async def submit_order(self) -> str:
        try:
            for selector in self.SELECTORS["place_order"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    break
                except Exception:
                    continue

            self.driver.execute_script("""
                var btns = document.querySelectorAll('input, button');
                for (var btn of btns) {
                    var text = (btn.value || btn.textContent || '').toLowerCase();
                    if (text.includes('place your order') || text.includes('buy now')) {
                        btn.click(); return;
                    }
                }
            """)

            await asyncio.sleep(5)

            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "declined" in page_text.lower():
                raise CheckoutDeclined("Amazon payment declined")

            match = re.search(r"(\d{3}-\d{7}-\d{7})", page_text)
            return match.group(1) if match else "AMZ-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"Amazon submit failed: {e}")

    async def _sign_in_if_needed(self):
        account = self.config.get("retailer_accounts", {}).get("amazon", {})
        if not account.get("email"):
            return
        try:
            # Email step
            for s in self.SELECTORS["email_input"].split(", "):
                try:
                    self.safe_type(s, account["email"], timeout=3)
                    break
                except Exception:
                    continue

            for s in self.SELECTORS["continue_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=3)
                    break
                except Exception:
                    continue
            await asyncio.sleep(1)

            # Password step
            for s in self.SELECTORS["password_input"].split(", "):
                try:
                    self.safe_type(s, account["password"], timeout=3)
                    break
                except Exception:
                    continue

            for s in self.SELECTORS["sign_in_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=3)
                    break
                except Exception:
                    continue
            await asyncio.sleep(2)
        except Exception:
            pass
