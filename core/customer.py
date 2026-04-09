"""Customer management for the ACO (Automated Checkout) service.

Handles customer onboarding, profile storage, PAS (Pay After Success)
fee tracking, and customer-controlled data management.

All customer data (credentials, card info, addresses) is encrypted
at rest. Customers choose whether to keep or delete their data.
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.profile import CheckoutProfile, get_cipher
from utils.logger import get_logger

log = get_logger("customer", "system")

DB_PATH = Path("data/customers.db")

# PAS (Pay After Success) fee schedule
PAS_FEES = {
    "booster_bundle": {"min": 2.00, "max": 7.00},
    "etb": {"min": 5.00, "max": 15.00},
    "booster_box": {"min": 10.00, "max": 25.00},
    "pc_etb": {"min": 15.00, "max": 40.00},
    "tech_sticker": {"min": 1.50, "max": 3.00},
    "blister": {"min": 1.50, "max": 3.00},
    "upc": {"min": 20.00, "max": 50.00},
    "collection_box": {"min": 5.00, "max": 20.00},
    "tin": {"min": 2.00, "max": 5.00},
    "other": {"min": 3.00, "max": 10.00},
}

# Payment deadline after successful checkout (hours)
PAYMENT_NOTIFICATION_WINDOW = 24
PAYMENT_DEADLINE_HOURS = 72

# Card charge disclaimer
CARD_DISCLAIMER = (
    "DISCLAIMER: By providing your payment information, you authorize us to "
    "use your card details solely to complete purchases on your behalf through "
    "the selected retailer(s). Your card will be charged directly by the "
    "retailer for the product price at checkout -- we never charge your card "
    "ourselves. The only fee we collect is the PAS (Pay After Success) service "
    "fee, which is billed separately via Stripe after a successful checkout. "
    "All payment data is AES-256 encrypted at rest. You may request deletion "
    "of your stored data at any time through the dashboard or by contacting us."
)


@dataclass
class Customer:
    """A registered customer of the ACO service."""
    customer_id: str
    discord_id: str
    discord_name: str
    email: str
    status: str = "active"       # active, suspended, banned
    tier: str = "standard"       # standard, bulk, vip
    data_retention: str = "keep" # keep, delete_after_checkout
    created_at: float = field(default_factory=time.time)
    total_checkouts: int = 0
    total_fees_paid: float = 0.0
    total_fees_owed: float = 0.0
    notes: str = ""


@dataclass
class CustomerProfile:
    """A customer's checkout profile (encrypted at rest)."""
    profile_id: str
    customer_id: str
    retailer: str                # which retailer this profile is for
    profile_data: dict = field(default_factory=dict)  # encrypted blob
    created_at: float = field(default_factory=time.time)
    used: bool = False
    purged: bool = False         # True if customer requested deletion


@dataclass
class CheckoutOrder:
    """A checkout performed on behalf of a customer."""
    order_id: str
    customer_id: str
    retailer: str
    product_name: str
    product_url: str
    price: float
    pas_fee: float
    status: str = "pending"      # pending, success, failed, cancelled
    fee_status: str = "unpaid"   # unpaid, notified, paid, overdue
    checkout_ms: int = 0
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    stripe_payment_id: str = ""


