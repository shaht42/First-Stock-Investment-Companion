"""
First Stock Investment Companion — v6
======================================
Phase 1 additions over v5:
  - BEGINNER MODE: star metrics, plain-English flags, decision tree, scenario analysis
  - EXPERT MODE: full 10-metric display (existing analysis, unchanged)
  - Sidebar toggle: Beginner ↔ Expert
  - Interactive glossary: expandable "What is X?" under every metric
  - Scenario analysis: Bull / Base / Bear + stress test
  - Exchange detection: NYSE / NASDAQ / TSX badge
  - Asset type badge: Stock / ETF
  - Data freshness timestamp
  - Disclaimer footer
"""

import yfinance as yf
import pandas as pd
import streamlit as st
import requests
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIG  (must be first Streamlit call)
# ============================================================================

st.set_page_config(
    page_title="Stock Investment Companion",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CUSTOM CSS
# ============================================================================

st.markdown("""
<style>
/* Card-style containers */
.stExpander { border-radius: 6px !important; }

/* Beginner metric rows */
.metric-row {
    padding: 6px 0;
    border-bottom: 1px solid rgba(128,128,128,0.15);
}

/* Mobile: single-column feel */
@media (max-width: 640px) {
    h1 { font-size: 1.3rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 1rem   !important; }
    .block-container { padding: 1rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SHARED HELPERS
# ============================================================================

def flag_emoji(flag):
    return {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴", "SKIP": "⚪"}.get(flag, "⚪")

def check_emoji(flag):
    """Simple symbols for beginner mode."""
    return {"GREEN": "✅", "YELLOW": "⚠️", "RED": "❌"}.get(flag, "⚪")


# ============================================================================
# GLOSSARY CONTENT
# ============================================================================

GLOSSARY = {
    "revenue_growth": {
        "name": "Revenue Growth",
        "long": """**Revenue Growth** = How much more the company sold this year vs last year.

**Formula:** (This Year's Revenue − Last Year's Revenue) ÷ Last Year's Revenue × 100

**Example:**
- 2023 revenue: $100M
- 2024 revenue: $108M
- Growth = 8%

**What's good?**
- Above 10% 🟢 · 0–10% 🟡 · Negative = shrinking 🔴

**TL;DR:** Higher % = company is growing its sales — usually a good sign.""",
    },
    "profit_margin": {
        "name": "Profit Margin",
        "long": """**Profit Margin** = % of revenue the company keeps as profit after all costs.

**Formula:** Net Income ÷ Revenue × 100

**Example:**
- Revenue: $100M · Profit: $20M
- Margin = 20%

**What's good?**
- Above 15% 🟢 · 5–15% 🟡 · Below 5% or negative 🔴

**TL;DR:** Higher % = company keeps more of every dollar it earns.""",
    },
    "debt_to_equity": {
        "name": "Debt-to-Equity",
        "long": """**Debt-to-Equity (D/E)** = Total Debt ÷ Shareholder Equity.

**Example:**
- Debt: $150M · Equity: $100M → D/E = 1.5
- For every $1 of equity, company has $1.50 in debt

**What's good?**
- Below 1.0 🟢 · 1–2 🟡 · Above 2 🔴 (banks are exempt — they carry more debt by nature)

**TL;DR:** Lower = safer. High debt is risky when the economy turns bad.""",
    },
    "roe": {
        "name": "Return on Equity (ROE)",
        "long": """**ROE** = How much profit the company generates per dollar shareholders invested.

**Formula:** Net Income ÷ Shareholder Equity × 100

**Example:**
- Shareholders invested $100M · Company earned $20M profit
- ROE = 20%

**What's good?**
- Above 15% 🟢 · 10–15% 🟡 · Below 10% 🔴

**TL;DR:** Higher ROE = company is better at turning your investment into profit.""",
    },
    "fcf": {
        "name": "Free Cash Flow (FCF)",
        "long": """**Free Cash Flow** = Real cash left after running the business and investing in growth.

**Formula:** Operating Cash Flow − Capital Expenditures

**Example:**
- Operations generate $50M · Spending on equipment: $10M
- FCF = $40M ← actual cash in hand

**Why better than profit?**
Accounting profits can be inflated. Cash can't be faked.

**What's good?**
- Positive and growing 🟢 · Positive but small 🟡 · Negative 🔴

**TL;DR:** FCF is the company's real take-home pay.""",
    },
    "pe_ratio": {
        "name": "P/E Ratio (Price-to-Earnings)",
        "long": """**P/E Ratio** = How much you pay per $1 of annual profit.

**Formula:** Stock Price ÷ Earnings Per Share

**Example:**
- Stock at $200 · Earns $8/share → P/E = 25x
- You pay $25 for every $1 earned

**Context matters:**
- Fast-growing tech company: 30x might be fine
- Slow-growing utility: 30x is expensive
- S&P 500 average: ~18–20x
- Negative P/E = company losing money → 🔴

**TL;DR:** Lower P/E = cheaper — but cheap for a reason, or a hidden gem?""",
    },
    "peg_ratio": {
        "name": "PEG Ratio",
        "long": """**PEG Ratio** = P/E adjusted for growth speed.

**Formula:** P/E Ratio ÷ Earnings Growth Rate

**Example:**
- P/E = 30x · Earnings growing at 30%/year → PEG = 1.0 (fair)
- P/E = 30x · Earnings growing at 10%/year → PEG = 3.0 (expensive!)

**What's good?**
- Below 1.0 🟢 · 1–2 🟡 · Above 2 🔴

**TL;DR:** A "high" P/E might be fair if the company is growing fast enough.""",
    },
    "ev_ebitda": {
        "name": "EV/EBITDA",
        "long": """**EV/EBITDA** = Full company price vs operating profit.

- **EV (Enterprise Value)** = Market cap + Debt − Cash (price to buy the whole company)
- **EBITDA** = Earnings before interest, taxes, depreciation — a measure of operating profit

**Example:**
- Company costs $500M total · Generates $50M EBITDA/year → EV/EBITDA = 10x

**What's good?**
- Below 10x 🟢 · 10–15x 🟡 · Above 15x 🔴

**TL;DR:** Lower = cheaper vs operating profit. Useful for comparing across companies.""",
    },
    "pb_ratio": {
        "name": "Price-to-Book (P/B)",
        "long": """**P/B Ratio** = Price vs what the company is worth "on paper."

- **Book Value** = Total Assets − Total Liabilities

**Example:**
- Net assets = $100M · Market cap = $200M → P/B = 2x
- You pay 2x what it's worth on paper

**What's good?**
- Below 1x 🟢 · 1–3x 🟡 · Negative P/B = liabilities exceed assets 🔴

**TL;DR:** P/B < 1 can be a bargain. Negative P/B is a red flag.""",
    },
    "current_ratio": {
        "name": "Current Ratio",
        "long": """**Current Ratio** = Can the company pay its short-term bills?

**Formula:** Current Assets ÷ Current Liabilities

**Example:**
- $200M in short-term assets · $100M in bills due soon → Ratio = 2.0

**What's good?**
- Above 1.5 🟢 · 1.0–1.5 🟡 · Below 1.0 = can't pay short-term bills 🔴

**TL;DR:** Above 1 = can pay bills. Below 1 = cash crunch risk.""",
    },
    "expense_ratio": {
        "name": "Expense Ratio",
        "long": """**Expense Ratio** = Annual management fee charged by an ETF or fund.

**Example:**
- $10,000 invested in an ETF with 0.20% expense ratio
- Annual fee = $10,000 × 0.002 = **$20/year**

**What's good?**
- Below 0.20% 🟢 · 0.20–0.50% 🟡 · Above 0.50% 🔴

**TL;DR:** Always pick the lower-cost fund when two ETFs do the same thing. Fees compound painfully over decades.""",
    },
}

