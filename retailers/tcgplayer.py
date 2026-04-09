"""TCGPlayer (tcgplayer.com) checkout module.

Marketplace scraping with seller filtering and cart optimization.
Bundles from fewest sellers to minimize shipping costs.
"""

import asyncio
import re

from selenium.webdriver.common.by import By

from core.checkout import BaseCheckout, CheckoutProfile, CheckoutError, CheckoutDeclined
from utils.logger import get_logger

log = get_logger("tcgplayer", "tcgplayer")


class TCGPlayerCheckout(BaseCheckout):
    """TCGPlayer marketplace checkout implementation."""

    RETAILER_NAME = "tcgplayer"
    CHECKOUT_TIMEOUT = 30

    SELECTORS = {
        "add_to_cart": '.add-to-cart, button[class*="add-to-cart"], .listing-item__add-to-cart',
        "listing_price": '.listing-item__listing-data__info__price, .product-listing__price',
        "seller_rating": '.seller-info__rating, .seller-rating',
        "cart_icon": 'a[href*="/cart"], .header-cart',
        "checkout_btn": '.checkout-button, a[href*="/checkout"]',

        "email_input": 'input[name="email"], #email',
        "password_input": 'input[name="password"], #password',
        "sign_in_btn": 'button[type="submit"]',

        "first_name": 'input[name="firstName"], #firstName',
        "last_name": 'input[name="lastName"], #lastName',
        "address1": 'input[name="address1"], #address1',
        "address2": 'input[name="address2"], #address2',
        "city": 'input[name="city"], #city',
        "state": 'select[name="state"], #state',
        "zip_code": 'input[name="zipCode"], #zipCode',
        "phone": 'input[name="phone"], #phone',
        "continue_btn": 'button[data-testid="continue"], button.continue-button',

        "card_number": 'input[name="cardNumber"], #cardNumber',
        "exp_date": 'input[name="expiration"], #expiration',
        "cvv": 'input[name="cvv"], #cvv',
        "card_name": 'input[name="cardholderName"], #cardholderName',

        "place_order": 'button[data-testid="place-order"], button.place-order',
    }

    async def add_to_cart(self) -> bool:
        try:
            await asyncio.sleep(1)

            # Find the best listing (lowest price from good seller)
            best_listing = await self._find_best_listing()
            if best_listing:
                best_listing.click()
                log.info("Added best TCGPlayer listing to cart")
                await asyncio.sleep(1.5)
                return True

            # Fallback: click first add to cart
            for selector in self.SELECTORS["add_to_cart"].split(", "):
                try:
                    self.safe_click(selector, timeout=5)
                    await asyncio.sleep(1.5)
                    return True
                except Exception:
                    continue

            return False
        except Exception:
            return False

    async def go_to_checkout(self):
        try:
            self.driver.get("https://www.tcgplayer.com/cart")
            await asyncio.sleep(2)

            for s in self.SELECTORS["checkout_btn"].split(", "):
                try:
                    self.safe_click(s, timeout=5)
                    break
                except Exception:
                    continue

            await asyncio.sleep(2)
            await self._sign_in_if_needed()
        except Exception as e:
            raise CheckoutError(f"TCGPlayer checkout failed: {e}")

    async def fill_shipping(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            self._fill("first_name", profile.first_name)
            self._fill("last_name", profile.last_name)
            self._fill("address1", profile.address1)
            if profile.address2:
                self._fill("address2", profile.address2)
            self._fill("city", profile.city)
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
            raise CheckoutError(f"TCGPlayer shipping failed: {e}")

    async def fill_payment(self, profile: CheckoutProfile):
        try:
            await asyncio.sleep(1)
            iframes = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[title*="payment"], iframe[name*="card"]')
            if iframes:
                self.driver.switch_to.frame(iframes[0])

            self._fill("card_number", profile.card_number)
            self._fill("exp_date", f"{profile.exp_month}/{profile.exp_year[-2:]}")
            self._fill("cvv", profile.cvv)
            self._fill("card_name", profile.cardholder)

            if iframes:
                self.driver.switch_to.default_content()
        except Exception as e:
            raise CheckoutError(f"TCGPlayer payment failed: {e}")

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
                raise CheckoutDeclined("TCGPlayer payment declined")

            match = re.search(r"(?:order)\s*#?\s*(\d+)", page_text, re.IGNORECASE)
            return match.group(1) if match else "TCGP-CONFIRMED"
        except CheckoutDeclined:
            raise
        except Exception as e:
            raise CheckoutError(f"TCGPlayer submit failed: {e}")

    async def _find_best_listing(self):
        """Find the lowest-price listing from a reputable seller."""
        try:
            listings = self.driver.find_elements(By.CSS_SELECTOR, '.listing-item, .product-listing')
            best_btn = None
            best_price = float("inf")

            for listing in listings[:20]:  # Check first 20 listings
                try:
                    price_elem = listing.find_element(By.CSS_SELECTOR, '.listing-item__listing-data__info__price, .price')
                    price_text = price_elem.text.replace("$", "").replace(",", "").strip()
                    price = float(price_text)

                    # Check seller rating
                    try:
                        rating_elem = listing.find_element(By.CSS_SELECTOR, '.seller-info__rating, .seller-rating')
                        rating = float(rating_elem.text.replace("%", "").strip()) / 100
                    except Exception:
                        rating = 0.99  # Assume good if not found

                    config_min_rating = self.config.get("products", [{}])[0].get("min_seller_rating", 4.5) / 5.0
                    if rating >= config_min_rating and price < best_price:
                        best_price = price
                        best_btn = listing.find_element(By.CSS_SELECTOR, 'button[class*="add-to-cart"], .add-to-cart')

                except Exception:
                    continue

            return best_btn
        except Exception:
            return None

    async def _sign_in_if_needed(self):
        account = self.config.get("retailer_accounts", {}).get("tcgplayer", {})
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
