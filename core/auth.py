"""Customer authentication system.

Handles registration, login, password hashing, session tokens,
and API key management for programmatic access.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

log = get_logger("auth", "system")

DB_PATH = Path("data/customers.db")

# Session token lifetime (24 hours)
SESSION_TTL = 86400

# API key prefix for identification
API_KEY_PREFIX = "paco_"


def _hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-SHA256.

    Returns:
        (hash_hex, salt_hex)
    """
    if salt is None:
        salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
    return key.hex(), salt.hex()


def _verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    """Verify a password against its hash."""
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
    return hmac.compare_digest(key.hex(), hash_hex)


@dataclass
class Session:
    token: str
    customer_id: str
    created_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class AuthManager:
    """Manages customer authentication, sessions, and API keys."""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH))
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS auth_credentials (
                customer_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at REAL,
                last_login REAL DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                created_at REAL,
                expires_at REAL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS auth_api_keys (
                api_key TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                name TEXT DEFAULT 'default',
                created_at REAL,
                last_used REAL DEFAULT 0,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );

            CREATE INDEX IF NOT EXISTS idx_auth_username ON auth_credentials(username);
            CREATE INDEX IF NOT EXISTS idx_sessions_customer ON auth_sessions(customer_id);
            CREATE INDEX IF NOT EXISTS idx_api_keys_customer ON auth_api_keys(customer_id);
        """)
        self.db.commit()

    # --- Registration ---

    def register(self, customer_id: str, username: str, password: str) -> bool:
        """Register credentials for an existing customer.

        Args:
            customer_id: ID from the customers table
            username: Chosen username (unique)
            password: Plaintext password (will be hashed)

        Returns:
            True if registered, False if username taken
        """
        existing = self.db.execute(
            "SELECT 1 FROM auth_credentials WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return False

        pw_hash, pw_salt = _hash_password(password)
        self.db.execute(
            """INSERT INTO auth_credentials
               (customer_id, username, password_hash, password_salt, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, username.lower(), pw_hash, pw_salt, time.time()),
        )
        self.db.commit()
        log.info(f"Credentials registered for {customer_id} ({username})")
        return True

    # --- Login ---

    def login(self, username: str, password: str) -> Optional[Session]:
        """Authenticate and create a session.

        Returns:
            Session object if successful, None if failed
        """
        row = self.db.execute(
            "SELECT * FROM auth_credentials WHERE username = ?", (username.lower(),)
        ).fetchone()

        if not row:
            return None

        if not _verify_password(password, row["password_hash"], row["password_salt"]):
            return None

        # Update last login
        self.db.execute(
            "UPDATE auth_credentials SET last_login = ? WHERE customer_id = ?",
            (time.time(), row["customer_id"]),
        )

        # Create session
        session = self._create_session(row["customer_id"])
        self.db.commit()
        log.info(f"Login successful: {username}")
        return session

    def _create_session(self, customer_id: str) -> Session:
        """Create a new session token."""
        # Clean expired sessions for this customer
        self.db.execute(
            "DELETE FROM auth_sessions WHERE customer_id = ? OR expires_at < ?",
            (customer_id, time.time()),
        )

        token = secrets.token_urlsafe(48)
        now = time.time()
        session = Session(
            token=token,
            customer_id=customer_id,
            created_at=now,
            expires_at=now + SESSION_TTL,
        )

        self.db.execute(
            """INSERT INTO auth_sessions (token, customer_id, created_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (token, customer_id, now, now + SESSION_TTL),
        )
        self.db.commit()
        return session

    # --- Session validation ---

    def validate_session(self, token: str) -> Optional[str]:
        """Validate a session token.

        Returns:
            customer_id if valid, None if expired/invalid
        """
        row = self.db.execute(
            "SELECT customer_id, expires_at FROM auth_sessions WHERE token = ?",
            (token,),
        ).fetchone()

        if not row:
            return None
        if time.time() > row["expires_at"]:
            self.db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            self.db.commit()
            return None

        return row["customer_id"]

    def logout(self, token: str):
        """Destroy a session."""
        self.db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        self.db.commit()

    # --- API Keys ---

    def create_api_key(self, customer_id: str, name: str = "default") -> str:
        """Generate an API key for programmatic access.

        Returns:
            The API key string (only shown once)
        """
        raw_key = secrets.token_urlsafe(32)
        api_key = f"{API_KEY_PREFIX}{raw_key}"

        self.db.execute(
            """INSERT INTO auth_api_keys (api_key, customer_id, name, created_at)
               VALUES (?, ?, ?, ?)""",
            (api_key, customer_id, name, time.time()),
        )
        self.db.commit()
        log.info(f"API key created for {customer_id}: {name}")
        return api_key

    def validate_api_key(self, api_key: str) -> Optional[str]:
        """Validate an API key.

        Returns:
            customer_id if valid, None otherwise
        """
        row = self.db.execute(
            "SELECT customer_id FROM auth_api_keys WHERE api_key = ? AND active = 1",
            (api_key,),
        ).fetchone()

        if not row:
            return None

        self.db.execute(
            "UPDATE auth_api_keys SET last_used = ? WHERE api_key = ?",
            (time.time(), api_key),
        )
        self.db.commit()
        return row["customer_id"]

    def list_api_keys(self, customer_id: str) -> list[dict]:
        """List API keys for a customer (keys are masked)."""
        rows = self.db.execute(
            """SELECT api_key, name, created_at, last_used, active
               FROM auth_api_keys WHERE customer_id = ?""",
            (customer_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["api_key"] = d["api_key"][:10] + "..." + d["api_key"][-4:]
            result.append(d)
        return result

    def revoke_api_key(self, api_key: str, customer_id: str) -> bool:
        """Revoke an API key."""
        result = self.db.execute(
            "UPDATE auth_api_keys SET active = 0 WHERE api_key = ? AND customer_id = ?",
            (api_key, customer_id),
        )
        self.db.commit()
        return result.rowcount > 0

    # --- Password management ---

    def change_password(self, customer_id: str, old_password: str, new_password: str) -> bool:
        """Change a customer's password."""
        row = self.db.execute(
            "SELECT password_hash, password_salt FROM auth_credentials WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()

        if not row or not _verify_password(old_password, row["password_hash"], row["password_salt"]):
            return False

        pw_hash, pw_salt = _hash_password(new_password)
        self.db.execute(
            "UPDATE auth_credentials SET password_hash = ?, password_salt = ? WHERE customer_id = ?",
            (pw_hash, pw_salt, customer_id),
        )
        # Invalidate all sessions
        self.db.execute(
            "DELETE FROM auth_sessions WHERE customer_id = ?", (customer_id,)
        )
        self.db.commit()
        log.info(f"Password changed for {customer_id}")
        return True

    def get_username(self, customer_id: str) -> Optional[str]:
        """Get username for a customer ID."""
        row = self.db.execute(
            "SELECT username FROM auth_credentials WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        return row["username"] if row else None

    def has_credentials(self, customer_id: str) -> bool:
        """Check if a customer has login credentials."""
        row = self.db.execute(
            "SELECT 1 FROM auth_credentials WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        return row is not None
