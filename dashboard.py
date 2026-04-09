"""Pokemon ACO - Customer Website.

Full website experience built on Streamlit. Custom navbar, hero section,
site guides, registration, customer portal, and admin panel.
Based on the Frostaco ACO service template.

Usage: streamlit run dashboard.py --server.port 8891
"""

import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

st.set_page_config(
    page_title="Pokemon ACO - Automated Checkout Service",
    page_icon="pokeball",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS - Full website theme, hide Streamlit chrome
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');

/* Hide Streamlit defaults */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}
[data-testid="collapsedControl"] {display: none;}
.stDeployButton {display: none;}

.stApp {
    background-color: #0a0a12;
    color: #e8e8e8;
    font-family: 'Inter', sans-serif;
}

/* Remove top padding */
.block-container {
    padding-top: 0 !important;
    max-width: 1200px;
}

h1 { font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -0.5px; }
h2 { font-weight: 700; color: #ddd; }
h3 { font-weight: 600; }

/* ---------- NAVBAR ---------- */
.navbar {
    background: rgba(10, 10, 18, 0.95);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid #1a1a2e;
    padding: 12px 0;
    margin: -1rem -1rem 2rem -1rem;
    position: sticky;
    top: 0;
    z-index: 999;
}
.navbar-inner {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
}
.navbar-brand {
    font-size: 1.3rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.5px;
}
.navbar-brand span { color: #ffcc00; }
.nav-links { display: flex; gap: 8px; align-items: center; }
.nav-link {
    color: #999;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 6px 14px;
    border-radius: 8px;
    transition: all 0.2s;
    cursor: pointer;
}
.nav-link:hover { color: #fff; background: #1a1a2e; }
.nav-link.active { color: #ffcc00; background: #1a1a10; }
.nav-btn {
    background: #ffcc00;
    color: #000;
    font-weight: 700;
    font-size: 0.8rem;
    padding: 7px 18px;
    border-radius: 8px;
    text-decoration: none;
    margin-left: 8px;
}
.nav-user {
    color: #ffcc00;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 12px;
}

/* ---------- HERO ---------- */
.hero {
    background: linear-gradient(135deg, #0f0f20 0%, #1a0a2e 50%, #0a1628 100%);
    border: 1px solid #1e1e3a;
    border-radius: 20px;
    padding: 60px 48px;
    text-align: center;
    margin-bottom: 40px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 30% 40%, rgba(255,204,0,0.04) 0%, transparent 50%),
                radial-gradient(circle at 70% 60%, rgba(64,196,255,0.04) 0%, transparent 50%);
}
.hero h1 {
    font-size: 3rem;
    font-weight: 800;
    margin-bottom: 12px;
    position: relative;
}
.hero h1 span { color: #ffcc00; }
.hero-sub {
    font-size: 1.15rem;
    color: #999;
    margin-bottom: 32px;
    position: relative;
}
.hero-cta {
    display: inline-block;
    background: #ffcc00;
    color: #000;
    font-weight: 700;
    font-size: 1rem;
    padding: 12px 32px;
    border-radius: 10px;
    text-decoration: none;
    position: relative;
    margin: 0 6px;
}
.hero-cta-outline {
    display: inline-block;
    background: transparent;
    color: #ffcc00;
    font-weight: 600;
    font-size: 1rem;
    padding: 11px 30px;
    border-radius: 10px;
    border: 2px solid #ffcc00;
    text-decoration: none;
    position: relative;
    margin: 0 6px;
}

/* ---------- CARDS ---------- */
.card {
    background: #12122a;
    border: 1px solid #1e1e3a;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    transition: border-color 0.2s;
}
.card:hover { border-color: #2a2a5a; }

.feature-card {
    background: linear-gradient(180deg, #14142a, #0f0f1e);
    border: 1px solid #1e1e3a;
    border-radius: 16px;
    padding: 28px 24px;
    text-align: center;
    min-height: 160px;
}
.feature-icon {
    font-size: 2rem;
    margin-bottom: 12px;
    display: block;
}

.stat-box {
    background: linear-gradient(135deg, #14142a, #1a1a36);
    border: 1px solid #2a2a4a;
    border-radius: 14px;
    padding: 24px;
    text-align: center;
}
.stat-val {
    font-size: 2.2rem;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
}
.stat-lbl {
    font-size: 0.7rem;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 6px;
}

.order-item {
    background: #0f0f1e;
    border: 1px solid #1a1a33;
    border-radius: 12px;
    padding: 16px 20px;
    margin: 8px 0;
}

/* ---------- COLORS ---------- */
.green { color: #00e676; }
.yellow { color: #ffd740; }
.red { color: #ff5252; }
.blue { color: #40c4ff; }
.purple { color: #b388ff; }
.dim { color: #666; }
.mono { font-family: 'JetBrains Mono', monospace; }

/* ---------- BOXES ---------- */
.info-box {
    background: #0a1628;
    border: 1px solid #1a3050;
    border-left: 4px solid #40c4ff;
    border-radius: 0 12px 12px 0;
    padding: 20px 24px;
    font-size: 0.92rem;
    line-height: 1.7;
    color: #ccc;
    margin: 20px 0;
}
.warn-box {
    background: #1a1500;
    border: 1px solid #4a3800;
    border-left: 4px solid #ffd740;
    border-radius: 0 12px 12px 0;
    padding: 20px 24px;
    font-size: 0.88rem;
    line-height: 1.6;
    color: #ccc;
    margin: 20px 0;
}
.danger-box {
    background: #1a0505;
    border: 1px solid #4a1515;
    border-left: 4px solid #ff5252;
    border-radius: 0 12px 12px 0;
    padding: 20px 24px;
    font-size: 0.88rem;
    line-height: 1.6;
    color: #ccc;
    margin: 20px 0;
}
.danger-zone {
    background: #1a0505;
    border: 1px solid #4a1515;
    border-radius: 16px;
    padding: 24px;
    margin-top: 24px;
}

/* ---------- STEPS ---------- */
.step-box {
    background: #12122a;
    border: 1px solid #1e1e3a;
    border-radius: 14px;
    padding: 20px 24px;
    margin: 10px 0;
}
.step-num {
    display: inline-block;
    background: linear-gradient(135deg, #ffcc00, #ff9900);
    color: #000;
    font-weight: 800;
    width: 30px;
    height: 30px;
    line-height: 30px;
    text-align: center;
    border-radius: 50%;
    margin-right: 12px;
    font-size: 0.85rem;
}

/* ---------- RETAILER BADGES ---------- */
.retailer-badge {
    display: inline-block;
    padding: 6px 18px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 700;
    margin-right: 8px;
    margin-bottom: 10px;
}

/* ---------- FOOTER ---------- */
.footer {
    border-top: 1px solid #1a1a2e;
    margin-top: 60px;
    padding: 30px 0 20px 0;
    text-align: center;
    color: #444;
    font-size: 0.8rem;
}
.footer a { color: #666; text-decoration: none; }
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


# Session state
for k in ["customer_id", "session_token", "username"]:
    if k not in st.session_state:
        st.session_state[k] = ""

if "page" not in st.session_state:
    st.session_state["page"] = "Home"


def nav_to(p):
    st.session_state["page"] = p


# ---------------------------------------------------------------------------
# NAVBAR (HTML)
# ---------------------------------------------------------------------------
def render_navbar():
    user_section = ""
    if is_logged_in():
        user_section = f'<span class="nav-user">{st.session_state["username"]}</span>'
    else:
        user_section = ''

    st.markdown(f"""
    <div class="navbar">
        <div class="navbar-inner">
            <div class="navbar-brand">Poke<span>ACO</span></div>
            <div style="display:flex;align-items:center">
                {user_section}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


render_navbar()

# Navigation via Streamlit buttons (since HTML links can't trigger Streamlit)
if is_logged_in():
    nav_cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    pages = ["Home", "How We Operate", "Site Guides", "PAS Fees", "FAQ", "Terms",
             "My Orders", "My Profile", "My Data", "API Keys", "Admin"]
    # Split into two rows if needed
    nav_cols = st.columns(len(pages))
    for i, p in enumerate(pages):
        with nav_cols[i]:
            if st.button(p, key=f"nav_{p}", use_container_width=True,
                         type="primary" if st.session_state["page"] == p else "secondary"):
                nav_to(p)
                st.rerun()

    # Logout button
    logout_cols = st.columns([10, 1])
    with logout_cols[1]:
        if st.button("Logout", key="nav_logout"):
            do_logout()
            st.rerun()
else:
    pages = ["Home", "How We Operate", "Site Guides", "PAS Fees", "FAQ", "Terms",
             "Login", "Register", "Admin"]
    nav_cols = st.columns(len(pages))
    for i, p in enumerate(pages):
        with nav_cols[i]:
            btn_type = "primary" if st.session_state["page"] == p else "secondary"
            if st.button(p, key=f"nav_{p}", use_container_width=True, type=btn_type):
                nav_to(p)
                st.rerun()

st.markdown("")  # spacing

page = st.session_state["page"]


# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------
def render_footer():
    st.markdown(f"""
    <div class="footer">
        Pokemon ACO &middot; Automated Checkout Service &middot; {datetime.now().year}<br>
        <span style="color:#333">All customer data AES-256 encrypted at rest.
        Cards charged by retailers, not by us.</span>
    </div>
    """, unsafe_allow_html=True)


# ========================================================================
# HOME
# ========================================================================
if page == "Home":
    # Hero
    st.markdown("""
    <div class="hero">
        <h1>Pokemon <span>ACO</span></h1>
        <p class="hero-sub">
            Automated checkout for high-demand Pokemon TCG products.<br>
            We monitor. We checkout. You pay only after success.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    c1, c2, c3, c4 = st.columns(4)
    features = [
        ("24/7 Monitoring", "All major retailers + Discord restock channels monitored around the clock.", "blue"),
        ("Instant Checkout", "Sub-second checkout when products restock. Selenium + stealth fingerprinting.", "green"),
        ("7 Retailers", "Pokemon Center, Target, Walmart, Amazon, Best Buy, TCGPlayer, eBay.", "yellow"),
        ("Pay After Success", "No upfront cost. You only pay a small PAS fee after we secure your product.", "purple"),
    ]
    for col, (title, desc, color) in zip([c1, c2, c3, c4], features):
        with col:
            st.markdown(f"""
            <div class="feature-card">
                <strong style="font-size:1.05rem" class="{color}">{title}</strong><br><br>
                <span class="dim" style="font-size:0.85rem">{desc}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # How it works
    st.markdown("## How It Works")
    steps = [
        ("Register", "Create your account, choose retailers, and submit your encrypted checkout profile."),
        ("We Monitor", "Our bot watches all major retailers and Discord channels 24/7 for Pokemon TCG drops."),
        ("Auto Checkout", "When a product restocks, we checkout at maximum speed using your stored profile."),
        ("Pay After Success", "You only pay a small PAS fee after a successful checkout. Payment via Stripe."),
    ]
    for i, (title, desc) in enumerate(steps):
        st.markdown(f"""
        <div class="step-box">
            <span class="step-num">{i + 1}</span>
            <strong>{title}</strong><br>
            <span class="dim" style="margin-left:42px;display:block;margin-top:4px">{desc}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # Disclaimer
    st.markdown(f"""
    <div class="warn-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # Retailers
    st.markdown("## Supported Retailers")
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
        tags += f"<span class='retailer-badge' style='background:{bg};color:{fg}'>{name}</span>"
    st.markdown(tags, unsafe_allow_html=True)

    st.markdown("")

    # Tiers
    st.markdown("## Service Tiers")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("""
        <div class="card">
            <strong style="font-size:1.15rem">Standard ACO</strong><br><br>
            <span class="dim">Regular per-submission pricing. Submit your profiles for
            upcoming releases and restocks at standard PAS fees.</span>
        </div>
        """, unsafe_allow_html=True)
    with t2:
        st.markdown("""
        <div class="card">
            <strong style="font-size:1.15rem;color:#ffcc00">Bulk ACO</strong><br><br>
            <span class="dim">15+ profiles. Higher volume, lower cost.
            <strong>20% discount</strong> on all PAS fees.</span>
        </div>
        """, unsafe_allow_html=True)

    # Quick fee table
    st.markdown("")
    st.markdown("## PAS Fees at a Glance")
    fee_data = {
        "Product": ["Blister", "Booster Bundle", "Tin", "ETB", "Collection Box", "Booster Box", "PC ETB", "UPC"],
        "Fee": ["$1.50-$3", "$2-$7", "$2-$5", "$5-$15", "$5-$20", "$10-$25", "$15-$40", "$20-$50"],
    }
    st.table(fee_data)

    render_footer()


# ========================================================================
# HOW WE OPERATE
# ========================================================================
elif page == "How We Operate":
    st.markdown("# How We Operate")

    st.markdown("""
    <div class="info-box">
        <strong>ACO</strong> = <strong>Automated Checkout</strong> -- bot software that
        automatically completes purchases for high-demand Pokemon TCG items from online
        retailers that typically sell out within seconds.<br><br>
        This is a <strong>paid service</strong>. Success is not guaranteed, but your odds
        of securing products are greatly improved with ACO.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### What Information We Need")
    st.markdown("""
    - **Login credentials** for retailer websites (where applicable)
    - **Payment method** -- credit or debit card
    - **Shipping and billing address**
    - **Name, phone number, and email**
    """)

    st.markdown("""
    <div class="warn-box">
        <strong>Data Security:</strong> All information is <strong>AES-256 encrypted at rest</strong>.
        You may request deletion at any time. Your card is charged by the <strong>retailer</strong>, never by us.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### Payment Model (PAS)")
    st.markdown("""
    - Payment due **within 24 hours** of successful checkout notification
    - Full payment within **72 hours** or account suspension
    - **Stripe only** for PAS fee payment
    - The only fee we charge is the PAS service fee
    """)

    st.markdown("---")

    st.markdown("### What to Expect")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="card">
            <strong class="blue">Before a Release</strong><br><br>
            <span class="dim">Submit profiles via Register or My Profile.
            Set up retailer accounts per Site Guides.
            Jig profiles if submitting multiples.</span>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="card">
            <strong class="green">During a Release</strong><br><br>
            <span class="dim">Bot detects restock and begins checkout immediately.
            Discord notification sent on success or failure.</span>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="card">
            <strong class="yellow">After a Release</strong><br><br>
            <span class="dim">Success: pay PAS fee within 72h via Stripe.
            Failure: no charge, we try again next drop.</span>
        </div>
        """, unsafe_allow_html=True)

    render_footer()


# ========================================================================
# SITE GUIDES
# ========================================================================
elif page == "Site Guides":
    st.markdown("# Site Guides")
    st.markdown("Retailer-specific requirements and setup instructions.")
    st.markdown("---")

    guides = [
        ("Pokemon Center", "#ffcc00", "#000", """
            <strong>Account:</strong> No account required -- guest checkout used.<br><br>
            <strong>Jigging:</strong> <span class="yellow">REQUIRED</span> for multiple profiles.<br><br>
            <strong>PAS:</strong> PC ETB / Bundle PAS will vary. Other items TBD.
        """),
        ("Target", "#cc0000", "#fff", """
            <strong>Account:</strong> Can be newly created. Aged accounts with order history preferred.<br><br>
            <strong>Jigging:</strong> <span class="yellow">REQUIRED</span> for multiple accounts.
        """),
        ("Walmart", "#0071ce", "#fff", """
            <strong>Account:</strong> <span class="yellow">Required.</span><br><br>
            <strong>Jigging:</strong> <span class="yellow">REQUIRED</span> for multiple accounts.<br><br>
            <strong>New accounts:</strong> Allowed but higher cancellation rates.
        """),
        ("Amazon", "#ff9900", "#000", """
            <strong>Account:</strong> <span class="red">Must be VERIFIED.</span><br><br>
            <strong>Required setup (all 4):</strong><br>
            1. Enable <strong>2FA</strong><br>
            2. Set <strong>default payment + shipping</strong><br>
            3. Have <strong>Amazon Prime</strong><br>
            4. Turn ON <strong>1-Click checkout</strong>
        """),
        ("Best Buy", "#0046be", "#fff", """
            <strong>Account:</strong> Required with payment info on file.<br><br>
            <strong>Queue:</strong> Bot handles waiting rooms automatically.
        """),
        ("TCGPlayer", "#6b21a8", "#fff", """
            <strong>Account:</strong> Recommended for faster checkout.<br><br>
            <strong>Features:</strong> Seller rating filtering, price optimization, cart bundling.
        """),
        ("eBay", "#e53238", "#fff", """
            <strong>Account:</strong> Required with payment on file.<br><br>
            <strong>Features:</strong> BIN sniping, keyword search, seller feedback filtering (98%+).
        """),
    ]

    for name, bg, fg, content in guides:
        st.markdown(f"""
        <div class="card">
            <span class="retailer-badge" style="background:{bg};color:{fg}">{name}</span><br><br>
            {content}
        </div>
        """, unsafe_allow_html=True)

    render_footer()


# ========================================================================
# PAS FEES
# ========================================================================
elif page == "PAS Fees":
    st.markdown("# PAS Fee Schedule")

    st.markdown("""
    <div class="info-box">
        <strong>PAS</strong> = Pay After Success. The only fee we charge.
        Your card is charged by the <strong>retailer</strong> for the product.
        Our PAS fee is billed separately via <strong>Stripe</strong>.
    </div>
    """, unsafe_allow_html=True)

    fee_data = {
        "Product Type": [
            "Tech Sticker / Blister", "Booster Bundle", "Tin",
            "ETB (Elite Trainer Box)", "Collection Box", "Booster Box",
            "PC ETB (Pokemon Center Exclusive)", "UPC (Ultra Premium Collection)",
        ],
        "Fee Range": [
            "$1.50 - $3.00", "$2.00 - $7.00", "$2.00 - $5.00",
            "$5.00 - $15.00", "$5.00 - $20.00", "$10.00 - $25.00",
            "$15.00 - $40.00", "$20.00 - $50.00",
        ],
    }
    st.table(fee_data)

    st.markdown("""
    <div class="info-box">
        <strong>Bulk discount:</strong> 15+ profiles = <strong>20% off</strong> all PAS fees.<br>
        <strong>PAS marked TBD</strong> will always be fair.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### How to Pay")
    steps = [
        "Receive notification with Retailer, Product, Quantity, and Total Due",
        "Stripe payment link is sent to you",
        "Complete payment within 72 hours",
        "Confirm payment and wait for your next hit",
    ]
    for i, s in enumerate(steps):
        st.markdown(f"""
        <div class="step-box">
            <span class="step-num">{i+1}</span> {s}
        </div>
        """, unsafe_allow_html=True)

    render_footer()


# ========================================================================
# FAQ
# ========================================================================
elif page == "FAQ":
    st.markdown("# Frequently Asked Questions")
    st.markdown("")

    faqs = [
        ("Why do you need my personal information?",
         "We need it to check out items on your behalf. All data is AES-256 encrypted and can be deleted anytime."),
        ("Why was my order canceled?",
         "Possible reasons: info flagged by retailer, card declined, profiles not jigged correctly, "
         "same info used with multiple providers, or product went out of stock."),
        ("What is jigging?",
         "Creating slight variations of your profile (address, name, phone) so each looks unique to the retailer. "
         "Required for multiple profiles to avoid cancellation."),
        ("How quickly do I need to pay PAS?",
         "Within 72 hours via Stripe. Failure to pay may result in account suspension."),
        ("Is success guaranteed?",
         "No. But ACO significantly improves your odds. You only pay if we succeed."),
        ("Can I use new retailer accounts?",
         "For most retailers, yes. Amazon requires verified accounts with order history, Prime, and 2FA."),
        ("How do I delete my data?",
         "Log in > My Data page. Delete individual profiles or everything. Order history retained for billing only."),
        ("What retailers are supported?",
         "Pokemon Center, Target, Walmart, Amazon, Best Buy, TCGPlayer, and eBay."),
    ]
    for q, a in faqs:
        with st.expander(q):
            st.markdown(a, unsafe_allow_html=True)

    render_footer()


# ========================================================================
# TERMS
# ========================================================================
elif page == "Terms":
    st.markdown("# Terms of Service")

    st.markdown("""
    <div class="danger-box">
        <strong>If you do not accept these terms, do not sign up.</strong>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    By using Pokemon ACO, you acknowledge and agree to:

    **1. Service Description** -- ACO is a digital, non-tangible service. You authorize us to
    process your information to complete automated checkouts.

    **2. Fees** -- The sole cost is the PAS fee, billed via Stripe. Your card is charged by the
    retailer for products.

    **3. Payment Terms** -- PAS fees due within 72 hours. Failure to pay may result in suspension.

    **4. Data Handling** -- All data AES-256 encrypted. Deletable anytime via My Data or contact.

    **5. No Guarantee** -- Success is not guaranteed. ACO improves odds but cannot guarantee every checkout.

    **6. Liability** -- Pokemon ACO is not responsible for unwanted or unauthorized charges.

    **7. Misuse** -- False info, payment circumvention, or sharing access may result in bans and fees.
    """)

    render_footer()


# ========================================================================
# LOGIN
# ========================================================================
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
                    st.session_state["page"] = "My Orders"
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    render_footer()


# ========================================================================
# REGISTER
# ========================================================================
elif page == "Register":
    st.markdown("# Register")
    st.markdown("Create your account and submit your first checkout profile.")

    st.markdown(f"""
    <div class="warn-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    with st.form("register"):
        st.markdown("### Account")
        ac1, ac2 = st.columns(2)
        with ac1:
            reg_username = st.text_input("Username (min 3 chars)")
            reg_password = st.text_input("Password (min 8 chars)", type="password")
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
        st.caption("See Site Guides for retailer requirements before submitting.")

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

        st.markdown("---")
        st.markdown("### Retailer Login")
        st.caption("Required for Target, Walmart, Amazon, Best Buy, TCGPlayer, eBay. Not needed for Pokemon Center.")
        rl1, rl2 = st.columns(2)
        with rl1:
            retailer_email = st.text_input("Retailer Account Email")
        with rl2:
            retailer_password = st.text_input("Retailer Account Password", type="password")

        st.markdown("---")
        st.markdown("### Data Preference")
        retention = st.radio("After a successful checkout:", ["keep", "delete_after_checkout"],
                             format_func=lambda x: {
                                 "keep": "Keep my profile for future checkouts",
                                 "delete_after_checkout": "Delete my profile after each checkout"}[x])

        agreed = st.checkbox("I agree to the Card Charge Disclaimer and Terms of Service")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            if not agreed:
                st.error("You must agree to the disclaimer and terms.")
            elif not reg_username or len(reg_username) < 3:
                st.error("Username must be at least 3 characters.")
            elif not reg_password or len(reg_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif reg_password != reg_password2:
                st.error("Passwords do not match.")
            elif not discord_id or not discord_name or not email:
                st.error("Fill in Discord ID, username, and email.")
            else:
                cm = get_cm()
                auth = get_auth()

                if not auth.register("__temp__", reg_username, reg_password):
                    st.error("Username already taken.")
                else:
                    auth.db.execute("DELETE FROM auth_credentials WHERE customer_id = '__temp__'")
                    auth.db.commit()

                    customer = cm.add_customer(discord_id, discord_name, email, tier, retention)
                    auth.register(customer.customer_id, reg_username, reg_password)

                    profile_data = {
                        "first_name": first_name, "last_name": last_name,
                        "email": checkout_email, "phone": phone,
                        "address1": address1, "address2": address2,
                        "city": city, "state": state.upper(), "zip": zipcode, "country": "US",
                        "card_number": card_number, "exp_month": exp_month,
                        "exp_year": exp_year, "cvv": cvv, "cardholder": cardholder,
                        "retailer_email": retailer_email, "retailer_password": retailer_password,
                    }
                    cm.store_profile(customer.customer_id, retailer, profile_data)

                    session = auth.login(reg_username, reg_password)
                    if session:
                        st.session_state["customer_id"] = session.customer_id
                        st.session_state["session_token"] = session.token
                        st.session_state["username"] = reg_username

                    st.success(f"Account created! Logged in as **{reg_username}** (ID: {customer.customer_id})")
                    time.sleep(1)
                    st.session_state["page"] = "My Orders"
                    st.rerun()

    render_footer()


# ========================================================================
# MY ORDERS
# ========================================================================
elif page == "My Orders":
    if not is_logged_in():
        st.warning("Please log in to view your orders.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    customer = cm.get_customer(cid)

    if not customer:
        st.error("Customer not found.")
        st.stop()

    st.markdown(f"# Welcome back, {customer.discord_name}")

    c1, c2, c3 = st.columns(3)
    metrics = [
        (customer.total_checkouts, "Checkouts", "green"),
        (f"${customer.total_fees_paid:.2f}", "Fees Paid", "blue"),
        (f"${customer.total_fees_owed:.2f}", "Balance Due", "yellow"),
    ]
    for col, (val, label, color) in zip([c1, c2, c3], metrics):
        with col:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val {color}">{val}</div>
                <div class="stat-lbl">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    orders = cm.get_customer_orders(cid)
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
                <span class="dim" style="margin-left:12px">PAS:</span>
                <span class="{fc}">${o.pas_fee:.2f} ({o.fee_status})</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No orders yet. We'll check out products for you as soon as they drop!")

    render_footer()


# ========================================================================
# MY PROFILE
# ========================================================================
elif page == "My Profile":
    if not is_logged_in():
        st.warning("Please log in.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    auth = get_auth()
    customer = cm.get_customer(cid)

    if not customer:
        st.error("Customer not found.")
        st.stop()

    username = auth.get_username(cid)

    st.markdown("# My Profile")

    st.markdown(f"""
    <div class="card">
        <strong style="font-size:1.2rem">{customer.discord_name}</strong><br>
        <span class="dim">Username: <span class="mono">{username}</span></span> &middot;
        <span class="dim">ID: <span class="mono">{customer.customer_id}</span></span> &middot;
        <span class="dim">Tier: <strong>{customer.tier}</strong></span> &middot;
        <span class="green">{customer.status.upper()}</span>
    </div>
    """, unsafe_allow_html=True)

    profiles = cm.get_profile_summary(cid)
    active = [p for p in profiles if not p["purged"]]

    st.markdown("### Stored Profiles")
    if active:
        for p in active:
            ts = datetime.fromtimestamp(p["created_at"]).strftime("%b %d, %Y")
            st.markdown(f"""
            <div class="card" style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <strong>{p['retailer'].replace('_',' ').title()}</strong><br>
                    <span class="dim">Added: {ts}</span>
                </div>
                <span class="green">Active</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No active profiles. Add one below.")

    st.markdown("---")
    st.markdown("### Add Profile")

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
            address2 = st.text_input("Address Line 2")
            city = st.text_input("City")
            sc1, sc2 = st.columns(2)
            with sc1:
                sv = st.text_input("State", max_chars=2)
            with sc2:
                zv = st.text_input("ZIP")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            cn = st.text_input("Card Number", type="password")
        with c2:
            em = st.text_input("MM")
        with c3:
            ey = st.text_input("YYYY")
        with c4:
            cv = st.text_input("CVV", type="password")
        ch = st.text_input("Name on Card")

        rl1, rl2 = st.columns(2)
        with rl1:
            re = st.text_input("Retailer Email")
        with rl2:
            rp = st.text_input("Retailer Password", type="password")

        if st.form_submit_button("Add Profile", use_container_width=True):
            pd = {
                "first_name": first_name, "last_name": last_name,
                "email": checkout_email, "phone": phone,
                "address1": address1, "address2": address2,
                "city": city, "state": sv.upper(), "zip": zv, "country": "US",
                "card_number": cn, "exp_month": em, "exp_year": ey, "cvv": cv, "cardholder": ch,
                "retailer_email": re, "retailer_password": rp,
            }
            cm.store_profile(cid, retailer, pd)
            st.success(f"**{retailer.replace('_',' ').title()}** profile added.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Change Password")
    with st.form("change_pw"):
        old_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        new_pw2 = st.text_input("Confirm", type="password")
        if st.form_submit_button("Change Password"):
            if new_pw != new_pw2:
                st.error("Passwords don't match.")
            elif len(new_pw) < 8:
                st.error("Min 8 characters.")
            else:
                if auth.change_password(cid, old_pw, new_pw):
                    do_logout()
                    st.success("Password changed. Log in again.")
                    st.session_state["page"] = "Login"
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Current password incorrect.")

    render_footer()


# ========================================================================
# MY DATA
# ========================================================================
elif page == "My Data":
    if not is_logged_in():
        st.warning("Please log in.")
        st.stop()

    cid = current_customer_id()
    cm = get_cm()
    customer = cm.get_customer(cid)

    if not customer:
        st.error("Customer not found.")
        st.stop()

    st.markdown("# My Data")

    st.markdown(f"""
    <div class="warn-box">
        <strong>Card Charge Disclaimer</strong><br><br>
        {get_disclaimer()}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Data Retention")
    options = {"keep": "Keep data for future checkouts", "delete_after_checkout": "Delete after each checkout"}
    choice = st.radio("Preference", list(options.keys()),
                      format_func=lambda x: options[x],
                      index=0 if customer.data_retention == "keep" else 1)
    if st.button("Save Preference"):
        cm.update_data_retention(cid, choice)
        st.success(f"Updated: **{options[choice]}**")

    st.markdown("---")
    st.markdown("### Delete Profile")
    profiles = cm.get_profile_summary(cid)
    active = [p for p in profiles if not p["purged"]]
    if active:
        rd = st.selectbox("Retailer", [p["retailer"] for p in active],
                          format_func=lambda x: x.replace("_", " ").title())
        if st.button("Delete This Profile"):
            cm.delete_single_profile(cid, rd)
            st.success(f"**{rd.replace('_',' ').title()}** deleted.")
            st.rerun()
    else:
        st.info("No active profiles.")

    st.markdown("""
    <div class="danger-zone">
        <strong style="color:#ff5252">Delete All Data</strong><br>
        <span class="dim">Permanently deletes all profiles. Order history kept for billing.</span>
    </div>
    """, unsafe_allow_html=True)
    if st.checkbox("I understand this is permanent"):
        if st.button("Delete All My Data", type="primary"):
            cm.delete_customer_data(cid)
            st.success("All profile data deleted.")
            st.rerun()

    render_footer()


# ========================================================================
# API KEYS
# ========================================================================
elif page == "API Keys":
    if not is_logged_in():
        st.warning("Please log in.")
        st.stop()

    cid = current_customer_id()
    auth = get_auth()

    st.markdown("# API Keys")

    with st.form("create_key"):
        kn = st.text_input("Key Name", value="default")
        if st.form_submit_button("Generate API Key"):
            key = auth.create_api_key(cid, kn)
            st.success("Copy this key now -- it won't be shown again.")
            st.code(key, language="text")

    st.markdown("---")
    keys = auth.list_api_keys(cid)
    if keys:
        for k in keys:
            sc = "green" if k["active"] else "red"
            status = "Active" if k["active"] else "Revoked"
            created = datetime.fromtimestamp(k["created_at"]).strftime("%b %d, %Y")
            st.markdown(f"""
            <div class="card" style="padding:14px 18px">
                <strong>{k['name']}</strong>
                <span class="{sc}" style="float:right;font-weight:700">{status}</span><br>
                <span class="dim mono" style="font-size:0.8rem">{k['api_key']}</span><br>
                <span class="dim">Created: {created}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.code('curl -H "Authorization: ApiKey paco_YOUR_KEY" http://localhost:8080/api/me', language="bash")

    render_footer()


# ========================================================================
# ADMIN
# ========================================================================
elif page == "Admin":
    st.markdown("# Admin Panel")
    admin_pw = st.text_input("Admin password", type="password")
    if admin_pw != "admin":
        st.warning("Enter admin password.")
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
    for col, (val, label, color) in zip(cols, admin_metrics):
        with col:
            st.markdown(f"""
            <div class="stat-box">
                <div class="stat-val {color}">{val}</div>
                <div class="stat-lbl">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Customers")
    for c in cm.list_customers():
        sc = {"active": "green", "suspended": "yellow", "banned": "red"}.get(c.status, "dim")
        st.markdown(f"""
        <div class="card" style="padding:12px 18px">
            <strong>{c.discord_name}</strong>
            <span class="{sc}" style="float:right;font-weight:700">{c.status.upper()}</span><br>
            <span class="dim mono" style="font-size:0.8rem">
                {c.customer_id} | {c.tier} | {c.total_checkouts} checkouts |
                paid ${c.total_fees_paid:.2f} | owed ${c.total_fees_owed:.2f}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Overdue")
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
                <span class="yellow" style="margin-left:12px">${o.pas_fee:.2f}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("No overdue payments.")

    st.markdown("---")
    st.markdown("### Logs")
    log_lines = read_log_file()
    if log_lines:
        filt = st.text_input("Filter")
        if filt:
            log_lines = [l for l in log_lines if filt.lower() in l.lower()]
        st.code("\n".join(log_lines[-60:]), language="log")

    render_footer()
