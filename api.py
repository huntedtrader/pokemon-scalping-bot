"""REST API for customer self-service.

FastAPI endpoints for registration, login, profile management,
orders, data controls, and API key management. Authenticated
via session tokens (Cookie/Header) or API keys.

Run:
    uvicorn api:app --host 0.0.0.0 --port 8080
"""

import time
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from core.auth import AuthManager, API_KEY_PREFIX
from core.customer import CustomerManager, CARD_DISCLAIMER, PAS_FEES

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PokeACO API",
    description="Pokemon TCG Automated Checkout - Customer Self-Service API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singletons (created once on startup)
auth_mgr = AuthManager()
customer_mgr = CustomerManager()

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    discord_id: str
    discord_name: str
    email: str
    tier: str = "standard"
    data_retention: str = "keep"


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileRequest(BaseModel):
    retailer: str
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    address1: str
    address2: str = ""
    city: str
    state: str
    zip: str
    country: str = "US"
    card_number: str
    exp_month: str
    exp_year: str
    cvv: str
    cardholder: str


class RetentionRequest(BaseModel):
    preference: str = Field(pattern="^(keep|delete_after_checkout)$")


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ApiKeyRequest(BaseModel):
    name: str = "default"


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def get_current_customer(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> str:
    """Extract and validate the caller's identity.

    Accepts either:
      - Header: Authorization: Bearer <session_token>
      - Header: Authorization: ApiKey <api_key>
      - Cookie: session_token=<token>

    Returns customer_id or raises 401.
    """
    token = None
    api_key = None

    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2:
            scheme, value = parts
            if scheme.lower() == "bearer":
                token = value
            elif scheme.lower() == "apikey":
                api_key = value
    elif session_token:
        token = session_token

    # Try session token
    if token:
        customer_id = auth_mgr.validate_session(token)
        if customer_id:
            return customer_id

    # Try API key
    if api_key:
        customer_id = auth_mgr.validate_api_key(api_key)
        if customer_id:
            return customer_id

    raise HTTPException(status_code=401, detail="Not authenticated")


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "PokeACO", "time": time.time()}


@app.get("/api/disclaimer")
def disclaimer():
    return {"disclaimer": CARD_DISCLAIMER}


@app.get("/api/fees")
def fees():
    return {"fees": PAS_FEES}


@app.post("/api/register")
def register(req: RegisterRequest):
    """Register a new customer account."""
    # Check if discord ID already exists
    existing = customer_mgr.get_customer_by_discord(req.discord_id)
    if existing:
        raise HTTPException(400, "Discord ID already registered")

    # Create customer record
    customer = customer_mgr.add_customer(
        discord_id=req.discord_id,
        discord_name=req.discord_name,
        email=req.email,
        tier=req.tier,
        data_retention=req.data_retention,
    )

    # Create auth credentials
    ok = auth_mgr.register(customer.customer_id, req.username, req.password)
    if not ok:
        raise HTTPException(400, "Username already taken")

    # Auto-login
    session = auth_mgr.login(req.username, req.password)

    return {
        "customer_id": customer.customer_id,
        "username": req.username,
        "session_token": session.token if session else None,
        "expires_at": session.expires_at if session else None,
        "message": "Account created successfully",
    }