def show_glossary(key):
    """Render expandable 'What is X?' under a metric."""
    if key not in GLOSSARY:
        return
    g = GLOSSARY[key]
    with st.expander(f"📚 What is {g['name']}?"):
        st.markdown(g['long'])


# ============================================================================
# EXCHANGE DETECTION
# ============================================================================

# Maps yfinance internal exchange codes → readable names.
# No hardcoded ticker list needed: .TO catches all TSX, yfinance handles everything else.
_EXCHANGE_YF_MAP = {
    'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ',
    'NYQ': 'NYSE',   'NYSEArca': 'NYSE', 'PCX': 'NYSE Arca',
    'TSX': 'TSX',    'TOR': 'TSX',
}

@st.cache_data(ttl=3600)
def detect_exchange(ticker):
    """
    Exchange detection for any ticker — no hardcoded list required.
    1. Ends with .TO  → TSX  (instant, covers every Canadian listing)
    2. Ask yfinance   → works for any stock/ETF on Yahoo Finance
    3. Fallback       → UNKNOWN
    """
    if ticker.upper().endswith(".TO"):
        return "TSX"
    try:
        exc = yf.Ticker(ticker).info.get('exchange', '') or ''
        return _EXCHANGE_YF_MAP.get(exc, exc or "UNKNOWN")
    except:
        return "UNKNOWN"


# ============================================================================
# 1. ETF CHECK
# ============================================================================

@st.cache_data(ttl=3600)
def is_etf(ticker):
    try:
        qt = yf.Ticker(ticker).info.get('quoteType', '').upper()
        return qt in ['ETF', 'ECNQUOTE']
    except:
        return False


# ============================================================================
# 2. FETCH RAW FINANCIAL STATEMENTS
# ============================================================================

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    tk = yf.Ticker(ticker)
    income_stmt   = tk.income_stmt
    balance_sheet = tk.balance_sheet
    cashflow      = tk.cashflow

    if income_stmt.empty or balance_sheet.empty or cashflow.empty:
        raise ValueError(f"{ticker}: No financial statements found. Check the ticker.")

    cutoff = pd.Timestamp('2021-12-31')
    income_stmt   = income_stmt.loc[:, income_stmt.columns   > cutoff]
    balance_sheet = balance_sheet.loc[:, balance_sheet.columns > cutoff]
    cashflow      = cashflow.loc[:, cashflow.columns         > cutoff]

    if len(income_stmt.columns) < 2:
        raise ValueError(f"{ticker}: Need at least 2 fiscal years after 2021.")

    return {
        "ticker":        ticker,
        "income_stmt":   income_stmt,
        "balance_sheet": balance_sheet,
        "cashflow":      cashflow,
    }


# ============================================================================
# 3. COMPANY INFO
# ============================================================================

@st.cache_data(ttl=3600)
def get_company_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        raw  = info.get('longBusinessSummary', '')
        desc = (raw[:280] + '…') if len(raw) > 280 else raw
        return {
            "name":          info.get('longName', ticker),
            "description":   desc,
            "sector":        info.get('sector', 'Unknown'),
            "industry":      info.get('industry', 'Unknown'),
            "week_52_high":  info.get('fiftyTwoWeekHigh'),
            "week_52_low":   info.get('fiftyTwoWeekLow'),
            "current_price": info.get('currentPrice') or info.get('regularMarketPrice'),
            "beta":          info.get('beta'),
        }
    except:
        return {
            "name": ticker, "description": "", "sector": "Unknown",
            "industry": "Unknown", "week_52_high": None,
            "week_52_low": None, "current_price": None, "beta": None,
        }


# ============================================================================
# 4. GET PEERS — DYNAMIC via Yahoo Finance
# ============================================================================

@st.cache_data(ttl=3600)
def get_peers(ticker):
    try:
        url = (
            "https://query2.finance.yahoo.com"
            f"/v6/finance/recommendationsbysymbol/{ticker}"
        )
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data    = r.json()
            results = data.get('finance', {}).get('result', [])
            if results:
                recs  = results[0].get('recommendedSymbols', [])
                peers = [
                    rec['symbol'] for rec in recs
                    if rec.get('symbol', '').upper() != ticker.upper()
                ][:4]
                if peers:
                    return peers, "dynamic"
    except:
        pass
    return [], "none"


# ============================================================================
# 5. EXTRACT FUNDAMENTAL METRICS
# ============================================================================

