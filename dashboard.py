"""Streamlit dashboard for the Pokemon ACO Service.

Clean, simple UI for both operators and customers.
Customers log in to view orders, manage profiles, and control their data.

Usage: streamlit run dashboard.py --server.port 8891
"""

import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

st.set_page_config(
    page_title="Pokemon ACO",
    page_icon="pokeball",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Clean CSS ---
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

.stApp {
    background-color: #0c0c14;
    color: #e8e8e8;
    font-family: 'Inter', sans-serif;
}

h1 { font-weight: 700; margin-bottom: 0.5rem; }
h2 { font-weight: 600; color: #ccc; }
h3 { font-weight: 600; }

.card {
    background: #14142a;
    border: 1px solid #1e1e3a;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}

.stat-box {
    background: linear-gradient(135deg, #14142a, #1a1a36);
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.stat-val {
    font-size: 2rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.stat-lbl {
    font-size: 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-top: 4px;
}

.order-item {
    background: #0f0f1e;
    border: 1px solid #1a1a33;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 6px 0;
}

.green { color: #00e676; }
.yellow { color: #ffd740; }
.red { color: #ff5252; }
.blue { color: #40c4ff; }
.dim { color: #666; }
.mono { font-family: 'JetBrains Mono', monospace; }

.disclaimer-box {
    background: #1a1500;
    border: 1px solid #4a3800;
    border-left: 4px solid #ffd740;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    font-size: 0.85rem;
    line-height: 1.5;
    color: #ccc;
    margin: 16px 0;
}

.danger-zone {
    background: #1a0505;
    border: 1px solid #4a1515;
    border-radius: 12px;
    padding: 20px;
    margin-top: 20px;
}

.login-box {
    max-width: 400px;
    margin: 40px auto;
    background: #14142a;
    border: 1px solid #1e1e3a;
    border-radius: 16px;
    padding: 32px;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_cm():
    from core.customer import CustomerManager
    return CustomerManager()


def get_auth():
    from core.auth import AuthManager
    return AuthManager()


def get_disclaimer():
    from core.customer import CARD_DISCLAIMER
    return CARD_DISCLAIMER


def read_log_file():
    log_dir = Path("logs")
    if not log_dir.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"bot_{today}.log"
    if not log_file.exists():
        return []
    return log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-150:]


def is_logged_in() -> bool:
    return bool(st.session_state.get("customer_id"))


def current_customer_id() -> str:
    return st.session_state.get("customer_id", "")


def do_logout():
    auth = get_auth()
    token = st.session_state.get("session_token")
    if token:
        auth.logout(token)
    for k in ["customer_id", "session_token", "username"]:
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
for k in ["customer_id", "session_token", "username"]:
    if k not in st.session_state:
        st.session_state[k] = ""


# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("## Pokemon ACO")
    st.markdown("---")

    if is_logged_in():
        st.markdown(
            f"Logged in as **{st.session_state['username'] or current_customer_id()}**"
        )
        if st.button("Logout"):
            do_logout()
            st.rerun()

        page = st.radio(
            "Menu",
            ["Home", "My Orders", "My Profile", "My Data", "API Keys", "Admin"],
            label_visibility="collapsed",
        )
    else:
        page = st.radio(
            "Menu",
            ["Home", "Login", "Register", "Admin"],
            label_visibility="collapsed",
        )

    st.markdown("---")
    config = load_config()
    dry = config.get("general", {}).get("dry_run", True)
    st.markdown(
        f"**Status:** <span class='{'yellow' if dry else 'green'}'>"
        f"{'Test Mode' if dry else 'Live'}</span>",
        unsafe_allow_html=True,
    )


# ========== HOME ==========
if page == "Home":
    st.markdown("# Welcome to Pokemon ACO")
    st.markdown("Your automated checkout service for Pokemon TCG products.")

    st.markdown("---")

    st.markdown("### How It Works")
    cols = st.columns(4)
    steps = [
        ("1. Register", "Create your account and submit your checkout profile."),
        ("2. We Monitor", "Our bot watches all major retailers 24/7 for restocks."),
        ("3. Auto Checkout", "When a drop hits, we check out instantly on your behalf."),
        ("4. You Pay PAS", "You only pay a small service fee after a successful checkout."),
    ]
    for i, (title, desc) in enumerate(steps):
        with cols[i]:
            st.markdown(f"""
            <div class="card" style="min-height:120px">
                <strong>{title}</strong><br>
                <small class="dim">{desc}</small>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Disclaimer
    st.markdown(f"""
    <div class="disclaimer-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### Supported Retailers")
    retailers = [
        ("Pokemon Center", "#ffcc00", "#000"),
        ("Target", "#cc0000", "#fff"),
        ("Walmart", "#0071ce", "#fff"),
        ("Amazon", "#ff9900", "#000"),
        ("Best Buy", "#0046be", "#fff"),
        ("TCGPlayer", "#6b21a8", "#fff"),
        ("eBay", "#e53238", "#fff"),
    ]
    tags = ""
    for name, bg, fg in retailers:
        tags += (
            f"<span style='background:{bg};color:{fg};padding:4px 12px;"
            f"border-radius:6px;font-size:0.8rem;font-weight:700;"
            f"margin-right:8px;display:inline-block;margin-bottom:6px'>{name}</span>"
        )
    st.markdown(tags, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### PAS Fee Schedule")
    st.markdown("You only pay after we successfully check out a product for you.")
    fee_data = {
        "Product Type": [
            "Tech Sticker / Blister", "Booster Bundle", "Tin",
            "ETB", "Collection Box", "Booster Box", "PC ETB", "UPC",
        ],
        "Fee": [
            "$1.50 - $3", "$2 - $7", "$2 - $5",
            "$5 - $15", "$5 - $20", "$10 - $25", "$15 - $40", "$20 - $50",
        ],
    }
    st.table(fee_data)
    st.caption("Bulk customers (15+ profiles) receive a 20% discount on all fees.")


# ========== LOGIN ==========
elif page == "Login":
    st.markdown("# Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Enter your username and password.")
            else:
                auth = get_auth()
                session = auth.login(username, password)
                if session:
                    st.session_state["customer_id"] = session.customer_id
                    st.session_state["session_token"] = session.token
                    st.session_state["username"] = username
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    st.markdown("---")
    st.caption("Don't have an account? Select **Register** from the sidebar.")


# ========== REGISTER ==========
elif page == "Register":
    st.markdown("# Register")
    st.markdown("Create your account and add a checkout profile.")

    # Disclaimer up front
    st.markdown(f"""
    <div class="disclaimer-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    with st.form("register"):
        st.markdown("### Account")
        ac1, ac2 = st.columns(2)
        with ac1:
            reg_username = st.text_input("Choose a Username (min 3 chars)")
            reg_password = st.text_input("Choose a Password (min 8 chars)", type="password")
        with ac2:
            reg_password2 = st.text_input("Confirm Password", type="password")

        st.markdown("---")

        st.markdown("### Your Info")
        c1, c2 = st.columns(2)
        with c1:
            discord_id = st.text_input("Discord ID")
            discord_name = st.text_input("Discord Username")
        with c2:
            email = st.text_input("Email")
            tier = st.selectbox("Tier", ["standard", "bulk", "vip"])

        st.markdown("---")

        st.markdown("### Checkout Profile")
        retailer = st.selectbox("Retailer", [
            "pokemon_center", "target", "walmart", "amazon", "bestbuy", "tcgplayer", "ebay"
        ], format_func=lambda x: x.replace("_", " ").title())

        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            checkout_email = st.text_input("Checkout Email")
            phone = st.text_input("Phone")
        with c2:
            address1 = st.text_input("Address Line 1")
            address2 = st.text_input("Address Line 2 (optional)")
            city = st.text_input("City")
            sc1, sc2 = st.columns(2)
            with sc1:
                state = st.text_input("State", max_chars=2)
            with sc2:
                zipcode = st.text_input("ZIP")

        st.markdown("---")

        st.markdown("### Payment")
        st.caption("Your card is charged by the retailer, not by us. We only collect PAS fees via Stripe.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            card_number = st.text_input("Card Number", type="password")
        with c2:
            exp_month = st.text_input("MM")
        with c3:
            exp_year = st.text_input("YYYY")
        with c4:
            cvv = st.text_input("CVV", type="password")
        cardholder = st.text_input("Name on Card")

        st.markdown("---")

        st.markdown("### Data Preference")
        retention = st.radio(
            "After a successful checkout:",
            ["keep", "delete_after_checkout"],
            format_func=lambda x: {
                "keep": "Keep my profile on file for future checkouts",
                "delete_after_checkout": "Delete my profile after each checkout",
            }[x],
        )

        agreed = st.checkbox("I have read and agree to the card charge disclaimer above")

        submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            if not agreed:
                st.error("You must agree to the card charge disclaimer to continue.")
            elif not reg_username or len(reg_username) < 3:
                st.error("Username must be at least 3 characters.")
            elif not reg_password or len(reg_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif reg_password != reg_password2:
                st.error("Passwords do not match.")
            elif not discord_id or not discord_name or not email:
                st.error("Please fill in your Discord ID, username, and email.")
            else:
                cm = get_cm()
                auth = get_auth()

                # Check username availability
                if not auth.register("__temp__", reg_username, reg_password):
                    st.error("Username already taken. Choose a different one.")
                else:
                    # Clean up the temp registration
                    auth.db.execute(
                        "DELETE FROM auth_credentials WHERE customer_id = '__temp__'", ()
                    )
                    auth.db.commit()

                    # Create real customer
                    customer = cm.add_customer(discord_id, discord_name, email, tier, retention)

                    # Register auth credentials
                    auth.register(customer.customer_id, reg_username, reg_password)

                    # Store profile
                    profile_data = {
                        "first_name": first_name, "last_name": last_name,
                        "email": checkout_email, "phone": phone,
                        "address1": address1, "address2": address2,
                        "city": city, "state": state.upper(), "zip": zipcode, "country": "US",
                        "card_number": card_number, "exp_month": exp_month,
                        "exp_year": exp_year, "cvv": cvv, "cardholder": cardholder,
                    }
                    cm.store_profile(customer.customer_id, retailer, profile_data)

                    # Auto-login
                    session = auth.login(reg_username, reg_password)
                    if session:
                        st.session_state["customer_id"] = session.customer_id
                        st.session_state["session_token"] = session.token
                        st.session_state["username"] = reg_username

                    st.success(
                        f"Account created! You are now logged in as **{reg_username}**. "
                        f"Your Customer ID is **{customer.customer_id}**."
                    )
                    time.sleep(1)
                    st.rerun()


# ========== MY ORDERS ==========
elif page == "My Orders":
    if not is_logged_in():
        st.warning("Please log in to view your orders.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    customer = cm.get_customer(cid)

    st.markdown("# My Orders")

    if not customer:
        st.error("Customer record not found.")
        st.stop()

    st.markdown(f"### Welcome back, {customer.discord_name}")

    orders = cm.get_customer_orders(cid)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-val green">{customer.total_checkouts}</div>
            <div class="stat-lbl">Checkouts</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-val blue">${customer.total_fees_paid:.2f}</div>
            <div class="stat-lbl">Fees Paid</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-val yellow">${customer.total_fees_owed:.2f}</div>
            <div class="stat-lbl">Balance Due</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    if orders:
        for o in orders:
            sc = {"success": "green", "failed": "red", "pending": "yellow"}.get(o.status, "dim")
            fc = {"paid": "green", "unpaid": "yellow", "overdue": "red"}.get(o.fee_status, "dim")
            ts = datetime.fromtimestamp(o.created_at).strftime("%b %d, %Y %I:%M %p")
            st.markdown(f"""
            <div class="order-item">
                <span class="{sc}" style="font-weight:700">{o.status.upper()}</span>
                <span class="dim" style="margin-left:12px">{ts}</span><br>
                <span style="font-size:1.05rem">{o.product_name}</span><br>
                <span class="dim">{o.retailer.replace('_',' ').title()}</span>
                <span class="blue" style="margin-left:12px">${o.price:.2f}</span>
                <span class="dim" style="margin-left:12px">PAS fee:</span>
                <span class="{fc}">${o.pas_fee:.2f} ({o.fee_status})</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No orders yet. We'll check out products for you as soon as they drop!")


# ========== MY PROFILE ==========
elif page == "My Profile":
    if not is_logged_in():
        st.warning("Please log in to view your profile.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    auth = get_auth()
    customer = cm.get_customer(cid)

    st.markdown("# My Profile")

    if not customer:
        st.error("Customer record not found.")
        st.stop()

    username = auth.get_username(cid)

    st.markdown(f"""
    <div class="card">
        <strong style="font-size:1.2rem">{customer.discord_name}</strong><br>
        <span class="dim">Username: <span class="mono">{username}</span></span><br>
        <span class="dim">ID: <span class="mono">{customer.customer_id}</span></span><br>
        <span class="dim">Email: {customer.email}</span><br>
        <span class="dim">Tier: <strong>{customer.tier}</strong></span><br>
        <span class="dim">Status: <span class="green">{customer.status.upper()}</span></span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Stored Profiles")
    st.caption("Your payment and address info for each retailer (encrypted).")

    profiles = cm.get_profile_summary(cid)
    active = [p for p in profiles if not p["purged"]]
    deleted = [p for p in profiles if p["purged"]]

    if active:
        for p in active:
            ts = datetime.fromtimestamp(p["created_at"]).strftime("%b %d, %Y")
            used_tag = " (used)" if p["used"] else ""
            st.markdown(f"""
            <div class="card" style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <strong>{p['retailer'].replace('_',' ').title()}</strong>{used_tag}<br>
                    <span class="dim">Added: {ts}</span>
                </div>
                <span class="green">Active</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No active profiles. Add one below.")

    if deleted:
        with st.expander("Deleted profiles"):
            for p in deleted:
                st.markdown(
                    f"- {p['retailer'].replace('_',' ').title()} -- "
                    f"<span class='red'>Deleted</span>",
                    unsafe_allow_html=True,
                )

    # Add new profile
    st.markdown("---")
    st.markdown("### Add Another Profile")

    with st.form("add_profile"):
        retailer = st.selectbox("Retailer", [
            "pokemon_center", "target", "walmart", "amazon", "bestbuy", "tcgplayer", "ebay"
        ], format_func=lambda x: x.replace("_", " ").title())

        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            checkout_email = st.text_input("Checkout Email")
            phone = st.text_input("Phone")
        with c2:
            address1 = st.text_input("Address Line 1")
            address2 = st.text_input("Address Line 2 (optional)")
            city = st.text_input("City")
            sc1, sc2 = st.columns(2)
            with sc1:
                state_val = st.text_input("State", max_chars=2)
            with sc2:
                zipcode = st.text_input("ZIP")

        st.caption("Your card is charged by the retailer, not by us.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            card_number = st.text_input("Card Number", type="password")
        with c2:
            exp_month = st.text_input("MM")
        with c3:
            exp_year = st.text_input("YYYY")
        with c4:
            cvv = st.text_input("CVV", type="password")
        cardholder = st.text_input("Name on Card")

        if st.form_submit_button("Add Profile", use_container_width=True):
            profile_data = {
                "first_name": first_name, "last_name": last_name,
                "email": checkout_email, "phone": phone,
                "address1": address1, "address2": address2,
                "city": city, "state": state_val.upper(), "zip": zipcode, "country": "US",
                "card_number": card_number, "exp_month": exp_month,
                "exp_year": exp_year, "cvv": cvv, "cardholder": cardholder,
            }
            cm.store_profile(cid, retailer, profile_data)
            st.success(f"Profile for **{retailer.replace('_',' ').title()}** added (encrypted).")
            st.rerun()

    # Change password
    st.markdown("---")
    st.markdown("### Change Password")

    with st.form("change_pw"):
        old_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password (min 8 chars)", type="password")
        new_pw2 = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Change Password"):
            if not old_pw or not new_pw:
                st.error("Fill in all password fields.")
            elif len(new_pw) < 8:
                st.error("New password must be at least 8 characters.")
            elif new_pw != new_pw2:
                st.error("New passwords do not match.")
            else:
                ok = auth.change_password(cid, old_pw, new_pw)
                if ok:
                    do_logout()
                    st.success("Password changed. Please log in again.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Current password is incorrect.")


# ========== MY DATA ==========
elif page == "My Data":
    if not is_logged_in():
        st.warning("Please log in to manage your data.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    customer = cm.get_customer(cid)

    st.markdown("# My Data")
    st.markdown("Control what we store and manage your privacy.")

    if not customer:
        st.error("Customer record not found.")
        st.stop()

    # Disclaimer
    st.markdown(f"""
    <div class="disclaimer-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Data retention preference
    st.markdown("### Data Retention Preference")
    st.markdown(
        "Choose whether we keep your checkout profiles on file for "
        "future drops, or delete them after each successful checkout."
    )

    current = customer.data_retention
    options = {
        "keep": "Keep my data on file for future checkouts",
        "delete_after_checkout": "Delete my data after each successful checkout",
    }
    choice = st.radio(
        "Your preference",
        list(options.keys()),
        format_func=lambda x: options[x],
        index=0 if current == "keep" else 1,
        key="retention_choice",
    )

    if st.button("Save Preference"):
        cm.update_data_retention(cid, choice)
        st.success(f"Preference updated: **{options[choice]}**")

    st.markdown("---")

    # Delete specific profile
    st.markdown("### Delete a Specific Profile")
    st.markdown("Remove your stored data for one retailer.")

    profiles = cm.get_profile_summary(cid)
    active = [p for p in profiles if not p["purged"]]

    if active:
        retailer_to_delete = st.selectbox(
            "Select retailer profile to delete",
            [p["retailer"] for p in active],
            format_func=lambda x: x.replace("_", " ").title(),
        )

        if st.button("Delete This Profile", type="secondary"):
            cm.delete_single_profile(cid, retailer_to_delete)
            st.success(f"Profile for **{retailer_to_delete.replace('_',' ').title()}** has been deleted.")
            st.rerun()
    else:
        st.info("No active profiles to delete.")

    # Delete all data
    st.markdown("""
    <div class="danger-zone">
        <strong style="color:#ff5252">Delete All My Data</strong><br>
        <span class="dim">This will permanently delete all your stored checkout profiles
        (payment info, addresses, credentials). Your order history is retained for
        billing records only. This action cannot be undone.</span>
    </div>
    """, unsafe_allow_html=True)

    confirm = st.checkbox("I understand this is permanent and cannot be undone")
    if confirm:
        if st.button("Delete All My Data", type="primary"):
            cm.delete_customer_data(cid)
            st.success("All your stored profile data has been permanently deleted.")
            st.rerun()


# ========== API KEYS ==========
elif page == "API Keys":
    if not is_logged_in():
        st.warning("Please log in to manage API keys.")
        st.stop()

    cid = current_customer_id()
    auth = get_auth()

    st.markdown("# API Keys")
    st.markdown("Create API keys for programmatic access to the PokeACO API.")

    # Create new key
    st.markdown("### Create a New Key")
    with st.form("create_key"):
        key_name = st.text_input("Key Name", value="default", placeholder="e.g. my-script")
        if st.form_submit_button("Generate API Key"):
            api_key = auth.create_api_key(cid, key_name)
            st.success("API key created. Copy it now -- it will not be shown again.")
            st.code(api_key, language="text")

    st.markdown("---")

    # List keys
    st.markdown("### Your API Keys")
    keys = auth.list_api_keys(cid)

    if keys:
        for k in keys:
            status = "Active" if k["active"] else "Revoked"
            sc = "green" if k["active"] else "red"
            created = datetime.fromtimestamp(k["created_at"]).strftime("%b %d, %Y")
            last_used = (
                datetime.fromtimestamp(k["last_used"]).strftime("%b %d, %Y %I:%M %p")
                if k["last_used"] else "Never"
            )
            st.markdown(f"""
            <div class="card" style="padding:14px 18px">
                <strong>{k['name']}</strong>
                <span class="{sc}" style="float:right;font-weight:700">{status}</span><br>
                <span class="dim mono" style="font-size:0.8rem">{k['api_key']}</span><br>
                <span class="dim">Created: {created} | Last used: {last_used}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No API keys yet.")

    st.markdown("---")
    st.markdown("### Usage")
    st.code(
        'curl -H "Authorization: ApiKey paco_YOUR_KEY" https://your-server/api/me',
        language="bash",
    )


# ========== ADMIN ==========
elif page == "Admin":
    st.markdown("# Admin Panel")

    admin_pw = st.text_input("Admin password", type="password")
    if admin_pw != "admin":  # Replace with real auth
        st.warning("Enter the admin password to continue.")
        st.stop()

    cm = get_cm()
    stats = cm.get_service_stats()

    cols = st.columns(5)
    admin_metrics = [
        (stats.get("active_customers", 0), "Customers", "green"),
        (stats.get("total_checkouts", 0), "Checkouts", "blue"),
        (f"{stats.get('success_rate', 0):.1f}%", "Win Rate", "yellow"),
        (f"${stats.get('total_revenue', 0):.2f}", "Revenue", "green"),
        (f"${stats.get('outstanding_fees', 0):.2f}", "Outstanding", "red"),
    ]
    for i, (val, label, color) in enumerate(admin_metrics):
        with cols[i]:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val {color}">{val}</div>
                <div class="stat-lbl">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Customer list
    st.markdown("### All Customers")
    customers = cm.list_customers()
    for c in customers:
        sc = {"active": "green", "suspended": "yellow", "banned": "red"}.get(c.status, "dim")
        st.markdown(f"""
        <div class="card" style="padding:12px 18px">
            <strong>{c.discord_name}</strong>
            <span class="{sc}" style="float:right;font-weight:700">{c.status.upper()}</span><br>
            <span class="dim mono" style="font-size:0.8rem">
                {c.customer_id} | {c.tier} | {c.total_checkouts} checkouts |
                paid ${c.total_fees_paid:.2f} | owed ${c.total_fees_owed:.2f} |
                data: {c.data_retention}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Overdue
    st.markdown("### Overdue Payments")
    overdue = cm.get_overdue_orders()
    if overdue:
        for o in overdue:
            cust = cm.get_customer(o.customer_id)
            name = cust.discord_name if cust else "Unknown"
            hrs = (time.time() - o.completed_at) / 3600
            st.markdown(f"""
            <div class="order-item">
                <span class="red" style="font-weight:700">OVERDUE ({hrs:.0f}h)</span>
                <strong style="margin-left:12px">{name}</strong>
                <span class="dim" style="margin-left:12px">Order: {o.order_id}</span>
                <span class="yellow" style="margin-left:12px">${o.pas_fee:.2f}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("No overdue payments.")

    st.markdown("---")

    # Log
    st.markdown("### Live Log")
    log_lines = read_log_file()
    if log_lines:
        filt = st.text_input("Filter", placeholder="Search logs...")
        if filt:
            log_lines = [l for l in log_lines if filt.lower() in l.lower()]
        st.code("\n".join(log_lines[-60:]), language="log")
    else:
        st.info("No logs yet.")
