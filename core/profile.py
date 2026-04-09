"""Profile management with encryption for payment data.

Loads profiles from config, encrypts sensitive fields at rest,
and provides jigged variants for multi-checkout.
"""

import base64
import os
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.jig import generate_jigged_profile
from utils.logger import get_logger

log = get_logger("profile")

KEY_FILE = Path("config/.key")


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def get_cipher(password: str = None) -> Fernet:
    """Get or create the Fernet cipher for encrypting profile data."""
    if KEY_FILE.exists():
        key_data = KEY_FILE.read_bytes()
        return Fernet(key_data)

    if password is None:
        # Generate a random key
        key = Fernet.generate_key()
    else:
        salt = os.urandom(16)
        key = _derive_key(password, salt)

    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    log.info("Encryption key generated and saved")
    return Fernet(key)


@dataclass
class CheckoutProfile:
    """A complete profile ready for checkout."""
    name: str
    first_name: str
    last_name: str
    email: str
    phone: str
    address1: str
    address2: str
    city: str
    state: str
    zip_code: str
    country: str
    card_number: str
    exp_month: str
    exp_year: str
    cvv: str
    cardholder: str

    # Billing address (if different from shipping)
    bill_address1: str = ""
    bill_address2: str = ""
    bill_city: str = ""
    bill_state: str = ""
    bill_zip: str = ""
    bill_country: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def card_last_four(self) -> str:
        return self.card_number[-4:] if self.card_number else "****"

    @property
    def exp_date(self) -> str:
        return f"{self.exp_month}/{self.exp_year}"


class ProfileManager:
    """Manages checkout profiles with encryption and jigging."""

    def __init__(self, config: dict):
        self.cipher = get_cipher()
        self.profiles: list[CheckoutProfile] = []
        self._load_profiles(config.get("profiles", []))

    def _load_profiles(self, profile_configs: list):
        """Load profiles from config, decrypting sensitive fields."""
        for pc in profile_configs:
            shipping = pc.get("shipping", {})
            billing = pc.get("billing", {})
            payment = pc.get("payment", {})

            # Decrypt card data if encrypted
            card_number = self._maybe_decrypt(payment.get("card_number", ""))
            cvv = self._maybe_decrypt(payment.get("cvv", ""))

            profile = CheckoutProfile(
                name=pc.get("name", "Default"),
                first_name=pc.get("first_name", ""),
                last_name=pc.get("last_name", ""),
                email=pc.get("email", ""),
                phone=pc.get("phone", ""),
                address1=shipping.get("address1", ""),
                address2=shipping.get("address2", ""),
                city=shipping.get("city", ""),
                state=shipping.get("state", ""),
                zip_code=shipping.get("zip", ""),
                country=shipping.get("country", "US"),
                card_number=card_number,
                exp_month=payment.get("exp_month", ""),
                exp_year=payment.get("exp_year", ""),
                cvv=cvv,
                cardholder=payment.get("cardholder", ""),
            )

            # Handle billing address
            if not billing.get("same_as_shipping", True):
                profile.bill_address1 = billing.get("address1", profile.address1)
                profile.bill_address2 = billing.get("address2", profile.address2)
                profile.bill_city = billing.get("city", profile.city)
                profile.bill_state = billing.get("state", profile.state)
                profile.bill_zip = billing.get("zip", profile.zip_code)
                profile.bill_country = billing.get("country", profile.country)

            self.profiles.append(profile)
            log.info(f"Loaded profile: {profile.name} (card ending {profile.card_last_four})")

    def _maybe_decrypt(self, value: str) -> str:
        """Decrypt a value if it's encrypted, otherwise return as-is."""
        if not value:
            return value
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except Exception:
            return value

    def encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value for storage."""
        return self.cipher.encrypt(value.encode()).decode()

    def get_profile(self, index: int = 0) -> CheckoutProfile:
        """Get a profile by index."""
        if not self.profiles:
            raise ValueError("No profiles configured")
        return self.profiles[index % len(self.profiles)]

    def get_jigged_profiles(self, count: int, base_index: int = 0) -> list[CheckoutProfile]:
        """Generate jigged variants of a base profile.

        Args:
            count: Number of variants to generate
            base_index: Index of the base profile

        Returns:
            List of CheckoutProfile objects with jigged details
        """
        base = self.profiles[base_index]
        base_dict = {
            "first_name": base.first_name,
            "last_name": base.last_name,
            "email": base.email,
            "phone": base.phone,
            "shipping": {
                "address1": base.address1,
                "address2": base.address2,
                "city": base.city,
                "state": base.state,
                "zip": base.zip_code,
                "country": base.country,
            },
            "billing": {"same_as_shipping": True},
        }

        variants = []
        for i in range(count):
            jigged = generate_jigged_profile(base_dict, variation_index=i)
            profile = CheckoutProfile(
                name=f"{base.name} (Jig #{i})",
                first_name=jigged["first_name"],
                last_name=jigged["last_name"],
                email=jigged["email"],
                phone=jigged["phone"],
                address1=jigged["shipping"]["address1"],
                address2=jigged["shipping"]["address2"],
                city=jigged["shipping"]["city"],
                state=jigged["shipping"]["state"],
                zip_code=jigged["shipping"]["zip"],
                country=jigged["shipping"]["country"],
                card_number=base.card_number,
                exp_month=base.exp_month,
                exp_year=base.exp_year,
                cvv=base.cvv,
                cardholder=base.cardholder,
            )
            variants.append(profile)

        return variants