@st.cache_data(ttl=3600)
def extract_metrics(ticker):
    data          = fetch_stock_data(ticker)
    income_stmt   = data["income_stmt"]
    balance_sheet = data["balance_sheet"]
    cashflow      = data["cashflow"]

    latest = income_stmt.columns[0]
    prior  = income_stmt.columns[1]

    revenue_latest      = income_stmt.loc['Total Revenue',         latest]
    revenue_prior       = income_stmt.loc['Total Revenue',         prior]
    net_income          = income_stmt.loc['Net Income',            latest]
    total_debt          = balance_sheet.loc['Total Debt',          latest]
    stockholders_equity = balance_sheet.loc['Stockholders Equity', latest]
    operating_cf        = cashflow.loc['Operating Cash Flow',      latest]
    capex               = cashflow.loc['Capital Expenditure', latest] if 'Capital Expenditure' in cashflow.index else 0

    sector       = yf.Ticker(ticker).info.get('sector', '')
    is_financial = 'Financial' in sector

    d_red, d_yellow, roe_min = (3.5, 2.0, 10) if is_financial else (2.0, 1.0, 15)

    revenue_growth = (
        ((revenue_latest - revenue_prior) / revenue_prior) * 100
        if (not pd.isna(revenue_prior) and revenue_prior != 0) else 0
    )
    profit_margin  = (net_income / revenue_latest * 100)      if revenue_latest      != 0 else 0
    debt_to_equity = (total_debt / stockholders_equity)       if stockholders_equity != 0 else 0
    roe            = (net_income / stockholders_equity * 100) if stockholders_equity != 0 else 0
    fcf            = operating_cf - capex
    fcf_to_flag    = net_income if is_financial else fcf

    def flag_revenue_growth(v):
        if pd.isna(v) or v == 0: return "YELLOW"
        if v < -5:               return "RED"
        if v < 0:                return "YELLOW"
        return "GREEN"

    def flag_profit_margin(v):
        if v < 0:  return "RED"
        if v < 10: return "YELLOW"
        return "GREEN"

    def flag_debt_to_equity(v):
        if v > d_red:    return "RED"
        if v > d_yellow: return "YELLOW"
        return "GREEN"

    def flag_roe(v):
        if v < 0:       return "RED"
        if v < roe_min: return "YELLOW"
        return "GREEN"

    def flag_fcf(v, revenue):
        if v < 0:              return "RED"
        if revenue <= 0:       return "YELLOW"
        if v < revenue * 0.05: return "YELLOW"
        return "GREEN"

    return {
        "revenue_growth":      float(round(revenue_growth, 2)),
        "revenue_growth_flag": flag_revenue_growth(revenue_growth),
        "profit_margin":       float(round(profit_margin, 2)),
        "profit_margin_flag":  flag_profit_margin(profit_margin),
        "debt_to_equity":      float(round(debt_to_equity, 2)),
        "debt_to_equity_flag": flag_debt_to_equity(debt_to_equity),
        "roe":                 float(round(roe, 2)),
        "roe_flag":            flag_roe(roe),
        "fcf":                 float(round(fcf_to_flag, 0)),
        "fcf_flag":            flag_fcf(fcf_to_flag, revenue_latest),
        "is_financial":        is_financial,
    }


# ============================================================================
# 6. EXTRACT VALUATION METRICS
# ============================================================================

@st.cache_data(ttl=3600)
def extract_valuation_metrics(ticker):
    info = yf.Ticker(ticker).info

    def first_valid(*keys):
        for k in keys:
            v = info.get(k)
            if v is not None:
                return v
        return None

    def to_float(v):
        try:    return float(v)
        except: return 0

    return {
        'pe_ratio':      to_float(first_valid('trailingPE', 'forwardPE')),
        'peg_ratio':     to_float(first_valid('pegRatio')),
        'ev_ebitda':     to_float(first_valid('enterpriseToEbitda')),
        'pb_ratio':      to_float(first_valid('priceToBook')),
        'current_ratio': to_float(first_valid('currentRatio')),
    }


# ============================================================================
# 7. FLAG VALUATION vs PEER MEDIAN
# ============================================================================

def flag_valuation_metrics(target_metrics, peer_metrics_list):
    flags        = {}
    peer_medians = {}

    for key in ['pe_ratio', 'peg_ratio', 'ev_ebitda', 'pb_ratio', 'current_ratio']:
        vals = [m[key] for m in peer_metrics_list if m[key] > 0]
        peer_medians[key] = float(pd.Series(vals).median()) if len(vals) >= 2 else None

    def compare(val, median, metric):
        if metric == 'pe_ratio'  and val < 0: return "RED"
        if metric == 'pb_ratio'  and val < 0: return "RED"
        if val == 0 or median is None or median == 0: return "SKIP"
        if metric == 'current_ratio':
            if val < 1.0:           return "RED"
            if val < median * 0.85: return "YELLOW"
            return "GREEN"
        deviation = (val - median) / median
        if deviation < 0.10: return "GREEN"
        if deviation < 0.25: return "YELLOW"
        return "RED"

    for key in ['pe_ratio', 'peg_ratio', 'ev_ebitda', 'pb_ratio', 'current_ratio']:
        flags[key] = compare(target_metrics[key], peer_medians.get(key), key)

    return flags, peer_medians


# ============================================================================
# 8. ETF ANALYSIS
# ============================================================================

def _extract_expense_ratio(info):
    for field in ['annualReportExpenseRatio', 'totalExpenseRatio', 'expense_ratio']:
        val = info.get(field)
        if val is not None and isinstance(val, (int, float)) and val > 0:
            if val < 0.10:
                return round(val * 100, 3)
            elif val < 5.0:
                return round(float(val), 3)
    return None


@st.cache_data(ttl=3600)
def extract_etf_metrics(ticker):
    tk   = yf.Ticker(ticker)
    info = tk.info

    ytd_hist   = tk.history(start="2026-01-01")
    ytd_return = (
        (ytd_hist['Close'].iloc[-1] - ytd_hist['Close'].iloc[0])
        / ytd_hist['Close'].iloc[0] * 100
        if not ytd_hist.empty else 0
    )

    yr_hist        = tk.history(period="1y")
    week_52_change = 0
    current_price  = None
    if not yr_hist.empty:
        week_52_change = (
            (yr_hist['Close'].iloc[-1] - yr_hist['Close'].iloc[0])
            / yr_hist['Close'].iloc[0] * 100
        )
        current_price = yr_hist['Close'].iloc[-1]

    divs           = tk.dividends
    dividend_yield = 0
    if not divs.empty and current_price:
        cutoff         = divs.index[-1] - timedelta(days=365)
        dividend_yield = divs[divs.index > cutoff].sum() / current_price * 100

    return {
        "expense_ratio":     _extract_expense_ratio(info),
        "dividend_yield":    round(float(dividend_yield),    2),
        "ytd_return":        round(float(ytd_return),        2),
        "52week_change":     round(float(week_52_change),    2),
        "assets_under_mgmt": float(info.get('totalAssets',   0) or 0),
        "avg_volume":        float(info.get('averageVolume', 0) or 0),
        "current_price":     current_price,
    }


