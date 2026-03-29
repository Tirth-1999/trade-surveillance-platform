"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  Repeat,
  Layers,
  TrendingUp,
  ArrowUpDown,
  Landmark,
  DollarSign,
  BarChart3,
  Activity,
  Scale,
  ShieldCheck,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Search,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Glossary data                                                     */
/* ------------------------------------------------------------------ */

type GlossaryEntry = {
  id: string;
  title: string;
  icon: React.ReactNode;
  color: string;
  what: string;
  why: string;
  example: string;
  detection: string;
  regulations: string[];
  category: "manipulation" | "structural" | "insider";
};

const GLOSSARY: GlossaryEntry[] = [
  {
    id: "wash-trading",
    title: "Wash Trading",
    icon: <Repeat className="h-5 w-5" />,
    color: "bg-red-500/15 text-red-700 dark:text-red-300",
    category: "manipulation",
    what: "A trader simultaneously buys and sells the same asset to create artificial trading volume. For example, Trader A sells 100 BTC to Trader B, but A and B are actually the same person (or colluding). The asset doesn't really change hands.",
    why: "It deceives other market participants into believing there is genuine demand or supply. Other traders may enter the market based on the fake volume, only to lose money. It violates the principle of fair and transparent markets.",
    example: "In 2019, a study found that up to 95% of Bitcoin trading volume on certain exchanges was wash trading. The CFTC has fined multiple firms millions of dollars for wash trading in crypto futures.",
    detection: "We look for trades where the same wallet (trader_id) appears on both sides of a transaction within a short time window, or where round-trip patterns (buy \u2192 sell \u2192 buy of the same amount) occur repeatedly.",
    regulations: ["SEC Rule 10b-5", "Commodity Exchange Act \u00a74c(a)", "Dodd-Frank Act \u00a7747"],
  },
  {
    id: "spoofing",
    title: "Spoofing",
    icon: <AlertTriangle className="h-5 w-5" />,
    color: "bg-orange-500/15 text-orange-700 dark:text-orange-300",
    category: "manipulation",
    what: "A trader places a large buy or sell order with no intention of executing it, just to create the illusion of demand (or supply). Once other traders react to the fake order and move the price, the spoofer cancels the order and trades in the opposite direction at the new, manipulated price.",
    why: "It artificially moves prices, allowing the spoofer to profit at the expense of traders who believed the orders were real. Markets must reflect genuine supply and demand.",
    example: "In 2015, the DOJ charged Navinder Singh Sarao with spoofing in the E-mini S&P 500 futures market. His activity contributed to the 2010 Flash Crash.",
    detection: "We track large orders that are placed and quickly cancelled (high cancel rates). In equity markets (P1), we look for bursts of cancellations within short time windows.",
    regulations: ["Dodd-Frank Act \u00a7747", "SEC Rule 10b-5", "MiFID II Article 12"],
  },
  {
    id: "layering",
    title: "Layering",
    icon: <Layers className="h-5 w-5" />,
    color: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    category: "manipulation",
    what: "A more sophisticated form of spoofing. The trader places multiple non-genuine orders at different price levels (creating \u201clayers\u201d) to create the appearance of depth in the order book, then executes a real trade on the other side.",
    why: "Same as spoofing \u2014 it artificially distorts the order book and misleads other market participants about true supply and demand.",
    example: "In 2018, the SEC fined a trading firm $1.4 million for layering in U.S. equity markets.",
    detection: "We look for chains of orders (often 3+ within a short window) on the same side that are later cancelled after a real trade executes on the opposite side.",
    regulations: ["Dodd-Frank Act \u00a7747", "SEC Rule 10b-5"],
  },
  {
    id: "pump-and-dump",
    title: "Pump and Dump",
    icon: <TrendingUp className="h-5 w-5" />,
    color: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
    category: "manipulation",
    what: "A group of traders accumulates a position in a low-volume asset, then artificially inflates the price through coordinated buying (\u201cpump\u201d). Once the price rises, they sell their holdings at the inflated price (\u201cdump\u201d), crashing the market and leaving other traders with losses.",
    why: "It is securities fraud. The pumpers deceive other market participants by creating false price momentum.",
    example: "Crypto \u201cpump-and-dump\u201d groups on Telegram coordinate buying of small-cap tokens. The SEC has charged numerous individuals for pump-and-dump schemes in penny stocks.",
    detection: "We identify bars (time periods) where price rises sharply on concentrated buying, followed by rapid selling. We use a trimmed approach that filters out noise and focuses on statistically significant price swings.",
    regulations: ["SEC Rule 10b-5", "Securities Act \u00a717(a)", "MiCA (EU crypto regulation)"],
  },
  {
    id: "ramping",
    title: "Ramping",
    icon: <ArrowUpDown className="h-5 w-5" />,
    color: "bg-purple-500/15 text-purple-700 dark:text-purple-300",
    category: "manipulation",
    what: "A trader places a series of progressively higher buy orders to push the price upward (or progressively lower sell orders to push it down). Unlike pump-and-dump, ramping may involve a single actor incrementally moving the price.",
    why: "It creates artificial price trends that mislead other traders into believing there is genuine directional momentum.",
    example: "Common in illiquid crypto markets where a single large trader can materially impact price by placing a sequence of incrementally larger orders over a short window.",
    detection: "We look for sequences of trades from the same wallet where each trade occurs at a higher price than the previous one, with the final trade being a sell at the inflated level.",
    regulations: ["SEC Rule 10b-5", "Market Abuse Regulation (EU)"],
  },
  {
    id: "aml-structuring",
    title: "AML Structuring",
    icon: <Landmark className="h-5 w-5" />,
    color: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
    category: "structural",
    what: "Anti-Money Laundering structuring (also called \u201csmurfing\u201d) involves breaking up large financial transactions into smaller ones to avoid triggering regulatory reporting thresholds. For example, instead of transferring $50,000 at once (which would trigger a Currency Transaction Report), a person might make 10 transfers of $4,900.",
    why: "It is a federal crime designed to evade the Bank Secrecy Act\u2019s reporting requirements. Even if the underlying money is legitimate, the act of structuring itself is illegal.",
    example: "In 2023, Binance was fined $4.3 billion for AML compliance failures, including failing to detect structuring patterns.",
    detection: "We cluster trades by wallet and time window, looking for multiple transactions just below round-number thresholds that together exceed a significant amount.",
    regulations: ["Bank Secrecy Act (BSA)", "FinCEN regulations", "Anti-Money Laundering Directives (EU)"],
  },
  {
    id: "peg-manipulation",
    title: "Peg Manipulation",
    icon: <DollarSign className="h-5 w-5" />,
    color: "bg-teal-500/15 text-teal-700 dark:text-teal-300",
    category: "structural",
    what: "Stablecoins like USDC are designed to maintain a 1:1 peg with the U.S. dollar. Peg manipulation involves trading activity that deliberately moves a stablecoin\u2019s price away from its peg, profiting from the temporary deviation.",
    why: "It undermines the fundamental guarantee of stablecoins and can cause cascading losses across DeFi protocols.",
    example: "During the UST/LUNA collapse in May 2022, deliberate selling pressure broke the algorithmic peg, resulting in $40 billion in losses.",
    detection: "We monitor USDC trades and flag bars where the price deviates significantly from the expected $1.00 peg.",
    regulations: ["MiCA (Title III \u2014 stablecoin regulation)", "SEC Rule 10b-5 (potential application)"],
  },
  {
    id: "order-book-imbalance",
    title: "Order Book Imbalance (OBI)",
    icon: <BarChart3 className="h-5 w-5" />,
    color: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
    category: "structural",
    what: "Order Book Imbalance measures the ratio between buy-side and sell-side depth in the order book. A high OBI means there are significantly more bids than asks (or vice versa). While OBI itself isn\u2019t illegal, extreme and sustained imbalances can indicate manipulation.",
    why: "Persistent extreme imbalance suggests someone is artificially loading one side of the book to create directional pressure or prepare for a large execution.",
    example: "Before a large institutional sell-off, the order book may show extreme buy-side concentration that vanishes once the selling begins.",
    detection: "We compute rolling 30-minute z-scores of OBI. Sustained extreme z-scores (indicating the order book is consistently one-sided) trigger alerts. We also check bid concentration and spread anomalies.",
    regulations: ["SEC market structure rules", "Exchange surveillance requirements"],
  },
  {
    id: "pre-announcement-drift",
    title: "Pre-Announcement Drift",
    icon: <Activity className="h-5 w-5" />,
    color: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-300",
    category: "insider",
    what: "Stock prices sometimes move suspiciously before a public announcement (like an earnings report or leadership change). This can indicate insider trading \u2014 someone with non-public knowledge is trading before the news is public.",
    why: "Insider trading is one of the most serious securities offenses. It undermines market fairness and erodes public trust in financial systems.",
    example: "In 2023, the SEC charged multiple corporate insiders for trading ahead of merger announcements, generating millions in illegal profits.",
    detection: "We pull 8-K filings from the SEC EDGAR database, identify the filing date, then analyze price and volume patterns in the days before the announcement. Significant abnormal returns or volume spikes trigger a drift flag.",
    regulations: ["SEC Rule 10b-5", "Insider Trading Sanctions Act", "Insider Trading and Securities Fraud Enforcement Act"],
  },
];