class CustomerManager:
    """Manages customers, profiles, orders, and PAS billing."""

    def __init__(self):
        self.cipher = get_cipher()
        self._init_db()
        log.info("Customer manager initialized")

    def _init_db(self):
        """Initialize SQLite database."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH))
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                discord_id TEXT UNIQUE NOT NULL,
                discord_name TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                tier TEXT DEFAULT 'standard',
                data_retention TEXT DEFAULT 'keep',
                created_at REAL,
                total_checkouts INTEGER DEFAULT 0,
                total_fees_paid REAL DEFAULT 0.0,
                total_fees_owed REAL DEFAULT 0.0,
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS customer_profiles (
                profile_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                retailer TEXT NOT NULL,
                encrypted_data TEXT NOT NULL,
                created_at REAL,
                used INTEGER DEFAULT 0,
                purged INTEGER DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS checkout_orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                retailer TEXT NOT NULL,
                product_name TEXT,
                product_url TEXT,
                price REAL DEFAULT 0.0,
                pas_fee REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                fee_status TEXT DEFAULT 'unpaid',
                checkout_ms INTEGER DEFAULT 0,
                created_at REAL,
                completed_at REAL DEFAULT 0.0,
                stripe_payment_id TEXT DEFAULT '',
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE INDEX IF NOT EXISTS idx_orders_customer ON checkout_orders(customer_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON checkout_orders(status);
            CREATE INDEX IF NOT EXISTS idx_profiles_customer ON customer_profiles(customer_id);
        """)
        self.db.commit()

    # --- Customer CRUD ---

    def add_customer(
        self,
        discord_id: str,
        discord_name: str,
        email: str,
        tier: str = "standard",
        data_retention: str = "keep",
    ) -> Customer:
        """Register a new customer."""
        import hashlib
        customer_id = hashlib.sha256(f"{discord_id}:{time.time()}".encode()).hexdigest()[:12]

        customer = Customer(
            customer_id=customer_id,
            discord_id=discord_id,
            discord_name=discord_name,
            email=email,
            tier=tier,
            data_retention=data_retention,
        )

        self.db.execute(
            """INSERT INTO customers
               (customer_id, discord_id, discord_name, email, status, tier,
                data_retention, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, discord_id, discord_name, email, "active", tier,
             data_retention, time.time()),
        )
        self.db.commit()
        log.info(f"New customer registered: {discord_name} ({customer_id})")
        return customer

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get customer by ID."""
        row = self.db.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if not row:
            return None
        row_dict = dict(row)
        # Handle older DB rows missing data_retention column
        if "data_retention" not in row_dict:
            row_dict["data_retention"] = "keep"
        return Customer(**row_dict)

    def get_customer_by_discord(self, discord_id: str) -> Optional[Customer]:
        """Get customer by Discord ID."""
        row = self.db.execute(
            "SELECT * FROM customers WHERE discord_id = ?", (discord_id,)
        ).fetchone()
        if not row:
            return None
        row_dict = dict(row)
        if "data_retention" not in row_dict:
            row_dict["data_retention"] = "keep"
        return Customer(**row_dict)

    def list_customers(self, status: str = None) -> list[Customer]:
        """List all customers, optionally filtered by status."""
        if status:
            rows = self.db.execute(
                "SELECT * FROM customers WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM customers ORDER BY created_at DESC"
            ).fetchall()
        results = []
        for r in rows:
            row_dict = dict(r)
            if "data_retention" not in row_dict:
                row_dict["data_retention"] = "keep"
            results.append(Customer(**row_dict))
        return results

    def update_data_retention(self, customer_id: str, preference: str):
        """Update a customer's data retention preference.

        Args:
            customer_id: Customer ID
            preference: 'keep' to retain data, 'delete_after_checkout' to auto-delete
        """
        self.db.execute(
            "UPDATE customers SET data_retention = ? WHERE customer_id = ?",
            (preference, customer_id),
        )
        self.db.commit()
        log.info(f"Data retention updated for {customer_id}: {preference}")

    def suspend_customer(self, customer_id: str, reason: str = ""):
        """Suspend a customer (e.g., for non-payment)."""
        self.db.execute(
            "UPDATE customers SET status = 'suspended', notes = ? WHERE customer_id = ?",
            (reason, customer_id),
        )
        self.db.commit()
        log.warning(f"Customer suspended: {customer_id} - {reason}")

    def ban_customer(self, customer_id: str, reason: str = ""):
        """Ban a customer permanently."""
        self.db.execute(
            "UPDATE customers SET status = 'banned', notes = ? WHERE customer_id = ?",
            (reason, customer_id),
        )
        self.db.commit()
        log.warning(f"Customer banned: {customer_id} - {reason}")

    # --- Profile Management ---

    def store_profile(
        self, customer_id: str, retailer: str, profile_data: dict
    ) -> str:
        """Store an encrypted customer checkout profile.

        Args:
            customer_id: Customer ID
            retailer: Retailer name (pokemon_center, target, etc.)
            profile_data: Dict with shipping, billing, payment info

        Returns:
            Profile ID
        """
        import hashlib
        profile_id = hashlib.sha256(
            f"{customer_id}:{retailer}:{time.time()}".encode()
        ).hexdigest()[:12]

        # Encrypt the profile data
        encrypted = self.cipher.encrypt(json.dumps(profile_data).encode()).decode()

        self.db.execute(
            """INSERT INTO customer_profiles
               (profile_id, customer_id, retailer, encrypted_data, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (profile_id, customer_id, retailer, encrypted, time.time()),
        )
        self.db.commit()
        log.info(f"Profile stored for customer {customer_id} ({retailer})")
        return profile_id

    def get_profile(self, customer_id: str, retailer: str) -> Optional[CheckoutProfile]:
        """Retrieve and decrypt a customer's checkout profile."""
        row = self.db.execute(
            """SELECT encrypted_data FROM customer_profiles
               WHERE customer_id = ? AND retailer = ? AND purged = 0
               ORDER BY created_at DESC LIMIT 1""",
            (customer_id, retailer),
        ).fetchone()

        if not row:
            return None

        try:
            data = json.loads(self.cipher.decrypt(row["encrypted_data"].encode()).decode())
            return CheckoutProfile(
                name=f"Customer {customer_id}",
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                address1=data.get("address1", ""),
                address2=data.get("address2", ""),
                city=data.get("city", ""),
                state=data.get("state", ""),
                zip_code=data.get("zip", ""),
                country=data.get("country", "US"),
                card_number=data.get("card_number", ""),
                exp_month=data.get("exp_month", ""),
                exp_year=data.get("exp_year", ""),
                cvv=data.get("cvv", ""),
                cardholder=data.get("cardholder", ""),
            )
        except Exception as e:
            log.error(f"Failed to decrypt profile for {customer_id}: {e}")
            return None

    def get_all_profiles(self, customer_id: str) -> list[tuple[str, CheckoutProfile]]:
        """Get all active profiles for a customer.

        Returns:
            List of (retailer, CheckoutProfile) tuples
        """
        rows = self.db.execute(
            """SELECT retailer, encrypted_data FROM customer_profiles
               WHERE customer_id = ? AND purged = 0
               ORDER BY created_at DESC""",
            (customer_id,),
        ).fetchall()

        profiles = []
        for row in rows:
            try:
                data = json.loads(self.cipher.decrypt(row["encrypted_data"].encode()).decode())
                profile = CheckoutProfile(
                    name=f"Customer {customer_id}",
                    first_name=data.get("first_name", ""),
                    last_name=data.get("last_name", ""),
                    email=data.get("email", ""),
                    phone=data.get("phone", ""),
                    address1=data.get("address1", ""),
                    address2=data.get("address2", ""),
                    city=data.get("city", ""),
                    state=data.get("state", ""),
                    zip_code=data.get("zip", ""),
                    country=data.get("country", "US"),
                    card_number=data.get("card_number", ""),
                    exp_month=data.get("exp_month", ""),
                    exp_year=data.get("exp_year", ""),
                    cvv=data.get("cvv", ""),
                    cardholder=data.get("cardholder", ""),
                )
                profiles.append((row["retailer"], profile))
            except Exception:
                continue

        return profiles

    def get_profile_summary(self, customer_id: str) -> list[dict]:
        """Get a non-sensitive summary of stored profiles (for display)."""
        rows = self.db.execute(
            """SELECT profile_id, retailer, created_at, used, purged
               FROM customer_profiles
               WHERE customer_id = ?
               ORDER BY created_at DESC""",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_customer_data(self, customer_id: str):
        """Customer-requested deletion of all their stored profile data.

        Overwrites encrypted data and marks profiles as purged.
        Order history is retained for billing records.
        """
        self.db.execute(
            """UPDATE customer_profiles
               SET encrypted_data = 'DELETED_BY_CUSTOMER', purged = 1
               WHERE customer_id = ?""",
            (customer_id,),
        )
        self.db.commit()
        log.info(f"Customer data deleted by request: {customer_id}")

    def delete_single_profile(self, customer_id: str, retailer: str):
        """Customer-requested deletion of a specific retailer profile."""
        self.db.execute(
            """UPDATE customer_profiles
               SET encrypted_data = 'DELETED_BY_CUSTOMER', purged = 1
               WHERE customer_id = ? AND retailer = ?""",
            (customer_id, retailer),
        )
        self.db.commit()
        log.info(f"Profile deleted by customer request: {customer_id} ({retailer})")

    # --- Order / PAS Tracking ---

    def create_order(
        self,
        customer_id: str,
        retailer: str,
        product_name: str,
        product_url: str,
        price: float,
        product_type: str = "other",
    ) -> CheckoutOrder:
        """Create a new checkout order for a customer."""
        import hashlib
        order_id = hashlib.sha256(
            f"{customer_id}:{retailer}:{time.time()}".encode()
        ).hexdigest()[:10].upper()

        # Calculate PAS fee
        fee_range = PAS_FEES.get(product_type, PAS_FEES["other"])
        # Fee scales with price: higher price items = higher fee
        fee_ratio = min(price / 100.0, 1.0)
        pas_fee = fee_range["min"] + (fee_range["max"] - fee_range["min"]) * fee_ratio

        # Bulk discount
        customer = self.get_customer(customer_id)
        if customer and customer.tier == "bulk":
            pas_fee *= 0.8  # 20% discount for bulk customers

        order = CheckoutOrder(
            order_id=order_id,
            customer_id=customer_id,
            retailer=retailer,
            product_name=product_name,
            product_url=product_url,
            price=price,
            pas_fee=round(pas_fee, 2),
        )

        self.db.execute(
            """INSERT INTO checkout_orders
               (order_id, customer_id, retailer, product_name, product_url,
                price, pas_fee, status, fee_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, customer_id, retailer, product_name, product_url,
             price, pas_fee, "pending", "unpaid", time.time()),
        )
        self.db.commit()
        return order

    def complete_order(self, order_id: str, checkout_ms: int = 0):
        """Mark an order as successfully checked out."""
        self.db.execute(
            """UPDATE checkout_orders
               SET status = 'success', completed_at = ?, checkout_ms = ?, fee_status = 'notified'
               WHERE order_id = ?""",
            (time.time(), checkout_ms, order_id),
        )

        # Update customer stats
        row = self.db.execute(
            "SELECT customer_id, pas_fee FROM checkout_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if row:
            self.db.execute(
                """UPDATE customers
                   SET total_checkouts = total_checkouts + 1,
                       total_fees_owed = total_fees_owed + ?
                   WHERE customer_id = ?""",
                (row["pas_fee"], row["customer_id"]),
            )

        self.db.commit()
        log.info(f"Order completed: {order_id}")

    def fail_order(self, order_id: str, reason: str = ""):
        """Mark an order as failed."""
        self.db.execute(
            """UPDATE checkout_orders
               SET status = 'failed', completed_at = ?
               WHERE order_id = ?""",
            (time.time(), order_id),
        )
        self.db.commit()

    def record_payment(self, order_id: str, stripe_payment_id: str = ""):
        """Record that a customer paid their PAS fee."""
        row = self.db.execute(
            "SELECT customer_id, pas_fee FROM checkout_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()

        if row:
            self.db.execute(
                """UPDATE checkout_orders
                   SET fee_status = 'paid', stripe_payment_id = ?
                   WHERE order_id = ?""",
                (stripe_payment_id, order_id),
            )
            self.db.execute(
                """UPDATE customers
                   SET total_fees_paid = total_fees_paid + ?,
                       total_fees_owed = total_fees_owed - ?
                   WHERE customer_id = ?""",
                (row["pas_fee"], row["pas_fee"], row["customer_id"]),
            )
            self.db.commit()
            log.info(f"Payment recorded for order {order_id}: ${row['pas_fee']:.2f}")

    def get_overdue_orders(self) -> list[CheckoutOrder]:
        """Get orders past the payment deadline."""
        cutoff = time.time() - (PAYMENT_DEADLINE_HOURS * 3600)
        rows = self.db.execute(
            """SELECT * FROM checkout_orders
               WHERE status = 'success' AND fee_status IN ('unpaid', 'notified')
               AND completed_at < ? AND completed_at > 0""",
            (cutoff,),
        ).fetchall()
        return [CheckoutOrder(**dict(r)) for r in rows]

    def get_customer_orders(self, customer_id: str) -> list[CheckoutOrder]:
        """Get all orders for a customer."""
        rows = self.db.execute(
            "SELECT * FROM checkout_orders WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
        return [CheckoutOrder(**dict(r)) for r in rows]

    # --- Service Stats ---

    def get_service_stats(self) -> dict:
        """Get aggregated service statistics."""
        stats = {}
        stats["total_customers"] = self.db.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]
        stats["active_customers"] = self.db.execute(
            "SELECT COUNT(*) FROM customers WHERE status = 'active'"
        ).fetchone()[0]
        stats["total_checkouts"] = self.db.execute(
            "SELECT COUNT(*) FROM checkout_orders WHERE status = 'success'"
        ).fetchone()[0]
        stats["total_revenue"] = self.db.execute(
            "SELECT COALESCE(SUM(pas_fee), 0) FROM checkout_orders WHERE fee_status = 'paid'"
        ).fetchone()[0]
        stats["outstanding_fees"] = self.db.execute(
            "SELECT COALESCE(SUM(pas_fee), 0) FROM checkout_orders WHERE status = 'success' AND fee_status != 'paid'"
        ).fetchone()[0]
        stats["success_rate"] = self.db.execute(
            """SELECT CAST(SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS FLOAT)
               / MAX(COUNT(*), 1) * 100
               FROM checkout_orders"""
        ).fetchone()[0] or 0.0

        return stats
