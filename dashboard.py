"""Streamlit real-time dashboard for Pokemon Scalping Bot.

Shows live monitoring status, checkout stats, price history,
and profile management.

Usage: streamlit run dashboard.py --server.port 8891
"""

import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

st.set_page_config(
    page_title="Pokemon Scalp Bot",
    page_icon="pokeball",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&display=swap');

.stApp {
    background-color: #0a0a0a;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', monospace;
}

.metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #0f3460;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}

.metric-value {
    font-size: 2.5rem;
    font-weight: 700;
    color: #00ff88;
}

.metric-label {
    font-size: 0.85rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 2px;
}

.success-badge {
    background: #00ff88;
    color: #000;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.8rem;
}

.fail-badge {
    background: #ff4444;
    color: #fff;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.8rem;
}

.retailer-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
}

.retailer-pkc { background: #ffcc00; color: #000; }
.retailer-target { background: #cc0000; color: #fff; }
.retailer-walmart { background: #0071ce; color: #fff; }
.retailer-amazon { background: #ff9900; color: #000; }
.retailer-bestbuy { background: #0046be; color: #fff; }
.retailer-tcgp { background: #6b21a8; color: #fff; }
.retailer-ebay { background: #e53238; color: #fff; }

.log-entry {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    padding: 4px 0;
    border-bottom: 1px solid #1a1a2e;
}

.stock-alert {
    background: #001a00;
    border-left: 4px solid #00ff88;
    padding: 12px;
    margin: 8px 0;
    border-radius: 0 8px 8px 0;
}
</style>
"""

st.markdown(DARK_CSS, unsafe_allow_html=True)


def load_config():
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def read_log_file():
    """Read the most recent log file."""
    log_dir = Path("logs")
    if not log_dir.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"bot_{today}.log"
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-100:]  # Last 100 lines


# --- Sidebar ---
with st.sidebar:
    st.markdown("## Pokemon Scalp Bot")
    st.markdown("---")

    config = load_config()
    dry_run = config.get("general", {}).get("dry_run", True)
    mode = "DRY RUN" if dry_run else "LIVE"
    mode_color = "#ffcc00" if dry_run else "#00ff88"
    st.markdown(f"**Mode:** <span style='color:{mode_color}'>{mode}</span>", unsafe_allow_html=True)

    num_profiles = len(config.get("profiles", []))
    num_products = sum(1 for p in config.get("products", []) if p.get("enabled", True))
    st.markdown(f"**Profiles:** {num_profiles}")
    st.markdown(f"**Products:** {num_products}")

    st.markdown("---")
    st.markdown("### Retailers")
    retailers = {
        "Pokemon Center": ("#ffcc00", "#000"),
        "Target": ("#cc0000", "#fff"),
        "Walmart": ("#0071ce", "#fff"),
        "Amazon": ("#ff9900", "#000"),
        "Best Buy": ("#0046be", "#fff"),
        "TCGPlayer": ("#6b21a8", "#fff"),
        "eBay": ("#e53238", "#fff"),
    }
    for name, (bg, fg) in retailers.items():
        st.markdown(
            f"<span style='background:{bg};color:{fg};padding:2px 8px;"
            f"border-radius:4px;font-size:0.75rem;font-weight:700'>{name}</span>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    auto_refresh = st.checkbox("Auto-refresh (5s)", value=True)
    if auto_refresh:
        st.markdown("<meta http-equiv='refresh' content='5'>", unsafe_allow_html=True)


# --- Main Content ---
st.markdown("# Dashboard")

# Metrics row
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-value">0</div>
        <div class="metric-label">Checkouts</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-value" style="color:#ff4444">0</div>
        <div class="metric-label">Failed</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-value" style="color:#ffcc00">$0.00</div>
        <div class="metric-label">Total Spent</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-value" style="color:#00bfff">0ms</div>
        <div class="metric-label">Avg Speed</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-value" style="color:#00ff88">0ms</div>
        <div class="metric-label">Fastest</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Two column layout
left_col, right_col = st.columns([2, 1])

with left_col:
    st.markdown("### Live Monitor Log")
    log_lines = read_log_file()
    if log_lines:
        log_text = "\n".join(log_lines[-50:])
        st.code(log_text, language="log")
    else:
        st.info("No log entries yet. Start the bot with: python bot.py")

with right_col:
    st.markdown("### Stock Alerts")
    st.markdown("""
    <div style="text-align:center;padding:40px;color:#555">
        Waiting for stock alerts...
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Monitored Products")
    products = config.get("products", [])
    for p in products:
        if p.get("enabled"):
            retailer = p.get("retailer", "unknown")
            max_price = p.get("max_price", 0)
            keywords = ", ".join(p.get("keywords", []))
            st.markdown(
                f"**{retailer.upper()}** - Max ${max_price:.2f}  \n"
                f"<small>{keywords or p.get('url', '')[:50]}</small>",
                unsafe_allow_html=True,
            )

st.markdown("---")
st.markdown("### Quick Actions")
action_cols = st.columns(4)

with action_cols[0]:
    if st.button("Start Bot", use_container_width=True):
        st.info("Run `python bot.py` in terminal")

with action_cols[1]:
    if st.button("Monitor Only", use_container_width=True):
        st.info("Run `python bot.py --monitor-only`")

with action_cols[2]:
    if st.button("Test Checkout", use_container_width=True):
        st.info("Run `python bot.py --dry-run --test-checkout <URL> <RETAILER>`")

with action_cols[3]:
    if st.button("Proxy Health", use_container_width=True):
        st.info("Run `python bot.py --health-check`")
