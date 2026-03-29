# Finance glossary & regulatory context

Long-form reference for manipulation types, detection notes, and regulations. The web app **Knowledge Base** (`/knowledge`) mirrors much of this for interactive reading.

---

## Violation types (detailed)

### Wash Trading

**What it is:** A trader simultaneously buys and sells the same asset to create artificial trading volume (e.g. same entity on both sides).

**Why illegal:** Deceives others about real supply/demand.

**Example:** High reported crypto volume on some venues was attributed in studies to wash trading; CFTC has fined firms for wash trading in futures.

**How we detect:** Same `trader_id` on both sides within a window; round-trip buy→sell→buy patterns.

**Regulations:** SEC Rule 10b-5, CEA § 4c(a), Dodd-Frank § 747.

### Spoofing

**What it is:** Large orders placed to move the book, then cancelled; trader profits on the other side.

**Why illegal:** Artificial price pressure.

**Example:** DOJ charges related to E-mini spoofing and the 2010 Flash Crash narrative.

**How we detect:** Cancel bursts; P1 equity cancel clustering.

**Regulations:** Dodd-Frank § 747, SEC 10b-5, MiFID II Art. 12.

### Layering

**What it is:** Multiple non-genuine price levels (“layers”) then real trade the other way.

**Why illegal:** False depth in the order book.

**Example:** SEC fines for layering in equities.

**How we detect:** Chains of same-side orders cancelled after opposite-side execution.

**Regulations:** Dodd-Frank § 747, SEC 10b-5.

### Pump and Dump

**What it is:** Pump price, sell into liquidity, others hold losses.

**Why illegal:** Securities fraud / false momentum.

**Example:** Telegram pump groups; penny-stock enforcement.

**How we detect:** Sharp bar moves + concentrated selling after pump.

**Regulations:** SEC 10b-5, Securities Act § 17(a), MiCA.

### Ramping

**What it is:** Series of buys (or sells) stepping price to create a trend.

**Why illegal:** Misleading directional signal.

**How we detect:** Same wallet, monotonic prices, exit trade.

**Regulations:** SEC 10b-5, EU MAR.

### AML structuring (“smurfing”)

**What it is:** Splitting transfers to stay under reporting thresholds.

**Why illegal:** BSA evasion; structuring itself can be a crime.

**Example:** Large exchange AML enforcement.

**How we detect:** Wallet clusters of many sub-threshold trades in a window.

**Regulations:** BSA, FinCEN, EU AMLD.

### Peg manipulation

**What it is:** Trading that breaks stablecoin peg for profit.

**Why illegal / risky:** Undermines stable value promise; systemic DeFi risk.

**How we detect:** USDC bars far from $1.

**Regulations:** MiCA Title III; 10b-5 may apply in some contexts.

### Order book imbalance (P1)

**What it is:** Extreme sustained bid/ask depth skew; can accompany manipulation.

**How we detect:** Rolling OBI z-scores, spread, bid concentration.

### Pre-announcement drift (P2)

**What it is:** Price/volume moves before public 8-K-type news; possible insider activity.

**How we detect:** SEC submissions + pre-window OHLCV/trade stats.

**Regulations:** SEC 10b-5; insider trading statutes.

---

## Regulatory frameworks (summary)

- **Dodd-Frank (2010):** § 747 — spoofing / disruptive trading in derivatives; CFTC authority.
- **BSA / AML:** CTRs, SARs, KYC; structuring is a core concern.
- **SEC Rule 10b-5:** Anti-fraud; wash, spoof, layer, pump-and-dump, insider-style abuse.
- **MiCA (EU):** Crypto market abuse, stablecoins, CASP surveillance duties.
- **Insider trading acts (1984/1988):** Stronger penalties; aligns with P2 drift surveillance.

---

*BITS Hackathon 2026 — reference only, not legal advice.*
