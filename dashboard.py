"""Streamlit dashboard for the Pokemon ACO Service.

Full operator dashboard with customer management, checkout tracking,
PAS fee billing, live monitoring, and service analytics.

Usage: streamlit run dashboard.py --server.port 8891
"""

import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

st.set_page_config(
    page_title="Pokemon ACO Service",
    page_icon="pokeball",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap');

.stApp {
    background-color: #0a0a0f;
    color: #e0e0e0;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 700; }

.metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #0f3460;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }

.metric-value {
    font-size: 2.2rem;
    font-weight: 900;
    font-family: 'JetBrains Mono', monospace;
}
.metric-label {
    font-size: 0.8rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 4px;
}

.customer-card {
    background: #111122;
    border: 1px solid #222244;
    border-radius: 10px;
    padding: 16px;
    margin: 8px 0;
}

.status-active { color: #00ff88; }
.status-suspended { color: #ffcc00; }
.status-banned { color: #ff4444; }

.fee-paid { color: #00ff88; }
.fee-unpaid { color: #ffcc00; }
.fee-overdue { color: #ff4444; }

.retailer-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1px;
}
.retailer-pkc { background: #ffcc00; color: #000; }
.retailer-target { background: #cc0000; color: #fff; }
.retailer-walmart { background: #0071ce; color: #fff; }
.retailer-amazon { background: #ff9900; color: #000; }
.retailer-bestbuy { background: #0046be; color: #fff; }
.retailer-tcgp { background: #6b21a8; color: #fff; }
.retailer-ebay { background: #e53238; color: #fff; }

.order-row {
    background: #0d0d1a;
    border: 1px solid #1a1a33;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
}

.log-box {
    background: #050510;
    border: 1px solid #1a1a33;
    border-radius: 8px;
    padding: 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    max-height: 400px;
    overflow-y: auto;
}

.pas-schedule {
    background: #111122;
    border-radius: 8px;
    padding: 16px;
}
.pas-schedule td { padding: 6px 12px; }
</style>
"""

st.markdown(DARK_CSS, unsafe_allow_html=True)


def load_config():
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_customer_manager():
    """Lazy-load customer manager."""
    from core.customer import CustomerManager
    return CustomerManager()


def read_log_file():
    log_dir = Path("logs")
    if not log_dir.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"bot_{today}.log"
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-200:]


# --- Sidebar ---
with st.sidebar:
    st.markdown("## Pokemon ACO")
    st.markdown("*Automated Checkout Service*")
    st.markdown("---")

    config = load_config()
    dry_run = config.get("general", {}).get("dry_run", True)
    mode = "DRY RUN" if dry_run else "LIVE"
    mode_color = "#ffcc00" if dry_run else "#00ff88"
    st.markdown(f"**Mode:** <span style='color:{mode_color};font-weight:700'>{mode}</span>", unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["Dashboard", "Customers", "Orders", "Add Customer", "PAS Billing", "Monitor Log", "Settings"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### Supported Retailers")
    retailer_tags = {
        "Pokemon Center": "retailer-pkc",
        "Target": "retailer-target",
        "Walmart": "retailer-walmart",
        "Amazon": "retailer-amazon",
        "Best Buy": "retailer-bestbuy",
        "TCGPlayer": "retailer-tcgp",
        "eBay": "retailer-ebay",
    }
    for name, cls in retailer_tags.items():
        st.markdown(f"<span class='retailer-tag {cls}'>{name}</span>", unsafe_allow_html=True)


# ==================== PAGES ====================

if page == "Dashboard":
    st.markdown("# Service Dashboard")

    cm = get_customer_manager()
    stats = cm.get_service_stats()

    # Top metrics
    cols = st.columns(6)
    metrics = [
        ("active_customers", "Customers", "#00ff88"),
        ("total_checkouts", "Checkouts", "#00bfff"),
        ("success_rate", "Win Rate", "#ffcc00"),
        ("total_revenue", "Revenue", "#00ff88"),
        ("outstanding_fees", "Outstanding", "#ff4444"),
    ]

    for i, (key, label, color) in enumerate(metrics):
        with cols[i]:
            val = stats.get(key, 0)
            if isinstance(val, float) and key in ("total_revenue", "outstanding_fees"):
                display = f"${val:.2f}"
            elif isinstance(val, float):
                display = f"{val:.1f}%"
            else:
                display = str(val)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{display}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    num_products = sum(1 for p in config.get("products", []) if p.get("enabled", True))
    with cols[5]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#888">{num_products}</div>
            <div class="metric-label">Monitored</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Recent activity
    left, right = st.columns([2, 1])
    with left:
        st.markdown("### Recent Orders")
        orders = []
        for c in cm.list_customers():
            orders.extend(cm.get_customer_orders(c.customer_id))
        orders.sort(key=lambda o: o.created_at, reverse=True)

        if orders:
            for order in orders[:15]:
                status_color = {"success": "#00ff88", "failed": "#ff4444", "pending": "#ffcc00"}.get(order.status, "#888")
                fee_color = {"paid": "#00ff88", "unpaid": "#ffcc00", "overdue": "#ff4444"}.get(order.fee_status, "#888")
                ts = datetime.fromtimestamp(order.created_at).strftime("%m/%d %H:%M")
                st.markdown(f"""
                <div class="order-row">
                    <span style="color:#555">{ts}</span> &nbsp;
                    <span style="color:{status_color};font-weight:700">{order.status.upper()}</span> &nbsp;
                    {order.retailer.upper()} &nbsp;
                    <span style="color:#ccc">{order.product_name[:40]}</span> &nbsp;
                    <span style="color:#00bfff">${order.price:.2f}</span> &nbsp;
                    PAS: <span style="color:{fee_color}">${order.pas_fee:.2f} ({order.fee_status})</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No orders yet. Start the bot to begin processing checkouts.")

    with right:
        st.markdown("### Monitored Products")
        products = config.get("products", [])
        for p in products:
            if p.get("enabled"):
                retailer = p.get("retailer", "unknown")
                max_price = p.get("max_price", 0)
                keywords = ", ".join(p.get("keywords", []))
                st.markdown(
                    f"**{retailer.replace('_', ' ').upper()}** - Max ${max_price:.2f}  \n"
                    f"<small style='color:#666'>{keywords or p.get('url', '')[:50]}</small>",
                    unsafe_allow_html=True,
                )


elif page == "Customers":
    st.markdown("# Customer Management")

    cm = get_customer_manager()
    customers = cm.list_customers()

    if not customers:
        st.info("No customers yet. Use the 'Add Customer' page or run `python bot.py --add-customer`")
    else:
        for c in customers:
            status_cls = f"status-{c.status}"
            st.markdown(f"""
            <div class="customer-card">
                <strong>{c.discord_name}</strong>
                <span class="{status_cls}" style="float:right;font-weight:700">{c.status.upper()}</span><br>
                <small style="color:#666">ID: {c.customer_id} | Discord: {c.discord_id} | Email: {c.email}</small><br>
                <small>Tier: <strong>{c.tier}</strong> | Checkouts: <strong>{c.total_checkouts}</strong> |
                Paid: <span class="fee-paid">${c.total_fees_paid:.2f}</span> |
                Owed: <span class="fee-unpaid">${c.total_fees_owed:.2f}</span></small>
            </div>
            """, unsafe_allow_html=True)


elif page == "Orders":
    st.markdown("# Order History")

    cm = get_customer_manager()

    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status", ["All", "Success", "Failed", "Pending"])
    with col2:
        fee_filter = st.selectbox("Fee Status", ["All", "Paid", "Unpaid", "Overdue"])

    orders = []
    for c in cm.list_customers():
        orders.extend(cm.get_customer_orders(c.customer_id))
    orders.sort(key=lambda o: o.created_at, reverse=True)

    if status_filter != "All":
        orders = [o for o in orders if o.status == status_filter.lower()]
    if fee_filter != "All":
        orders = [o for o in orders if o.fee_status == fee_filter.lower()]

    if orders:
        for order in orders:
            status_color = {"success": "#00ff88", "failed": "#ff4444", "pending": "#ffcc00"}.get(order.status, "#888")
            fee_color = {"paid": "#00ff88", "unpaid": "#ffcc00", "overdue": "#ff4444"}.get(order.fee_status, "#888")
            ts = datetime.fromtimestamp(order.created_at).strftime("%Y-%m-%d %H:%M:%S")
            speed = f"{order.checkout_ms}ms" if order.checkout_ms else "N/A"
            st.markdown(f"""
            <div class="order-row">
                <strong>{order.order_id}</strong> &nbsp;
                <span style="color:{status_color};font-weight:700">{order.status.upper()}</span><br>
                <small style="color:#666">{ts} | {order.retailer.upper()} | Speed: {speed}</small><br>
                <span style="color:#ccc">{order.product_name}</span> &nbsp;
                <span style="color:#00bfff">${order.price:.2f}</span> &nbsp;
                PAS: <span style="color:{fee_color}">${order.pas_fee:.2f} ({order.fee_status})</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No orders match your filters.")


elif page == "Add Customer":
    st.markdown("# Register New Customer")

    with st.form("add_customer"):
        st.markdown("### Customer Info")
        col1, col2 = st.columns(2)
        with col1:
            discord_id = st.text_input("Discord ID")
            discord_name = st.text_input("Discord Name")
        with col2:
            email = st.text_input("Email")
            tier = st.selectbox("Tier", ["standard", "bulk", "vip"])

        st.markdown("---")
        st.markdown("### Checkout Profile")
        st.caption("All data is encrypted at rest and automatically deleted after checkout.")

        retailer = st.selectbox("Retailer", [
            "pokemon_center", "target", "walmart", "amazon", "bestbuy", "tcgplayer", "ebay"
        ])

        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            checkout_email = st.text_input("Checkout Email")
            phone = st.text_input("Phone")
        with col2:
            address1 = st.text_input("Address Line 1")
            address2 = st.text_input("Address Line 2")
            city = st.text_input("City")
            c1, c2 = st.columns(2)
            with c1:
                state = st.text_input("State", max_chars=2)
            with c2:
                zipcode = st.text_input("ZIP Code")

        st.markdown("---")
        st.markdown("### Payment (encrypted)")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            card_number = st.text_input("Card Number", type="password")
        with col2:
            exp_month = st.text_input("Exp Month (MM)")
        with col3:
            exp_year = st.text_input("Exp Year (YYYY)")
        with col4:
            cvv = st.text_input("CVV", type="password")
        cardholder = st.text_input("Cardholder Name")

        submitted = st.form_submit_button("Register Customer", use_container_width=True)

        if submitted and discord_id and discord_name and email:
            cm = get_customer_manager()
            customer = cm.add_customer(discord_id, discord_name, email, tier)

            profile_data = {
                "first_name": first_name, "last_name": last_name,
                "email": checkout_email, "phone": phone,
                "address1": address1, "address2": address2,
                "city": city, "state": state.upper(), "zip": zipcode, "country": "US",
                "card_number": card_number, "exp_month": exp_month,
                "exp_year": exp_year, "cvv": cvv, "cardholder": cardholder,
            }
            cm.store_profile(customer.customer_id, retailer, profile_data)

            st.success(f"Customer registered: {discord_name} (ID: {customer.customer_id})")
            st.info("Profile encrypted and stored. Data will auto-delete after checkout.")


elif page == "PAS Billing":
    st.markdown("# PAS Fee Schedule & Billing")

    st.markdown("### Pay After Success (PAS) Fees")
    st.markdown("Customers are charged only after a successful checkout.")
    st.markdown("""
    <div class="pas-schedule">
    <table style="width:100%">
        <tr style="color:#888"><td><strong>Product Type</strong></td><td><strong>Fee Range</strong></td></tr>
        <tr><td>Tech Sticker / Blister</td><td>$1.50 - $3.00</td></tr>
        <tr><td>Booster Bundle</td><td>$2.00 - $7.00</td></tr>
        <tr><td>Tin</td><td>$2.00 - $5.00</td></tr>
        <tr><td>ETB (Elite Trainer Box)</td><td>$5.00 - $15.00</td></tr>
        <tr><td>Collection Box</td><td>$5.00 - $20.00</td></tr>
        <tr><td>Booster Box</td><td>$10.00 - $25.00</td></tr>
        <tr><td>PC ETB (Pokemon Center Exclusive)</td><td>$15.00 - $40.00</td></tr>
        <tr><td>UPC (Ultra Premium Collection)</td><td>$20.00 - $50.00</td></tr>
    </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Overdue Payments")
    st.caption("Customers have 72 hours to pay after notification. Non-payment results in suspension.")

    cm = get_customer_manager()
    overdue = cm.get_overdue_orders()
    if overdue:
        for order in overdue:
            customer = cm.get_customer(order.customer_id)
            name = customer.discord_name if customer else "Unknown"
            hours_ago = (time.time() - order.completed_at) / 3600
            st.markdown(f"""
            <div class="order-row">
                <span class="fee-overdue">OVERDUE ({hours_ago:.0f}h)</span> &nbsp;
                <strong>{name}</strong> &nbsp; Order: {order.order_id} &nbsp;
                Fee: <strong>${order.pas_fee:.2f}</strong>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("No overdue payments.")

    st.markdown("---")
    st.markdown("### Revenue Summary")
    stats = cm.get_service_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#00ff88">${stats['total_revenue']:.2f}</div>
            <div class="metric-label">Collected</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#ffcc00">${stats['outstanding_fees']:.2f}</div>
            <div class="metric-label">Outstanding</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        total = stats['total_revenue'] + stats['outstanding_fees']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:#00bfff">${total:.2f}</div>
            <div class="metric-label">Total Earned</div>
        </div>
        """, unsafe_allow_html=True)


elif page == "Monitor Log":
    st.markdown("# Live Monitor Log")

    log_lines = read_log_file()
    if log_lines:
        # Filter controls
        filter_text = st.text_input("Filter log", placeholder="Type to filter...")
        if filter_text:
            log_lines = [l for l in log_lines if filter_text.lower() in l.lower()]

        st.markdown(f'<div class="log-box">{"<br>".join(log_lines[-100:])}</div>', unsafe_allow_html=True)
    else:
        st.info("No log entries yet. Start the bot with: `python bot.py`")


elif page == "Settings":
    st.markdown("# Service Settings")

    st.markdown("### General")
    st.json({
        "dry_run": config.get("general", {}).get("dry_run", True),
        "monitor_interval": config.get("general", {}).get("monitor_interval", 3.0),
        "max_concurrent_tasks": config.get("general", {}).get("max_concurrent_tasks", 5),
        "checkout_timeout": config.get("general", {}).get("checkout_timeout", 30),
    })

    st.markdown("### Proxies")
    proxy_config = config.get("proxies", {})
    st.json({
        "enabled": proxy_config.get("enabled", False),
        "rotation": proxy_config.get("rotation", "round_robin"),
        "ban_threshold": proxy_config.get("ban_threshold", 3),
    })

    st.markdown("### Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Start ACO Service", use_container_width=True):
            st.code("python bot.py", language="bash")
    with col2:
        if st.button("Dry Run", use_container_width=True):
            st.code("python bot.py --dry-run", language="bash")
    with col3:
        if st.button("Proxy Health Check", use_container_width=True):
            st.code("python bot.py --health-check", language="bash")