@st.cache_data(ttl=3600)
def analyze_etf(ticker):
    m = extract_etf_metrics(ticker)

    # Detect complex / high-risk ETF types by dividend yield.
    # Covered call ETFs (NVDY, QYLD, XYLD) pay options premium as "dividends".
    # The yield looks huge but the fund slowly erodes in value (return of capital).
    div_yield    = m["dividend_yield"]
    is_complex   = div_yield > 15   # covered call, single-stock, thematic
    is_high_risk = div_yield > 30   # extreme yield -> very likely capital erosion

    def flag_expense(v):
        if v is None: return "SKIP"
        if v < 0.20:  return "GREEN"
        if v < 0.50:  return "YELLOW"
        return "RED"

    def flag_tracking(v):
        return "GREEN" if v > 0 else "YELLOW"

    def flag_liquidity(aum, vol):
        if aum == 0:                      return "SKIP"
        if aum > 1e9   and vol > 200_000: return "GREEN"
        if aum > 100e6 and vol > 50_000:  return "YELLOW"
        return "RED"

    ef = flag_expense(m["expense_ratio"])
    tf = flag_tracking(m["ytd_return"])
    lf = flag_liquidity(m["assets_under_mgmt"], m["avg_volume"])

    red_count = sum(f == "RED" for f in [ef, tf, lf])

    if is_high_risk:
        rec    = "CAUTION"
        reason = "Extreme yield — likely a covered call or options-based fund. Research carefully before buying."
    elif is_complex:
        rec    = "HOLD"
        reason = "High yield suggests a complex strategy (covered calls, options). Not a simple index fund."
    elif red_count >= 2:
        rec, reason = "AVOID", "High costs or low liquidity"
    elif red_count == 1 or tf == "YELLOW":
        rec, reason = "HOLD",  "Consider, but not ideal"
    else:
        cost_note   = ", costs moderate" if ef == "YELLOW" else ", low costs"
        rec, reason = "BUY",   "Good tracking + liquid" + cost_note

    return {
        "ticker":         ticker,
        "is_etf":         True,
        "etf_metrics":    m,
        "flags":          {"expense_ratio_flag": ef, "tracking_flag": tf, "liquidity_flag": lf},
        "recommendation": rec,
        "reason":         reason,
        "is_complex":     is_complex,
        "is_high_risk":   is_high_risk,
    }


# ============================================================================
# 9. MAIN STOCK ANALYSIS
# ============================================================================

@st.cache_data(ttl=3600)
def analyze_stock(ticker):
    if is_etf(ticker):
        return analyze_etf(ticker)

    fund            = extract_metrics(ticker)
    val             = extract_valuation_metrics(ticker)
    peers, peer_src = get_peers(ticker)

    peer_vals = []
    for p in peers:
        try:
            if not is_etf(p):
                peer_vals.append(extract_valuation_metrics(p))
        except:
            pass

    if peer_vals:
        val_flags, peer_medians = flag_valuation_metrics(val, peer_vals)
    else:
        val_flags    = {k: "YELLOW" for k in ['pe_ratio', 'peg_ratio', 'ev_ebitda', 'pb_ratio', 'current_ratio']}
        peer_medians = {}

    fund_red   = sum(1 for k, v in fund.items() if k.endswith('_flag') and v == 'RED')
    fund_green = sum(1 for k, v in fund.items() if k.endswith('_flag') and v == 'GREEN')
    val_red    = sum(1 for v in val_flags.values() if v == 'RED')

    if fund_red >= 3:
        rec, reason = "SELL", "Fundamentals are broken"
    elif fund_red >= 1 and val_red >= 3:
        rec, reason = "HOLD", "Weak fundamentals + expensive vs peers"
    elif val_red >= 4:
        rec, reason = "HOLD", "Too expensive relative to peers"
    elif fund_green >= 3 and fund_red == 0 and val_red <= 1:
        rec, reason = "BUY",  "Strong fundamentals + reasonable valuation"
    else:
        rec, reason = "HOLD", "Mixed signals — not enough confidence to buy"

    return {
        "ticker":              ticker,
        "fundamental_metrics": fund,
        "valuation_metrics":   val,
        "valuation_flags":     val_flags,
        "peer_medians":        peer_medians,
        "peer_source":         peer_src,
        "peers_list":          peers,
        "fundamental_red":     fund_red,
        "fundamental_green":   fund_green,
        "valuation_red":       val_red,
        "recommendation":      rec,
        "reason":              reason,
    }


# ============================================================================
# 10. SCENARIO GENERATION (educational estimates only)
# ============================================================================

def generate_scenarios(result, info):
    """
    Build rough Bull / Base / Bear price targets.
    Driven by signal quality and beta. NOT predictions.
    """
    price = info.get('current_price')
    if not price or price <= 0:
        return None

    rec        = result.get('recommendation', 'HOLD')
    beta       = max(0.5, min(2.5, info.get('beta') or 1.0))

    if rec == 'BUY':
        bull_pct, base_pct, bear_pct        = 0.35, 0.12, -0.20
        bull_prob, base_prob, bear_prob     = 35, 45, 20
        bull_driver = "Growth accelerates; market rewards strong fundamentals"
        base_driver = "Steady performance; modest market gains"
        bear_driver = "Market downturn or missed earnings guidance"
    elif rec == 'SELL':
        bull_pct, base_pct, bear_pct        = 0.10, -0.10, -0.40
        bull_prob, base_prob, bear_prob     = 15, 35, 50
        bull_driver = "Surprise turnaround or acquisition premium"
        base_driver = "Gradual decline as weak fundamentals weigh on price"
        bear_driver = "Fundamental problems worsen; possible dividend cut"
    else:  # HOLD
        bull_pct, base_pct, bear_pct        = 0.20, 0.05, -0.25
        bull_prob, base_prob, bear_prob     = 25, 50, 25
        bull_driver = "Better-than-expected results boost confidence"
        base_driver = "Company performs in line with expectations"
        bear_driver = "Macro headwinds or one key metric deteriorates"

    # Widen/narrow range by beta
    bull_pct *= beta
    bear_pct *= beta

    return {
        "current_price": round(price, 2),
        "bull": {
            "price": round(price * (1 + bull_pct), 2),
            "pct":   round(bull_pct * 100, 1),
            "prob":  bull_prob,
            "driver": bull_driver,
        },
        "base": {
            "price": round(price * (1 + base_pct), 2),
            "pct":   round(base_pct * 100, 1),
            "prob":  base_prob,
            "driver": base_driver,
        },
        "bear": {
            "price": round(price * (1 + bear_pct), 2),
            "pct":   round(abs(bear_pct) * 100, 1),
            "prob":  bear_prob,
            "driver": bear_driver,
        },
    }


