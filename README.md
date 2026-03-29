# Trade Surveillance Platform

**BITS Hackathon 2026** — An end-to-end trade surveillance system that detects market manipulation and suspicious trading activity across crypto and equity markets.

---

## Table of Contents

1. [What Is Trade Surveillance?](#what-is-trade-surveillance)
2. [Finance Glossary](#finance-glossary)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Quick Start](#quick-start)
6. [Pipeline Steps](#pipeline-steps)
7. [Dashboard Guide](#dashboard-guide)
8. [Web Frontend (Next.js)](#web-frontend-nextjs)
9. [Configuration](#configuration)
10. [Regulatory Context](#regulatory-context)

---

## What Is Trade Surveillance?

Trade surveillance is the process of monitoring financial markets to detect illegal or manipulative trading activity. When people trade stocks, cryptocurrencies, or other financial instruments, they must follow rules set by regulators. Some traders try to break these rules to make unfair profits — at the expense of everyone else in the market.

**Why does it matter?**

- Protects ordinary investors from being cheated by manipulators
- Maintains trust and fairness in financial markets
- Prevents financial crimes like money laundering
- Required by law for exchanges, brokers, and financial institutions

**What this system does:**

This platform ingests raw trade data from crypto and equity markets and runs a multi-layered detection pipeline:

1. **Rule-based detectors** — Hand-crafted heuristics flag known manipulation patterns
2. **AI ground truth** — A large language model independently evaluates every trade for suspicion
3. **ML re-ranker** — A machine learning model learns from the comparison between rules and AI
4. **Committee fusion** — A "three-way vote" combines all three approaches to maximize true positive detection

The result is a set of flagged trades with explanations, confidence scores, and violation types — presented through a **Next.js** dashboard (nine sections: surveillance pages, pipeline control, workflow map, in-app knowledge base, and audit trail), backed by a **FastAPI** API. A Streamlit `app.py` remains optional for the same outputs.

---

## Finance Glossary

Below are detailed definitions of every manipulation type this system detects. Each entry explains what the activity is, why it is illegal, how we detect it, and which regulations it violates.

### Wash Trading

**What it is:** A trader simultaneously buys and sells the same asset to create artificial trading volume. For example, Trader A sells 100 BTC to Trader B, but A and B are actually the same person (or colluding). The asset doesn't really change hands.

**Why it is illegal:** It deceives other market participants into believing there is genuine demand or supply. Other traders may enter the market based on the fake volume, only to lose money. It violates the principle of fair and transparent markets.

**Real-world example:** In 2019, a study found that up to 95% of Bitcoin trading volume on certain exchanges was wash trading. The CFTC has fined multiple firms millions of dollars for wash trading in crypto futures.

**How we detect it:** We look for trades where the same wallet (trader_id) appears on both sides of a transaction within a short time window, or where round-trip patterns (buy → sell → buy of the same amount) occur repeatedly.

**Regulations violated:** SEC Rule 10b-5, Commodity Exchange Act § 4c(a), Dodd-Frank Act § 747.

### Spoofing

**What it is:** A trader places a large buy or sell order with no intention of executing it, just to create the illusion of demand (or supply). Once other traders react to the fake order and move the price, the spoofer cancels the order and trades in the opposite direction at the new, manipulated price.

**Why it is illegal:** It artificially moves prices, allowing the spoofer to profit at the expense of traders who believed the orders were real. Markets must reflect genuine supply and demand.

**Real-world example:** In 2015, the DOJ charged Navinder Singh Sarao with spoofing in the E-mini S&P 500 futures market. His activity contributed to the 2010 Flash Crash.

**How we detect it:** We track large orders that are placed and quickly cancelled (high cancel rates). In equity markets (P1), we look for bursts of cancellations within short time windows.

**Regulations violated:** Dodd-Frank Act § 747, SEC Rule 10b-5, MiFID II Article 12.

### Layering

**What it is:** A more sophisticated form of spoofing. The trader places multiple non-genuine orders at different price levels (creating "layers") to create the appearance of depth in the order book, then executes a real trade on the other side.

**Why it is illegal:** Same as spoofing — it artificially distorts the order book and misleads other market participants about true supply and demand.

**Real-world example:** In 2018, the SEC fined a trading firm $1.4 million for layering in U.S. equity markets.

**How we detect it:** We look for chains of orders (often 3+ within a short window) on the same side that are later cancelled after a real trade executes on the opposite side.

**Regulations violated:** Dodd-Frank Act § 747, SEC Rule 10b-5.

### Pump and Dump

**What it is:** A group of traders accumulates a position in a low-volume asset, then artificially inflates the price through coordinated buying ("pump"). Once the price rises, they sell their holdings at the inflated price ("dump"), crashing the market and leaving other traders with losses.

**Why it is illegal:** It is securities fraud. The pumpers deceive other market participants by creating false price momentum.

**Real-world example:** Crypto "pump-and-dump" groups on Telegram coordinate buying of small-cap tokens. The SEC has charged numerous individuals for pump-and-dump schemes in penny stocks.

**How we detect it:** We identify bars (time periods) where price rises sharply on concentrated buying, followed by rapid selling. We use a trimmed approach that filters out noise and focuses on statistically significant price swings.

**Regulations violated:** SEC Rule 10b-5, Securities Act § 17(a), MiCA (EU crypto regulation).

### Ramping

**What it is:** A trader places a series of progressively higher buy orders to push the price upward (or progressively lower sell orders to push it down). Unlike pump-and-dump, ramping may involve a single actor incrementally moving the price.

**Why it is illegal:** It creates artificial price trends that mislead other traders into believing there is genuine directional momentum.

**How we detect it:** We look for sequences of trades from the same wallet where each trade occurs at a higher price than the previous one, with the final trade being a sell at the inflated level.

**Regulations violated:** SEC Rule 10b-5, Market Abuse Regulation (EU).

### AML Structuring

**What it is:** Anti-Money Laundering structuring (also called "smurfing") involves breaking up large financial transactions into smaller ones to avoid triggering regulatory reporting thresholds. For example, instead of transferring $50,000 at once (which would trigger a Currency Transaction Report), a person might make 10 transfers of $4,900.

**Why it is illegal:** It is a federal crime designed to evade the Bank Secrecy Act's reporting requirements. Even if the underlying money is legitimate, the act of structuring itself is illegal.

**Real-world example:** In 2023, Binance was fined $4.3 billion for AML compliance failures, including failing to detect structuring patterns.

**How we detect it:** We cluster trades by wallet and time window, looking for multiple transactions just below round-number thresholds that together exceed a significant amount.

**Regulations violated:** Bank Secrecy Act (BSA), FinCEN regulations, Anti-Money Laundering Directives (EU).

### Peg Manipulation

**What it is:** Stablecoins like USDC are designed to maintain a 1:1 peg with the U.S. dollar. Peg manipulation involves trading activity that deliberately moves a stablecoin's price away from its peg, profiting from the temporary deviation.

**Why it is illegal:** It undermines the fundamental guarantee of stablecoins and can cause cascading losses across DeFi protocols.

**How we detect it:** We monitor USDC trades and flag bars where the price deviates significantly from the expected $1.00 peg.

**Regulations violated:** MiCA (Title III — stablecoin regulation), potential application of SEC Rule 10b-5.

### Order Book Imbalance (OBI)

**What it is:** Order Book Imbalance measures the ratio between buy-side and sell-side depth in the order book. A high OBI means there are significantly more bids than asks (or vice versa). While OBI itself isn't illegal, extreme and sustained imbalances can indicate manipulation.

**How we detect it (P1):** We compute rolling z-scores of OBI over 30-minute windows. Sustained extreme z-scores (indicating the order book is consistently one-sided) trigger alerts. We also check bid concentration and spread anomalies.

### Pre-Announcement Drift

**What it is:** Stock prices sometimes move suspiciously before a public announcement (like an earnings report or leadership change). This can indicate insider trading — someone with non-public knowledge is trading before the news is public.

**How we detect it (P2):** We pull 8-K filings from the SEC EDGAR database, identify the filing date, then analyze price and volume patterns in the days before the announcement. Significant abnormal returns or volume spikes trigger a drift flag.

**Regulations violated:** SEC Rule 10b-5, Insider Trading Sanctions Act.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User's Browser                        │
│   Next.js + Tailwind v4 + shadcn/ui + Recharts + React Flow  │
│   (http://localhost:3000)                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ fetch() calls
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                            │
│              (http://localhost:8000/api/*)                    │
│                                                              │
│  GET  /api/outputs/{name}     Serve CSV data as JSON         │
│  GET  /api/reports/{name}     Serve text reports             │
│  POST /api/run/{pipeline}     Trigger pipeline steps         │
│  POST /api/upload             Upload CSV + run detection     │
│  GET  /api/status             Output file status             │
│  GET  /api/decisions          Read HITL audit log            │
│  POST /api/decisions          Write HITL audit log           │
└──────────────────────────┬──────────────────────────────────┘
                           │ subprocess.run / direct import
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   Python Pipelines                            │
│                                                              │
│  Step 1: Rule-based Detectors  (P1 equity, P2 SEC, P3 crypto)│
│  Step 2: AI Ground Truth       (LLM via OpenRouter)          │
│  Step 3: Compare               (Rules vs AI agreement)       │
│  Step 4: ML Re-Ranker          (GradientBoosting classifier) │
│  Step 5: Committee Fusion      (Three-way vote)              │
│  Step 6: Parameter Tuning      (Threshold suggestions)       │
└──────────────────────────┬──────────────────────────────────┘
                           │ reads / writes
                           ▼
                    outputs/*.csv / *.txt
```

**The 5-step detection pipeline:**

1. **Rule-Based Detection** — Hand-crafted heuristics scan trade data for patterns matching known manipulation types. Fast and interpretable.
2. **AI Ground Truth Generation** — An LLM (via OpenRouter API) independently evaluates every trade, providing verdicts and confidence scores.
3. **Comparison** — The rule-based flags are compared against AI verdicts to identify agreements, rule-only detections, and AI-only detections.
4. **ML Re-Ranking** — A Gradient Boosting classifier is trained on the comparison data to learn which flags are most likely true positives.
5. **Committee Fusion** — All three sources (rules, AI, ML) are combined in a tiered voting system. Trades flagged by 2+ methods are high confidence; single-source flags are evaluated with additional criteria.

---

## Project Structure

```
BITS Hackathon/
├── bits_hackathon/               # Python pipeline package
│   ├── core/
│   │   ├── paths.py              # Centralized path definitions
│   │   ├── config.py             # Thresholds and settings
│   │   └── crypto_load.py        # Data loading functions
│   ├── detectors/
│   │   ├── p1_equity.py          # Equity order book anomaly detection
│   │   ├── p2_sec.py             # SEC 8-K and insider drift detection
│   │   └── p3_crypto.py          # Crypto manipulation detection
│   └── pipeline/
│       ├── ground_truth_agent.py  # LLM-based ground truth labeling
│       ├── compare.py             # Rules vs AI comparison
│       ├── reranker.py            # ML re-ranking model
│       ├── parameter_tuning.py    # Threshold tuning suggestions
│       └── committee.py           # Three-way committee fusion
├── api/                           # FastAPI backend
│   ├── main.py                    # App entry point, CORS, route mounting
│   └── routes/
│       ├── outputs.py             # CSV → JSON endpoints
│       ├── reports.py             # Text report endpoints
│       ├── run.py                 # Pipeline trigger endpoints
│       ├── upload.py              # File upload + analysis
│       ├── status.py              # Output file status
│       └── decisions.py           # HITL audit log
├── frontend/                      # Next.js 16 dashboard (App Router)
│   └── src/
│       ├── app/
│       │   ├── globals.css        # Theme tokens + Tailwind v4 `@custom-variant dark` (class-based)
│       │   ├── layout.tsx         # Theme script, shell, sidebar + main
│       │   ├── p3/page.tsx        # Crypto surveillance
│       │   ├── p1/page.tsx        # Equity alerts
│       │   ├── p2/page.tsx        # SEC signals
│       │   ├── committee/page.tsx # Committee analytics
│       │   ├── comparison/page.tsx
│       │   ├── control/page.tsx   # Pipeline runs + upload + status
│       │   ├── audit/page.tsx     # HITL audit trail
│       │   ├── workflow/page.tsx  # Interactive pipeline mind map (React Flow)
│       │   └── knowledge/page.tsx # In-app glossary + regulations + pipeline explainer
│       ├── components/
│       │   ├── sidebar.tsx        # Nav (active item = solid highlight)
│       │   ├── theme-provider.tsx # light / dark / system + `color-scheme`
│       │   ├── theme-toggle.tsx
│       │   └── ui/                # Button, Card, Badge, Tabs, Input, etc.
│       └── lib/
│           ├── api.ts             # Fetch helpers → FastAPI
│           └── utils.ts
├── app.py                         # Optional: Streamlit HITL fallback (same outputs/)
├── student-pack/                  # Input data (not committed)
│   ├── crypto-market/            # OHLCV bars per symbol
│   ├── crypto-trades/            # Raw trade records per symbol
│   └── equity/                   # Equity market + trade data
├── outputs/                       # Pipeline output files
├── feedback/                      # HITL decision audit log
├── run.py                         # Unified CLI entry point
├── config.yaml                    # Detector thresholds
├── requirements.txt               # Python dependencies
└── .env                           # API keys (not committed)
```

---

## Quick Start

### Prerequisites

- **Python 3.10+** with pip
- **Node.js 20+** with npm
- **OpenRouter API key** (for AI ground truth — optional if only using rule-based detection)

### 1. Clone and install Python dependencies

```bash
cd "BITS Hackathon"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
# Create .env file
echo "OPENROUTER_API_KEY=sk-or-v1-your-key-here" > .env
```

### 3. Place input data

Put the hackathon dataset under `student-pack/`:
```
student-pack/
├── crypto-market/    # BTCUSDT.csv, ETHUSDT.csv, ... (OHLCV bars)
├── crypto-trades/    # BTCUSDT.csv, ETHUSDT.csv, ... (raw trades)
└── equity/
    ├── market_data.csv
    ├── trade_data.csv
    └── ohlcv.csv
```

### 4. Run the detection pipeline

```bash
# Run everything at once
python3 run.py all

# Or run individual steps
python3 run.py p3          # Crypto rules
python3 run.py p1          # Equity rules
python3 run.py p2          # SEC filings (needs internet)
python3 run.py ground-truth  # AI labeling (needs API key)
python3 run.py compare     # Rules vs AI comparison
python3 run.py reranker    # ML re-ranking
python3 run.py committee   # Committee fusion
python3 run.py tune        # Parameter tuning
```

### 5. Start the dashboard

**Terminal 1 — FastAPI backend:**
```bash
cd "BITS Hackathon"
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Next.js frontend:**
```bash
cd "BITS Hackathon/frontend"
npm install    # first time only
npm run dev
```

Open **http://localhost:3000** in your browser.

The UI talks to the API at **`http://localhost:8000`** by default. To point at another host, set:

`NEXT_PUBLIC_API_URL=https://your-api-host` before `npm run dev` (or in `frontend/.env.local`).

---

## Pipeline Steps

### Step 1: Rule-Based Detection

The rule engine scans every trade record using hand-crafted heuristics:

**P3 — Crypto (8 symbols × ~250K trades each):**
- Wash trade round-trip detection (same wallet, buy→sell→buy within time window)
- Spoofing / layering chain detection (rapid order sequences)
- Pump-and-dump bar analysis (sharp price rise + concentrated selling)
- Ramping sequence detection (incrementally higher prices from same wallet)
- AML structuring clusters (many small trades just below thresholds)
- Peg break detection (USDC price deviation from $1)
- BAT hourly volume spike detection
- Bar-range violation detection (price moves exceeding statistical norms)

**P1 — Equity:**
- Rolling 30-minute z-scores of Order Book Imbalance (OBI)
- Spread anomaly detection
- Bid concentration monitoring
- Cancel-burst alerts from trade data

**P2 — SEC:**
- Pulls 8-K filings from SEC EDGAR for each equity
- Classifies filings by item number (earnings, leadership changes, etc.)
- Scores pre-filing volume and return patterns
- Flags significant pre-announcement drift

**Output:** `submission.csv`, `p1_alerts.csv`, `p2_signals.csv`

### Step 2: AI Ground Truth

An LLM (via OpenRouter) independently evaluates trades:

- Uses a two-pass strategy: fast stub analysis first, then LLM deep evaluation on borderline cases
- The LLM receives trade context (price, volume, time, wallet, surrounding bar data) and returns a verdict (suspicious / benign / uncertain), confidence score, and reasoning
- Concurrent API calls with retry logic for reliability

**Output:** `ground_truth.csv`

### Step 3: Comparison

Compares rule-based flags against AI verdicts:

- Identifies agreements (both flagged), rule-only flags, and AI-only flags
- Calculates agreement rates per symbol and violation type
- Highlights where rules and AI diverge — these are the most interesting cases

**Output:** `comparison_report.csv`

### Step 4: ML Re-Ranker

A Gradient Boosting classifier trained on comparison data:

- Features: rule confidence, AI confidence, trade characteristics (volume, price deviation, time patterns)
- Target: whether the trade is a true positive based on agreement patterns
- Outputs calibrated probability scores for each flagged trade
- Reports precision, recall, F1, and AUC metrics

**Output:** `submission_ml.csv`, `reranker_report.txt`

### Step 5: Committee Fusion

A three-way voting system that combines rules, AI, and ML:

| Zone | Sources Agreeing | Action |
|------|-----------------|--------|
| All 3 agree | Rules + AI + ML | Highest confidence — always include |
| Rules + AI | 2 of 3 | Include — strong agreement between interpretable and AI |
| Rules + ML | 2 of 3 | Include — statistical and heuristic agreement |
| AI + ML | 2 of 3 | Include — model-based agreement |
| Rules only | 1 of 3 | Keep if rules have high confidence |
| AI only | 1 of 3 | Keep if AI confidence exceeds threshold (configurable per violation type) |
| ML only | 1 of 3 | Drop by default (configurable) |

**Output:** `submission_committee.csv`, `committee_report.txt`

### Step 6: Parameter Tuning

Analyzes comparison results and suggests threshold adjustments:

- Identifies violation types where rules over-flag or under-flag relative to AI
- Suggests specific threshold changes for each detector
- Helps iteratively improve rule-based detection accuracy

**Output:** `tuning_report.txt`

---

## Dashboard Guide

Nine routes live in the sidebar. **Theme:** use the control at the bottom of the sidebar to switch **Light**, **Dark**, or **System** (preference is stored in `localStorage` as `theme`). Dark mode uses neutral gray/black surfaces; primary blue is reserved for actions and accents.

| Route | Purpose |
|-------|---------|
| **P3 Crypto** | Rules vs **Committee** submission tabs, stats, violation bar chart, filters, expandable rows, CSV export. |
| **P1 Equity** | Order-book alerts, severity badges, filters, expandable remarks. |
| **P2 SEC** | 8-K-style signals, drift badges, EDGAR links, event-type chart. **If the page is empty**, `outputs/p2_signals.csv` is missing or has no data rows — run `python3 run.py p2` with network access; SEC may rate-limit or skip unmatched tickers / `other`-only filings. |
| **Committee** | Zone breakdown, violation mix, ML report text, tuning report (tabs). |
| **Comparison** | Agree/disagree charts, GT verdict bars, tabs: GT-only, Rules-only, both, full table. |
| **Pipeline** | One card per pipeline step with **Run** (calls `POST /api/run/...`), log output, CSV upload, output file status table + **Refresh**. |
| **Audit Trail** | Log HITL decisions (`POST /api/decisions`), filter table, stats, JSON export. |
| **Workflow** | Interactive pipeline diagram (**React Flow**): drag nodes, zoom, click a stage for inputs/outputs/insights. |
| **Knowledge Base** | Same ideas as this README’s glossary: violation types (expandable cards), regulatory frameworks, how the multi-stage detection works. |

**Navigation:** the current page uses a **solid lighter background** on the nav row (white pill in light mode, lighter gray in dark mode) so the active section is obvious.

---

## Web Frontend (Next.js)

- **Stack:** Next.js 16 (App Router), React 19, Tailwind CSS v4, shadcn-style UI components, Recharts, **@xyflow/react** (workflow graph).
- **Dark mode:** Tailwind’s `dark:` variant is scoped to **`.dark` on `<html>`** (see `globals.css`: `@custom-variant dark (&:where(.dark, .dark *))`). That keeps “Light” mode from picking up OS dark `dark:` styles and avoids contrast bugs.
- **First paint:** `layout.tsx` runs a small `beforeInteractive` script so `localStorage` + system preference apply before React hydrates.
- **Buttons:** Primary actions use a clear gradient/focus treatment so controls (especially on **Pipeline**) read as clickable in both themes.
- **Optional:** `app.py` is still a **Streamlit** dashboard over the same `outputs/` files if you prefer that workflow.

---

## Configuration

### `config.yaml`

Controls detector thresholds. Key sections:

```yaml
p3.wash.window_minutes: 15        # Time window for wash trade detection
p3.wash.qty_tolerance: 0.02       # Quantity match tolerance (2%)
p3.layering.min_chain: 3          # Minimum orders in a layering chain
p3.pump.price_jump_pct: 5.0       # Price jump threshold for pump detection
p3.aml.cluster_window_minutes: 60 # AML clustering time window

committee:
  ai_only_conf_default: 0.85      # Default AI confidence threshold
  ai_only_conf_wash: 0.80         # Lower threshold for wash trades
  ai_only_conf_layering: 0.90     # Higher threshold for layering
  rules_only_keep_uncertain: true  # Keep uncertain rule-only flags
  ml_only_include: false           # Exclude ML-only flags by default
```

### Environment variables

| Variable | Where | Required | Description |
|----------|--------|----------|-------------|
| `OPENROUTER_API_KEY` | Repo root `.env` | For AI pipeline | OpenRouter API key |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` (optional) | No | FastAPI base URL; default `http://localhost:8000` |

---

## Regulatory Context

This system is designed with awareness of the following regulatory frameworks:

### Dodd-Frank Wall Street Reform Act (2010)

Enacted after the 2008 financial crisis, Dodd-Frank introduced sweeping reforms to U.S. financial regulation. **Section 747** specifically addresses market manipulation, making spoofing and disruptive trading practices illegal in commodity and derivatives markets. The act gives the CFTC authority to prosecute manipulative and deceptive practices.

### Bank Secrecy Act (BSA) / Anti-Money Laundering (AML)

The BSA requires financial institutions to assist government agencies in detecting and preventing money laundering. Key requirements include:
- **Currency Transaction Reports (CTRs)** for transactions over $10,000
- **Suspicious Activity Reports (SARs)** for potentially illicit transactions
- **Know Your Customer (KYC)** programs

Our AML structuring detection directly addresses the BSA's concern about transaction structuring to evade reporting thresholds.

### SEC Rule 10b-5

The primary anti-fraud rule under U.S. securities law. It prohibits:
- Employment of any device, scheme, or artifice to defraud
- Making untrue statements of material fact
- Engaging in any practice that operates as fraud or deceit upon any person

Wash trading, spoofing, layering, and pump-and-dump all violate Rule 10b-5.

### Markets in Crypto-Assets Regulation (MiCA)

The EU's comprehensive framework for crypto asset regulation (effective 2024). MiCA introduces:
- Market abuse provisions specifically for crypto markets (Title VI)
- Stablecoin regulation (Title III) — relevant to our peg manipulation detection
- Requirements for crypto-asset service providers to implement surveillance systems
- Prohibition of insider dealing, market manipulation, and unlawful disclosure

### Insider Trading Sanctions Act (1984) / Insider Trading and Securities Fraud Enforcement Act (1988)

These acts strengthen penalties for insider trading and establish liability for firms that fail to prevent it. Our P2 pre-announcement drift detection helps identify potential insider trading by flagging abnormal price movements before public disclosures.

---

## License

BITS Hackathon 2026 — Academic project.