/* ------------------------------------------------------------------ */
/*  Regulation data                                                   */
/* ------------------------------------------------------------------ */

type Regulation = {
  id: string;
  name: string;
  year: string;
  summary: string;
  relevance: string;
};

const REGULATIONS: Regulation[] = [
  {
    id: "dodd-frank",
    name: "Dodd-Frank Wall Street Reform Act",
    year: "2010",
    summary: "Enacted after the 2008 financial crisis, Dodd-Frank introduced sweeping reforms to U.S. financial regulation. Section 747 specifically addresses market manipulation, making spoofing and disruptive trading practices illegal in commodity and derivatives markets.",
    relevance: "Gives the CFTC authority to prosecute manipulative and deceptive practices. Our spoofing and layering detectors directly target violations of \u00a7747.",
  },
  {
    id: "bsa-aml",
    name: "Bank Secrecy Act (BSA) / Anti-Money Laundering",
    year: "1970 / ongoing",
    summary: "The BSA requires financial institutions to assist government agencies in detecting and preventing money laundering. Key requirements include Currency Transaction Reports (CTRs) for transactions over $10,000, Suspicious Activity Reports (SARs), and Know Your Customer (KYC) programs.",
    relevance: "Our AML structuring detection directly addresses the BSA\u2019s concern about transaction structuring to evade reporting thresholds.",
  },
  {
    id: "sec-10b5",
    name: "SEC Rule 10b-5",
    year: "1942",
    summary: "The primary anti-fraud rule under U.S. securities law. It prohibits: employment of any device, scheme, or artifice to defraud; making untrue statements of material fact; and engaging in any practice that operates as fraud or deceit upon any person.",
    relevance: "Wash trading, spoofing, layering, pump-and-dump, and insider trading all violate Rule 10b-5. It\u2019s the foundation of most of our detection logic.",
  },
  {
    id: "mica",
    name: "Markets in Crypto-Assets Regulation (MiCA)",
    year: "2024",
    summary: "The EU\u2019s comprehensive framework for crypto asset regulation. MiCA introduces market abuse provisions specifically for crypto markets (Title VI), stablecoin regulation (Title III), and requirements for crypto-asset service providers to implement surveillance systems.",
    relevance: "Directly relevant to our peg manipulation and crypto market abuse detection. MiCA makes our system\u2019s capabilities a regulatory requirement in the EU.",
  },
  {
    id: "insider-trading-acts",
    name: "Insider Trading Sanctions Act / ITSFEA",
    year: "1984 / 1988",
    summary: "These acts strengthen penalties for insider trading and establish liability for firms that fail to prevent it. Penalties include up to 3x the profit gained or loss avoided, plus criminal sanctions.",
    relevance: "Our P2 pre-announcement drift detection helps identify potential insider trading by flagging abnormal price movements before public disclosures.",
  },
];