# ============================================================================
# 11. BEGINNER METRICS DISPLAY
# ============================================================================

def show_beginner_metrics(result):
    """Five ⭐ metrics in plain English with glossary links."""
    st.subheader("⭐ Key Metrics")

    fund = result['fundamental_metrics']
    val  = result['valuation_metrics']

    items = [
        {
            "question":     "Is it profitable?",
            "value":        f"{fund['profit_margin']:.1f}% profit margin",
            "flag":         fund['profit_margin_flag'],
            "good":         "Company keeps a healthy share of every dollar it earns.",
            "caution":      "Margins are thin — worth watching closely.",
            "bad":          "Negative margins: the company is spending more than it earns.",
            "glossary_key": "profit_margin",
        },
        {
            "question":     "Is it growing?",
            "value":        f"{fund['revenue_growth']:.1f}% revenue growth (last year)",
            "flag":         fund['revenue_growth_flag'],
            "good":         "Sales are expanding — healthy momentum.",
            "caution":      "Growth is slow. Not a disaster, but watch for further slowing.",
            "bad":          "Revenue is shrinking. The business may be losing ground.",
            "glossary_key": "revenue_growth",
        },
        {
            "question":     "Is debt manageable?",
            "value":        f"{fund['debt_to_equity']:.2f}x debt-to-equity ratio",
            "flag":         fund['debt_to_equity_flag'],
            "good":         "Debt is under control — company can weather downturns.",
            "caution":      "Debt is elevated but not alarming. Watch if it keeps rising.",
            "bad":          "High debt is risky if earnings slow or rates rise.",
            "glossary_key": "debt_to_equity",
        },
        {
            "question":     "Is it using money efficiently?",
            "value":        f"{fund['roe']:.1f}% return on equity",
            "flag":         fund['roe_flag'],
            "good":         "Strong return on shareholder capital — well-run business.",
            "caution":      "Moderate efficiency. Room to improve.",
            "bad":          "Not generating enough return on invested capital.",
            "glossary_key": "roe",
        },
        {
            "question":     "Is real cash flowing in?",
            "value":        f"${fund['fcf']:,.0f} free cash flow",
            "flag":         fund['fcf_flag'],
            "good":         "Generating real cash — harder to fake than accounting profits.",
            "caution":      "Cash flow is modest relative to the size of the business.",
            "bad":          "Negative cash flow: the company is burning more than it earns.",
            "glossary_key": "fcf",
        },
    ]

    # Add P/E if available
    pe = val.get('pe_ratio', 0)
    if pe and pe != 0:
        if pe < 0:
            pe_flag = "RED"
        elif pe < 25:
            pe_flag = "GREEN"
        elif pe < 40:
            pe_flag = "YELLOW"
        else:
            pe_flag = "RED"

        items.append({
            "question":     "Is the price reasonable?",
            "value":        f"{pe:.1f}x P/E ratio",
            "flag":         pe_flag,
            "good":         "Price looks reasonable relative to earnings.",
            "caution":      "On the expensive side — not alarming, but leave less margin for error.",
            "bad":          "Very expensive or company is currently unprofitable.",
            "glossary_key": "pe_ratio",
        })

    for item in items:
        f = item['flag']
        emoji = check_emoji(f)
        if f == 'GREEN':
            explanation = item['good']
        elif f == 'RED':
            explanation = item['bad']
        else:
            explanation = item['caution']

        st.markdown(f"**{emoji} {item['question']}**")
        st.markdown(f"*{item['value']}* — {explanation}")
        show_glossary(item['glossary_key'])
        st.divider()


# ============================================================================
# 12. BEGINNER DECISION TREE
# ============================================================================

def show_decision_tree(result, info, ticker):
    """Step-by-step buying checklist. Each question can stop the flow early."""
    st.subheader("🤔 Should You Buy?")
    st.markdown("Work through these questions honestly before deciding:")

    fund = result['fundamental_metrics']
    val  = result['valuation_metrics']
    rec  = result['recommendation']
    pfx  = f"dt_{ticker}"   # unique key prefix per ticker

    # ── Q1: Do you understand the business? ─────────────────────────────────
    st.markdown("**1. Do you understand what this company does?**")
    q1 = st.radio(
        "q1", ["✅ Yes — I know their products and business model",
               "❌ No — not really"],
        key=f"{pfx}_q1", label_visibility="collapsed"
    )

    if "No" in q1:
        st.error(
            "**Stop here.** Warren Buffett's rule: never invest in a business you don't understand. "
            "Read the company's Wikipedia page or annual report, then come back."
        )
        return

    # ── Q2: Is it making money? ──────────────────────────────────────────────
    pm    = fund['profit_margin']
    pm_ok = pm > 5
    st.markdown("**2. Is the company making money?**")
    st.caption(f"Profit margin: **{pm:.1f}%** {'✅' if pm_ok else '⚠️'}")

    q2 = st.radio(
        "q2", ["✅ Yes (or it's a young growth company and I understand the risk)",
               "❌ No, and I'm not sure why it's losing money"],
        key=f"{pfx}_q2", label_visibility="collapsed"
    )

    if "not sure" in q2:
        st.warning(
            "**Hold off.** Unprofitable companies can turn around — "
            "but you should know *why* before betting on it. Research the path to profitability first."
        )
        return

    # ── Q3: Is the price comfortable? ────────────────────────────────────────
    pe = val.get('pe_ratio', 0)
    st.markdown("**3. Are you comfortable with the current price?**")
    if pe and pe > 0:
        st.caption(f"P/E ratio: **{pe:.1f}x** (S&P 500 average ≈ 18–20x)")
    else:
        st.caption("P/E not available — company may be unprofitable or data is missing")

    q3 = st.radio(
        "q3", ["✅ Yes — the price looks fair to me",
               "⏸️ It feels expensive — I'd rather wait for a pullback"],
        key=f"{pfx}_q3", label_visibility="collapsed"
    )

    if "expensive" in q3:
        st.warning(
            "**Good instinct.** Discipline is the hardest part of investing. "
            "Consider setting a price alert 10–15% below today's price."
        )
        return

    # ── Final verdict ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Based on your answers + the 10-metric analysis:**")

    if rec == "BUY":
        st.success(
            "✅ **Looks like a reasonable candidate.**\n\n"
            "Strong fundamentals, price not alarming vs peers. If this fits your portfolio, "
            "a position could make sense — but keep it to a reasonable slice (10–15% max of your portfolio)."
        )
    elif rec == "SELL":
        st.error(
            "❌ **The fundamentals raise serious concerns.**\n\n"
            "Even with confident answers above, the model sees multiple red flags. "
            "Wait for the company to show sustained improvement before buying."
        )
    else:
        st.warning(
            "⏸️ **Mixed signals — proceed carefully.**\n\n"
            "This isn't a clear BUY or SELL. If you have high conviction from your own research, "
            "a small starter position is reasonable. Don't overcommit."
        )

    st.caption("⚠️ This is educational analysis, not financial advice. Always do your own research.")