@app.post("/api/login")
def login(req: LoginRequest):
    """Login and receive a session token."""
    session = auth_mgr.login(req.username, req.password)
    if not session:
        raise HTTPException(401, "Invalid username or password")

    response = JSONResponse({
        "customer_id": session.customer_id,
        "session_token": session.token,
        "expires_at": session.expires_at,
    })
    response.set_cookie(
        key="session_token",
        value=session.token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@app.post("/api/logout")
def logout(customer_id: str = Depends(get_current_customer),
           authorization: Optional[str] = Header(None),
           session_token: Optional[str] = Cookie(None)):
    """Destroy the current session."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    elif session_token:
        token = session_token

    if token:
        auth_mgr.logout(token)

    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("session_token")
    return response


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


@app.get("/api/me")
def get_me(customer_id: str = Depends(get_current_customer)):
    """Get current customer info."""
    customer = customer_mgr.get_customer(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    username = auth_mgr.get_username(customer_id)
    return {
        "customer_id": customer.customer_id,
        "username": username,
        "discord_name": customer.discord_name,
        "email": customer.email,
        "status": customer.status,
        "tier": customer.tier,
        "data_retention": customer.data_retention,
        "total_checkouts": customer.total_checkouts,
        "total_fees_paid": customer.total_fees_paid,
        "total_fees_owed": customer.total_fees_owed,
        "created_at": customer.created_at,
    }


# --- Orders ---


@app.get("/api/orders")
def get_orders(customer_id: str = Depends(get_current_customer)):
    """Get all orders for the authenticated customer."""
    orders = customer_mgr.get_customer_orders(customer_id)
    return {
        "orders": [
            {
                "order_id": o.order_id,
                "retailer": o.retailer,
                "product_name": o.product_name,
                "price": o.price,
                "pas_fee": o.pas_fee,
                "status": o.status,
                "fee_status": o.fee_status,
                "checkout_ms": o.checkout_ms,
                "created_at": o.created_at,
                "completed_at": o.completed_at,
            }
            for o in orders
        ]
    }


# --- Profiles ---


@app.get("/api/profiles")
def get_profiles(customer_id: str = Depends(get_current_customer)):
    """Get profile summaries (no sensitive data)."""
    profiles = customer_mgr.get_profile_summary(customer_id)
    return {"profiles": profiles}


@app.post("/api/profiles")
def add_profile(req: ProfileRequest, customer_id: str = Depends(get_current_customer)):
    """Add a checkout profile for a retailer."""
    valid_retailers = [
        "pokemon_center", "target", "walmart",
        "amazon", "bestbuy", "tcgplayer", "ebay",
    ]
    if req.retailer not in valid_retailers:
        raise HTTPException(400, f"Invalid retailer. Choose from: {valid_retailers}")

    profile_data = {
        "first_name": req.first_name,
        "last_name": req.last_name,
        "email": req.email,
        "phone": req.phone,
        "address1": req.address1,
        "address2": req.address2,
        "city": req.city,
        "state": req.state,
        "zip": req.zip,
        "country": req.country,
        "card_number": req.card_number,
        "exp_month": req.exp_month,
        "exp_year": req.exp_year,
        "cvv": req.cvv,
        "cardholder": req.cardholder,
    }

    profile_id = customer_mgr.store_profile(customer_id, req.retailer, profile_data)
    return {"profile_id": profile_id, "retailer": req.retailer, "message": "Profile stored (encrypted)"}


@app.delete("/api/profiles/{retailer}")
def delete_profile(retailer: str, customer_id: str = Depends(get_current_customer)):
    """Delete a specific retailer profile."""
    customer_mgr.delete_single_profile(customer_id, retailer)
    return {"message": f"Profile for {retailer} deleted"}


# --- Data management ---


@app.delete("/api/data")
def delete_all_data(customer_id: str = Depends(get_current_customer)):
    """Delete all stored profile data. Order history is retained for billing."""
    customer_mgr.delete_customer_data(customer_id)
    return {"message": "All profile data deleted. Order history retained for billing records."}


@app.put("/api/settings/retention")
def update_retention(req: RetentionRequest, customer_id: str = Depends(get_current_customer)):
    """Update data retention preference."""
    customer_mgr.update_data_retention(customer_id, req.preference)
    return {"data_retention": req.preference}


# --- Password ---


@app.put("/api/password")
def change_password(req: PasswordRequest, customer_id: str = Depends(get_current_customer)):
    """Change password. Invalidates all existing sessions."""
    ok = auth_mgr.change_password(customer_id, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(400, "Current password is incorrect")
    return {"message": "Password changed. All sessions invalidated -- please log in again."}


# --- API Keys ---


@app.post("/api/keys")
def create_key(req: ApiKeyRequest, customer_id: str = Depends(get_current_customer)):
    """Create an API key for programmatic access. The key is only shown once."""
    api_key = auth_mgr.create_api_key(customer_id, req.name)
    return {
        "api_key": api_key,
        "name": req.name,
        "message": "Save this key -- it will not be shown again.",
    }


@app.get("/api/keys")
def list_keys(customer_id: str = Depends(get_current_customer)):
    """List API keys (masked)."""
    keys = auth_mgr.list_api_keys(customer_id)
    return {"api_keys": keys}


@app.delete("/api/keys/{api_key}")
def revoke_key(api_key: str, customer_id: str = Depends(get_current_customer)):
    """Revoke an API key."""
    ok = auth_mgr.revoke_api_key(api_key, customer_id)
    if not ok:
        raise HTTPException(404, "API key not found or already revoked")
    return {"message": "API key revoked"}