/* ------------------------------------------------------------------ */
/*  Expandable glossary card                                          */
/* ------------------------------------------------------------------ */

function GlossaryCard({ entry }: { entry: GlossaryEntry }) {
  const [open, setOpen] = useState(false);

  return (
    <Card
      className={cn(
        "transition-all cursor-pointer",
        open && "ring-2 ring-ring/20"
      )}
      onClick={() => setOpen(!open)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className={cn("rounded-lg p-2.5", entry.color)}>
              {entry.icon}
            </span>
            <div>
              <CardTitle className="text-base">{entry.title}</CardTitle>
              <CardDescription className="mt-0.5">
                <Badge variant="outline" className="text-[10px] capitalize">
                  {entry.category}
                </Badge>
              </CardDescription>
            </div>
          </div>
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground mt-1" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground mt-1" />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground leading-relaxed">
          {entry.what}
        </p>

        {open && (
          <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="rounded-lg border bg-destructive/5 p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-destructive mb-1">
                Why It Is Illegal
              </h4>
              <p className="text-sm leading-relaxed">{entry.why}</p>
            </div>

            <div className="rounded-lg border bg-muted/30 p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Real-World Example
              </h4>
              <p className="text-sm leading-relaxed">{entry.example}</p>
            </div>

            <div className="rounded-lg border bg-primary/5 p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-primary mb-1">
                How We Detect It
              </h4>
              <p className="text-sm leading-relaxed">{entry.detection}</p>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Regulations Violated
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {entry.regulations.map((r) => (
                  <Badge key={r} variant="secondary" className="text-xs">
                    {r}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default function KnowledgeBasePage() {
  const [search, setSearch] = useState("");

  const filtered = GLOSSARY.filter((g) => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (
      g.title.toLowerCase().includes(q) ||
      g.what.toLowerCase().includes(q) ||
      g.category.toLowerCase().includes(q) ||
      g.regulations.some((r) => r.toLowerCase().includes(q))
    );
  });

  const categories = [
    { key: "all", label: "All Types" },
    { key: "manipulation", label: "Market Manipulation" },
    { key: "structural", label: "Structural / AML" },
    { key: "insider", label: "Insider Trading" },
  ];

  const [category, setCategory] = useState("all");

  const visible = filtered.filter(
    (g) => category === "all" || g.category === category
  );

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <BookOpen className="h-6 w-6" />
          Knowledge Base
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Comprehensive guide to market manipulation types, detection methods,
          and regulatory frameworks. Click any card to expand full details.
        </p>
      </div>

      <Tabs defaultValue="glossary">
        <TabsList>
          <TabsTrigger value="glossary">Violation Types</TabsTrigger>
          <TabsTrigger value="regulations">Regulatory Framework</TabsTrigger>
          <TabsTrigger value="pipeline">How Detection Works</TabsTrigger>
        </TabsList>

        {/* ---- Tab 1: Glossary ---- */}
        <TabsContent value="glossary" className="space-y-6 pt-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-1.5">
              {categories.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setCategory(c.key)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                    category === c.key
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:bg-accent"
                  )}
                >
                  {c.label}
                </button>
              ))}
            </div>
            <div className="relative max-w-xs">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search violations..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {visible.length === 0 ? (
            <div className="rounded-md border border-dashed bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground">
              No violations match your search.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {visible.map((entry) => (
                <GlossaryCard key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* ---- Tab 2: Regulations ---- */}
        <TabsContent value="regulations" className="space-y-4 pt-4">
          <p className="text-sm text-muted-foreground">
            Key regulatory frameworks that govern the types of market abuse this
            system detects. Understanding these helps explain why each detection
            matters.
          </p>

          <div className="space-y-4">
            {REGULATIONS.map((reg) => (
              <Card key={reg.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-3">
                    <span className="rounded-lg bg-primary/10 p-2.5 text-primary">
                      <Scale className="h-5 w-5" />
                    </span>
                    <div>
                      <CardTitle className="text-base">{reg.name}</CardTitle>
                      <CardDescription>{reg.year}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm leading-relaxed">{reg.summary}</p>
                  <div className="rounded-lg border bg-primary/5 p-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-primary mb-1">
                      Relevance to This System
                    </h4>
                    <p className="text-sm leading-relaxed">{reg.relevance}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* ---- Tab 3: Pipeline overview ---- */}
        <TabsContent value="pipeline" className="space-y-6 pt-4">
          <p className="text-sm text-muted-foreground">
            Our detection system uses a multi-layered approach: no single method
            is trusted alone. Instead, three independent approaches vote on each
            trade.
          </p>

          <div className="space-y-4">
            {[
              {
                step: 1,
                title: "Rule-Based Detection",
                color: "bg-amber-500",
                desc: "Hand-crafted heuristics scan every trade record using statistical thresholds. Fast, interpretable, and deterministic. Detects 8 violation types across crypto and equity markets.",
                strengths: ["Fast execution", "Fully interpretable", "No API dependency"],
                weaknesses: ["Fixed thresholds miss evolving patterns", "Some rules over-flag (e.g., pump-and-dump has ~90% false positive rate)"],
              },
              {
                step: 2,
                title: "AI Ground Truth (LLM)",
                color: "bg-purple-500",
                desc: "A large language model independently evaluates every trade in context \u2014 price, volume, wallet, surrounding bar data. Provides verdicts (suspicious/benign/uncertain) with confidence scores and reasoning.",
                strengths: ["Catches structuring and ramping that rules miss", "Contextual reasoning", "Confidence calibration"],
                weaknesses: ["API latency and cost", "Occasional hallucination", "Requires manual verification"],
              },
              {
                step: 3,
                title: "Comparison + ML Re-Ranker",
                color: "bg-rose-500",
                desc: "The comparison engine aligns rule flags against AI verdicts. A Gradient Boosting classifier then learns which patterns of agreement/disagreement predict true positives \u2014 it\u2019s a meta-learner over the other two approaches.",
                strengths: ["Learns from both approaches", "Calibrated probability scores", "Identifies reliable vs noisy rule detectors"],
                weaknesses: ["Requires both rule and AI outputs as input", "Training data quality depends on AI accuracy"],
              },
              {
                step: 4,
                title: "Committee Fusion (Three-Way Vote)",
                color: "bg-indigo-500",
                desc: "The final stage combines all three sources in a tiered voting system. Trades flagged by 2+ methods (Tier 1) are auto-included. Single-source flags (Tier 2) are triaged using per-violation-type confidence thresholds.",
                strengths: ["Highest precision output", "Configurable thresholds", "Maximizes true positives while minimizing noise"],
                weaknesses: ["Complexity", "Depends on all upstream stages running"],
              },
            ].map(({ step, title, color, desc, strengths, weaknesses }) => (
              <Card key={step}>
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold text-white",
                        color
                      )}
                    >
                      {step}
                    </span>
                    <CardTitle className="text-base">{title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {desc}
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border bg-emerald-500/5 p-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-1.5">
                        Strengths
                      </h4>
                      <ul className="space-y-1 text-sm">
                        {strengths.map((s) => (
                          <li key={s} className="flex items-start gap-2">
                            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                            <span>{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="rounded-lg border bg-red-500/5 p-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-red-700 dark:text-red-400 mb-1.5">
                        Limitations
                      </h4>
                      <ul className="space-y-1 text-sm">
                        {weaknesses.map((w) => (
                          <li key={w} className="flex items-start gap-2">
                            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600 dark:text-red-400" />
                            <span>{w}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