# ============================================================================
# 13. SCENARIO DISPLAY
# ============================================================================

def show_scenarios(scenarios):
    if not scenarios:
        st.info("Scenario analysis requires a current price — unavailable for this ticker.")
        return

    st.subheader("🎲 Scenario Analysis")
    st.caption(
        f"Current price: **${scenarios['current_price']:.2f}** · "
        "Rough estimates for educational purposes only — NOT predictions."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        b = scenarios['bull']
        st.markdown("**🐂 Bull Case**")
        st.markdown(f"Probability: **{b['prob']}%**")
        st.metric("Target", f"${b['price']:.2f}", f"+{b['pct']}%")
        st.caption(b['driver'])

    with c2:
        base = scenarios['base']
        st.markdown("**⚖️ Base Case**")
        st.markdown(f"Probability: **{base['prob']}%**")
        sign = "+" if base['pct'] >= 0 else ""
        st.metric("Target", f"${base['price']:.2f}", f"{sign}{base['pct']}%")
        st.caption(base['driver'])

    with c3:
        bear = scenarios['bear']
        st.markdown("**🐻 Bear Case**")
        st.markdown(f"Probability: **{bear['prob']}%**")
        st.metric("Target", f"${bear['price']:.2f}", f"-{bear['pct']}%")
        st.caption(bear['driver'])

    st.markdown("---")
    p   = scenarios['current_price']
    h50 = round(p * 0.5, 2)
    st.info(
        f"**Stress test:** In a severe market crash (−50%), this stock could fall to ~**${h50:.2f}**. "
        "Could you hold through that without panic-selling? If not, invest a smaller amount."
    )


# ============================================================================
# ██████████  STREAMLIT UI  ██████████
# ============================================================================

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    mode = st.radio(
        "Display mode:",
        ["🌱 Beginner", "🎓 Expert"],
        index=0,
        help=(
            "Beginner: 6 starred metrics, plain English, decision tree, scenarios, glossary.\n"
            "Expert: full 10-metric analysis with peer comparison table."
        ),
    )
    beginner_mode = (mode == "🌱 Beginner")

    st.markdown("---")
    if beginner_mode:
        st.markdown("""
**Beginner mode includes:**
- ⭐ 6 key metrics in plain English
- 📚 Click any metric to learn what it means
- 🤔 Step-by-step buying checklist
- 🎲 Bull / Base / Bear scenarios
- 🔥 Stress test (what if it drops 50%?)
        """)
    else:
        st.markdown("""
**Expert mode includes:**
- 📊 5 fundamental + 5 valuation metrics
- 💎 Flags vs peer medians
- ⚖️ Side-by-side competitor table
- 🟢🟡🔴 Full flag breakdown
        """)

    st.markdown("---")
    st.caption("Phase 2: Portfolio builder, watchlist, paper trading — coming soon.")

# ── Header ───────────────────────────────────────────────────────────────────

st.title("📈 First Stock Investment Companion")

if beginner_mode:
    st.markdown(
        "**🌱 Beginner Mode** — Key signals, plain English, and a step-by-step guide. "
        "Switch to Expert in the sidebar for full metric detail."
    )
else:
    st.markdown(
        "**🎓 Expert Mode** — Full 10-metric analysis with peer comparison. "
        "Switch to Beginner in the sidebar for simplified view."
    )

ticker_input = st.text_input(
    "Ticker:",
    placeholder="e.g., AAPL, MSFT, RY.TO, SPY, XEQT.TO",
    label_visibility="collapsed",
).strip().upper()

if not ticker_input:
    if beginner_mode:
        st.info(
            "👉 Type a stock ticker above to get started. "
            "A ticker is the short code for a company — **AAPL** = Apple, **RY.TO** = Royal Bank, **MSFT** = Microsoft."
        )
    else:
        st.info("👉 Enter any stock ticker or ETF above to get started.")
    st.stop()

# ── Fetch + route ─────────────────────────────────────────────────────────────

try:
    with st.spinner(f"Fetching data for {ticker_input}…"):
        result   = analyze_stock(ticker_input)
        exchange = detect_exchange(ticker_input)

    # Freshness bar
    st.caption(
        f"📅 Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"(cached up to 1 hr)  ·  ⚠️ Educational only — not financial advice"
    )

    # Asset / exchange badge
    asset_type = "ETF" if result.get('is_etf') else "Stock"
    st.markdown(f"**{ticker_input}** &nbsp;·&nbsp; {asset_type} &nbsp;·&nbsp; {exchange}")

    # ═══════════════════════════════════════════════════════════════════
    # ETF PATH
    # ═══════════════════════════════════════════════════════════════════
    if result.get('is_etf'):
        rec = result['recommendation']
        if   rec == 'BUY':     st.success(f"✅ **{ticker_input}: BUY** — {result['reason']}")
        elif rec == 'HOLD':    st.warning(f"⏸️ **{ticker_input}: HOLD** — {result['reason']}")
        elif rec == 'CAUTION': st.error(  f"⚠️ **{ticker_input}: CAUTION** — {result['reason']}")
        else:                  st.error(  f"❌ **{ticker_input}: AVOID** — {result['reason']}")

        # Complex / high-risk ETF warning block
        if result.get('is_high_risk'):
            st.error("""
**⚠️ This appears to be a covered call or options-based ETF.**

The very high dividend yield is mostly **options premium and return of your own capital** —
not real income. These funds slowly erode in value while appearing to "pay" you.

**What that means in plain English:**
If you invest $10,000 in a fund that "yields" 67%, you might receive $6,700/year in
distributions — but your $10,000 could shrink to $6,000 or less over that same period.
You didn't earn money; the fund just gave it back to you in instalments.

These are complex products designed for experienced investors. **Not recommended for beginners.**
""")
        elif result.get('is_complex'):
            st.warning("""
**⚠️ This may be a complex or thematic ETF, not a simple index fund.**

The high dividend yield suggests it uses options strategies or targets a specific niche.
These carry more risk than broad market ETFs. Research the fund's strategy before buying.
""")

        st.subheader("📊 ETF Metrics")
        m, fl = result['etf_metrics'], result['flags']
        c1, c2, c3 = st.columns(3)

        with c1:
            fe = fl['expense_ratio_flag']
            st.markdown("**Expense Ratio**")
            if m['expense_ratio'] is not None:
                st.write(f"{m['expense_ratio']:.2f}%  {flag_emoji(fe)} {fe}")
            else:
                st.write("⚪ Not reported — check the fund's website")
            if beginner_mode:
                show_glossary("expense_ratio")
            st.divider()

        with c2:
            tf = fl['tracking_flag']
            st.markdown("**YTD Return**")
            st.write(f"{m['ytd_return']:.2f}%  {flag_emoji(tf)} {tf}")
            st.divider()

        with c3:
            lf = fl['liquidity_flag']
            st.markdown("**Fund Size (AUM)**")
            if lf != "SKIP":
                st.write(f"${m['assets_under_mgmt']/1e9:.2f}B  {flag_emoji(lf)} {lf}")
            else:
                st.write("⚪ Data unavailable")
            st.divider()

        ca, cb = st.columns(2)
        ca.metric("Dividend Yield", f"{m['dividend_yield']:.2f}%")
        cb.metric("52-Week Change", f"{m['52week_change']:.2f}%")

        if beginner_mode:
            st.divider()
            st.markdown("""
**💡 Quick reading guide:**
- **Expense Ratio < 0.20%** ✅ &nbsp;|&nbsp; 0.20–0.50% ⚠️ &nbsp;|&nbsp; > 0.50% ❌ (high fees eat your returns)
- **YTD Return** = how much the fund has gained since Jan 1 this year
- **Fund Size (AUM)** = larger funds are easier to buy/sell without affecting the price
- **Dividend Yield** = % of your investment paid back as cash distributions per year
            """)

        with st.expander("📖 How is the BUY / HOLD / AVOID signal decided?"):
            st.markdown("""
Three things are checked:
1. **Expense ratio** — is the annual fee reasonable?
2. **YTD return** — is the fund tracking the market?
3. **Liquidity** — is the fund large enough to buy/sell easily?

🟢 **BUY** = all three look good  
🟡 **HOLD** = one concern, worth considering  
🔴 **AVOID** = high fees or low liquidity (could be hard to exit when you need to)
""")

    # ═══════════════════════════════════════════════════════════════════
    # STOCK PATH
    # ═══════════════════════════════════════════════════════════════════
    else:
        info = get_company_info(ticker_input)

        st.markdown(f"### {info['name']}  ({ticker_input})")
        st.caption(
            f"**Sector:** {info['sector']}  ·  "
            f"**Industry:** {info['industry']}  ·  "
            f"**Exchange:** {exchange}"
        )

        if info['week_52_low'] and info['week_52_high']:
            price_str = (
                f"  ·  **Current price:** ${info['current_price']:.2f}"
                if info['current_price'] else ""
            )
            st.markdown(
                f"**52-week range:** ${info['week_52_low']:.2f} — "
                f"${info['week_52_high']:.2f}{price_str}"
            )

        if info['description']:
            with st.expander("🏢 About this company"):
                st.write(info['description'])

        st.divider()

        # Recommendation banner
        rec = result['recommendation']
        if   rec == 'BUY':  st.success(f"✅ **{ticker_input}: BUY** — {result['reason']}")
        elif rec == 'HOLD': st.warning(f"⏸️ **{ticker_input}: HOLD** — {result['reason']}")
        else:               st.error(  f"❌ **{ticker_input}: SELL** — {result['reason']}")

        if result['peer_source'] == 'none':
            st.warning(
                "⚠️ Yahoo Finance returned no peer stocks for this ticker. "
                "Valuation flags (P/E vs peers, etc.) are unreliable — treat them as approximate."
            )

        # ── BEGINNER MODE ──────────────────────────────────────────────────
        if beginner_mode:
            ca, cb = st.columns(2)
            ca.metric("✅ Strong points",  result['fundamental_green'])
            cb.metric("❌ Concerns",       result['fundamental_red'])
            st.divider()

            show_beginner_metrics(result)
            st.divider()

            show_decision_tree(result, info, ticker_input)
            st.divider()

            scenarios = generate_scenarios(result, info)
            show_scenarios(scenarios)

            with st.expander("📖 How is BUY / HOLD / SELL decided?"):
                st.markdown("""
The tool checks **10 things** in two groups:

**Group 1 — Business health (5 checks):**
Revenue growth · Profit margin · Debt-to-equity · Return on equity · Free cash flow

**Group 2 — Price fairness vs similar companies (5 checks):**
P/E ratio · PEG ratio · EV/EBITDA · Price-to-book · Current ratio

**Decision rules:**
- 🟢 **BUY** = 3+ green business checks, zero red ones, AND price not stretched vs peers
- 🔴 **SELL** = 3+ red business checks (serious trouble)
- 🟡 **HOLD** = everything else — mixed signals, wait for clarity

**HOLD is not bad.** It just means "not enough certainty to act yet."
""")

        # ── EXPERT MODE ────────────────────────────────────────────────────
        else:
            ca, cb, cc, cd = st.columns(4)
            ca.metric("🟢 Fundamental Green", result['fundamental_green'])
            cb.metric("🔴 Fundamental Red",   result['fundamental_red'])
            cc.metric("🔴 Valuation Red",     result['valuation_red'])
            cd.metric("Signal",               rec)

            # Fundamental metrics
            st.subheader("📊 Fundamental Metrics (Company Health)")
            c1, c2 = st.columns(2)

            fund_items = [
                ("📈 Revenue Growth (YoY)", "revenue_growth", "%"),
                ("💰 Profit Margin",        "profit_margin",  "%"),
                ("⚠️ Debt-to-Equity",       "debt_to_equity", ""),
                ("🎯 Return on Equity",     "roe",            "%"),
                ("💵 Free Cash Flow",       "fcf",            "$"),
            ]
            for i, (label, key, unit) in enumerate(fund_items):
                v    = result['fundamental_metrics'][key]
                flag = result['fundamental_metrics'][f'{key}_flag']
                with c1 if i % 2 == 0 else c2:
                    st.write(f"**{label}**")
                    st.write(
                        f"${v:,.0f}  {flag_emoji(flag)} {flag}" if unit == "$"
                        else f"{v}{unit}  {flag_emoji(flag)} {flag}"
                    )
                    st.divider()

            # Valuation metrics
            st.subheader("💎 Valuation Metrics (Price vs Peers)")
            c1, c2  = st.columns(2)
            col_idx = 0

            val_items = [
                ("P/E Ratio",     "pe_ratio",      "x"),
                ("PEG Ratio",     "peg_ratio",     "x"),
                ("EV/EBITDA",     "ev_ebitda",     "x"),
                ("Price-to-Book", "pb_ratio",      "x"),
                ("Current Ratio", "current_ratio", "x"),
            ]
            for label, key, unit in val_items:
                flag   = result['valuation_flags'][key]
                val_v  = result['valuation_metrics'][key]
                if flag == "SKIP":
                    continue
                median = result['peer_medians'].get(key, 0)
                with c1 if col_idx % 2 == 0 else c2:
                    st.write(f"**{label}**")
                    if val_v < 0 and key == 'pe_ratio':
                        st.write(f"{val_v:.2f}{unit}  {flag_emoji(flag)}  Company currently unprofitable")
                    elif val_v < 0 and key == 'pb_ratio':
                        st.write(f"{val_v:.2f}{unit}  {flag_emoji(flag)}  Liabilities exceed assets")
                    elif median and median > 0:
                        st.write(f"This company: {val_v:.2f}{unit}")
                        st.write(f"Peer median:  {median:.2f}{unit}")
                        st.write(f"Status: {flag_emoji(flag)} {flag}")
                    else:
                        st.write(f"{val_v:.2f}{unit}  {flag_emoji(flag)} {flag}")
                    st.divider()
                col_idx += 1

            with st.expander("📖 What do these metrics mean?"):
                st.markdown("""
**FUNDAMENTAL METRICS (company's own numbers):**
- **Revenue Growth:** Is the company growing? Negative = shrinking
- **Profit Margin:** % of revenue kept as profit. Higher = more efficient
- **Debt-to-Equity:** Debt vs. shareholder equity. High = risky
- **ROE:** Profit per dollar of shareholder investment. Higher = better
- **Free Cash Flow:** Cash left after costs and investments. Negative = danger

**VALUATION METRICS (price vs competitors):**
- **P/E Ratio:** Price per $1 of earnings. Negative = company losing money → RED
- **PEG Ratio:** P/E adjusted for growth. <1 = possibly cheap, >1 = possibly expensive
- **EV/EBITDA:** Full company price vs operating profit. Lower = cheaper
- **Price-to-Book:** Price vs assets. Negative = liabilities exceed assets → RED
- **Current Ratio:** Can it pay short-term bills? >1.5 = healthy, <1 = risky

**HOW BUY / HOLD / SELL IS DECIDED:**
- 🟢 **BUY** = 3+ green fundamentals, 0 red fundamentals, AND ≤ 1 red valuation flag
- 🔴 **SELL** = 3+ red fundamentals (company is in serious trouble)
- 🟡 **HOLD** = everything else (mixed signals or expensive vs peers)
""")

            # Competitor comparison
            st.subheader("⚖️ Competitor Comparison")
            peers = result.get('peers_list', [])

            if peers:
                st.caption(
                    f"Peers from Yahoo Finance for {ticker_input}: "
                    f"{', '.join(peers)}"
                )
                comp   = {ticker_input: result}
                failed = []

                for peer in peers:
                    try:
                        pr = analyze_stock(peer)
                        if not pr.get('is_etf'):
                            comp[peer] = pr
                    except:
                        failed.append(peer)

                if len(comp) > 1:
                    rows = {}
                    for t, r in comp.items():
                        fm = r['fundamental_metrics']
                        vm = r['valuation_metrics']
                        rows[t] = {
                            "Growth %": f"{fm['revenue_growth']}%",
                            "Profit %": f"{fm['profit_margin']}%",
                            "D/E":      f"{fm['debt_to_equity']}",
                            "ROE %":    f"{fm['roe']}%",
                            "P/E":      f"{vm['pe_ratio']:.1f}"  if vm['pe_ratio']  != 0 else "N/A",
                            "PEG":      f"{vm['peg_ratio']:.2f}" if vm['peg_ratio'] > 0  else "N/A",
                            "P/B":      f"{vm['pb_ratio']:.1f}"  if vm['pb_ratio']  != 0 else "N/A",
                            "Signal":   r['recommendation'],
                        }
                    st.dataframe(pd.DataFrame(rows).T, use_container_width=True)
                    if failed:
                        st.caption(f"Could not load: {', '.join(failed)}")
                else:
                    st.warning("Could not load peer comparison data.")
            else:
                st.info(
                    "Yahoo Finance returned no similar stocks for this ticker. "
                    "Try a more widely-traded stock."
                )

        st.markdown("---")
        st.markdown(
            "**Legend:** 🟢 GREEN = Good &nbsp;|&nbsp; 🟡 YELLOW = Caution "
            "&nbsp;|&nbsp; 🔴 RED = Warning &nbsp;|&nbsp; ⚪ SKIP = No data"
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "⚠️ **Disclaimer:** This tool is for educational purposes only and is not financial advice. "
        "Past performance does not guarantee future results. "
        "Always consult a licensed financial advisor before making investment decisions."
    )

except ValueError as e:
    st.error(f"❌ {e}")
except Exception as e:
    st.error(f"❌ Error analyzing {ticker_input}: {str(e)}")