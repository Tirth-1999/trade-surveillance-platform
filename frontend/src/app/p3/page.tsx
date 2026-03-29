"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown, ChevronRight, Download, Loader2 } from "lucide-react";
import { fetchJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type TradeRow = {
  symbol: string;
  date: string;
  trade_id: string;
  violation_type: string;
  remarks: string;
  wallet_id?: string;
  trader_id?: string;
  timestamp?: string;
  side?: string;
  order_type?: string;
  price?: string;
  quantity?: string;
  notional_usdt?: string;
};

export type Pass2AuditRow = {
  trade_id: string;
  violation_type: string;
  decision: string;
  reason: string;
};

function normalizePass2Audit(raw: unknown): Pass2AuditRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((r) => {
    const o = r as Record<string, unknown>;
    return {
      trade_id: String(o.trade_id ?? ""),
      violation_type: String(o.violation_type ?? ""),
      decision: String(o.decision ?? ""),
      reason: String(o.reason ?? ""),
    };
  });
}

const BAR_COLORS = [
  "#3b82f6",
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
];

function str(o: Record<string, unknown>, k: string): string | undefined {
  if (!(k in o)) return undefined;
  const v = o[k];
  if (v === null || v === undefined || v === "") return undefined;
  return String(v);
}

function normalizeRows(raw: unknown): TradeRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((r) => {
    const o = r as Record<string, unknown>;
    return {
      symbol: String(o.symbol ?? ""),
      date: String(o.date ?? ""),
      trade_id: String(o.trade_id ?? ""),
      violation_type: String(o.violation_type ?? ""),
      remarks: String(o.remarks ?? ""),
      wallet_id: str(o, "wallet_id"),
      trader_id: str(o, "trader_id"),
      timestamp: str(o, "timestamp"),
      side: str(o, "side"),
      order_type: str(o, "order_type"),
      price: str(o, "price"),
      quantity: str(o, "quantity"),
      notional_usdt: str(o, "notional_usdt"),
    };
  });
}

function dateRangeLabel(dates: string[]): string {
  if (dates.length === 0) return "—";
  const parsed = dates
    .map((d) => new Date(d).getTime())
    .filter((t) => !Number.isNaN(t));
  if (parsed.length === 0) {
    const sorted = [...dates].sort();
    return `${sorted[0]} – ${sorted[sorted.length - 1]}`;
  }
  const min = new Date(Math.min(...parsed));
  const max = new Date(Math.max(...parsed));
  return `${min.toLocaleDateString()} – ${max.toLocaleDateString()}`;
}

function escapeCsvField(s: string): string {
  return `"${String(s).replace(/"/g, '""')}"`;
}

function downloadCsv(rows: TradeRow[], filenameSuffix: string) {
  const headers = ["symbol", "date", "trade_id", "violation_type", "remarks"];
  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      [
        r.symbol,
        r.date,
        r.trade_id,
        r.violation_type,
        r.remarks,
      ]
        .map(escapeCsvField)
        .join(",")
    ),
  ];
  const blob = new Blob([lines.join("\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `p3-surveillance-${filenameSuffix}-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const DETAIL_HEADERS = [
  "symbol",
  "date",
  "trade_id",
  "violation_type",
  "remarks",
  "wallet_id",
  "trader_id",
  "timestamp",
  "side",
  "order_type",
  "price",
  "quantity",
  "notional_usdt",
] as const;

type DetailHeader = (typeof DETAIL_HEADERS)[number];

function detailValues(r: TradeRow): Record<DetailHeader, string> {
  return {
    symbol: r.symbol,
    date: r.date,
    trade_id: r.trade_id,
    violation_type: r.violation_type,
    remarks: r.remarks,
    wallet_id: r.wallet_id ?? "",
    trader_id: r.trader_id ?? "",
    timestamp: r.timestamp ?? "",
    side: r.side ?? "",
    order_type: r.order_type ?? "",
    price: r.price ?? "",
    quantity: r.quantity ?? "",
    notional_usdt: r.notional_usdt ?? "",
  };
}

function downloadCsvWithTradeDetails(rows: TradeRow[], filenameSuffix: string) {
  const lines = [
    DETAIL_HEADERS.join(","),
    ...rows.map((r) =>
      DETAIL_HEADERS.map((h) => escapeCsvField(detailValues(r)[h])).join(",")
    ),
  ];
  const blob = new Blob([lines.join("\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `p3-surveillance-${filenameSuffix}-with-tape-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

async function fetchSubmissionForTab(
  tab: "rules" | "committee"
): Promise<unknown> {
  const enriched =
    tab === "rules"
      ? "/api/outputs/submission_with_trades"
      : "/api/outputs/submission_committee_with_trades";
  const base =
    tab === "rules"
      ? "/api/outputs/submission"
      : "/api/outputs/submission_committee";
  try {
    return await fetchJSON<unknown>(enriched);
  } catch {
    return fetchJSON<unknown>(base);
  }
}

export default function P3Page() {
  const [tab, setTab] = React.useState<"rules" | "committee">("rules");
  const [rows, setRows] = React.useState<TradeRow[]>([]);
  const [pass2Audit, setPass2Audit] = React.useState<Pass2AuditRow[] | null>(
    null
  );
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [symbolFilter, setSymbolFilter] = React.useState("");
  const [tradeIdQuery, setTradeIdQuery] = React.useState("");
  const [walletQuery, setWalletQuery] = React.useState("");
  const [expanded, setExpanded] = React.useState<Set<number>>(() => new Set());

  React.useEffect(() => {
    setSymbolFilter("");
    setTradeIdQuery("");
    setWalletQuery("");
    setExpanded(new Set());
  }, [tab]);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      setPass2Audit(null);
      try {
        const raw = await fetchSubmissionForTab(tab);
        if (!cancelled) setRows(normalizeRows(raw));
        if (tab === "rules") {
          try {
            const aud = await fetchJSON<unknown>("/api/outputs/p3_pass2_audit");
            if (!cancelled) setPass2Audit(normalizePass2Audit(aud));
          } catch {
            if (!cancelled) setPass2Audit(null);
          }
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tab]);

  const pass2Stats = React.useMemo(() => {
    if (pass2Audit === null) return null;
    let kept = 0;
    let dropped = 0;
    for (const r of pass2Audit) {
      const d = (r.decision ?? "").toLowerCase();
      if (d === "dropped") dropped += 1;
      else if (d === "kept") kept += 1;
    }
    return {
      kept,
      dropped,
      droppedRows: pass2Audit.filter((r) => r.decision === "dropped"),
    };
  }, [pass2Audit]);

  const uniqueSymbols = React.useMemo(() => {
    const s = new Set(rows.map((r) => r.symbol).filter(Boolean));
    return Array.from(s).sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const filtered = React.useMemo(() => {
    const q = tradeIdQuery.trim().toLowerCase();
    const wq = walletQuery.trim().toLowerCase();
    return rows.filter((r) => {
      if (symbolFilter && r.symbol !== symbolFilter) return false;
      if (q && !r.trade_id.toLowerCase().includes(q)) return false;
      if (wq) {
        const w = `${r.trader_id ?? ""} ${r.wallet_id ?? ""}`.toLowerCase();
        if (!w.includes(wq)) return false;
      }
      return true;
    });
  }, [rows, symbolFilter, tradeIdQuery, walletQuery]);

  const violationChart = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of filtered) {
      const key = r.violation_type || "(none)";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries()).map(([name, count]) => ({
      name,
      count,
    }));
  }, [filtered]);

  const statSymbols = React.useMemo(() => {
    return new Set(filtered.map((r) => r.symbol).filter(Boolean)).size;
  }, [filtered]);

  const statViolationTypes = React.useMemo(() => {
    return new Set(filtered.map((r) => r.violation_type).filter(Boolean)).size;
  }, [filtered]);

  const rangeLabel = React.useMemo(
    () => dateRangeLabel(filtered.map((r) => r.date)),
    [filtered]
  );

  function toggleRow(i: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            P3 — Crypto Trade Surveillance
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Rule-based and committee outputs from the FastAPI backend. The Rules tab
            reflects <span className="font-medium text-foreground">Pass 2</span>{" "}
            confirmation when you run <code className="rounded bg-muted px-1 py-0.5 text-xs">run.py p3</code>{" "}
            (<code className="rounded bg-muted px-1 py-0.5 text-xs">p3.pass2</code> in{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">config.yaml</code>
            ). When trade tape is available, wallet, side, order type, and timestamps
            are shown for analysis only — exports default to the competition CSV
            schema.
          </p>
        </div>
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as "rules" | "committee")}
          className="w-full sm:w-auto"
        >
          <TabsList className="grid w-full grid-cols-2 sm:inline-flex sm:w-auto">
            <TabsTrigger value="rules">Rules</TabsTrigger>
            <TabsTrigger value="committee">Committee</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {loading && (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/30 py-16 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
          <p className="text-sm font-medium">Loading surveillance data…</p>
        </div>
      )}

      {!loading && error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-destructive">
              Could not load data
            </CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      )}

      {!loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total flags</CardDescription>
                <CardTitle className="text-3xl tabular-nums">
                  {filtered.length}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Symbols</CardDescription>
                <CardTitle className="text-3xl tabular-nums">
                  {statSymbols}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Violation types</CardDescription>
                <CardTitle className="text-3xl tabular-nums">
                  {statViolationTypes}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Date range</CardDescription>
                <CardTitle className="text-lg font-semibold leading-snug">
                  {rangeLabel}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {tab === "rules" && pass2Stats && (
            <Card className="border-primary/20 bg-primary/[0.03]">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Pass 2 — detector confirmation</CardTitle>
                <CardDescription>
                  Each candidate row is checked against the same detector family as
                  the official <code className="text-xs">violation_type</code> (stricter
                  peg/spoof thresholds optional). Rows below were{" "}
                  <span className="font-medium text-foreground">dropped</span> from{" "}
                  <code className="text-xs">submission.csv</code>. Full log:{" "}
                  <code className="text-xs">outputs/p3_second_pass_audit.csv</code>.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-3">
                <Badge
                  variant="outline"
                  className="border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
                >
                  kept {pass2Stats.kept}
                </Badge>
                <Badge
                  variant="outline"
                  className={
                    pass2Stats.dropped > 0
                      ? "border-amber-500/50 bg-amber-500/10 text-amber-950 dark:text-amber-200"
                      : ""
                  }
                >
                  dropped {pass2Stats.dropped}
                </Badge>
              </CardContent>
              {pass2Stats.droppedRows.length > 0 && (
                <CardContent className="pt-0">
                  <p className="mb-2 text-sm font-medium text-muted-foreground">
                    Dropped rows
                  </p>
                  <ScrollArea className="h-[min(220px,40vh)] rounded-md border">
                    <table className="w-full text-left text-sm">
                      <thead className="sticky top-0 border-b bg-muted/80 backdrop-blur-sm">
                        <tr>
                          <th className="p-2 font-medium">trade_id</th>
                          <th className="p-2 font-medium">violation_type</th>
                          <th className="p-2 font-medium">reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pass2Stats.droppedRows.map((r, i) => (
                          <tr
                            key={`${r.trade_id}-${i}`}
                            className="border-b border-border/50 last:border-0"
                          >
                            <td className="p-2 font-mono text-xs">{r.trade_id}</td>
                            <td className="p-2">{r.violation_type}</td>
                            <td className="p-2 text-muted-foreground">{r.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollArea>
                </CardContent>
              )}
            </Card>
          )}

          {tab === "rules" && !loading && !error && pass2Audit === null && (
            <p className="text-sm text-muted-foreground">
              No Pass 2 audit file found. Generate it by running the P3 pipeline with{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                p3.pass2.write_audit: true
              </code>{" "}
              and sync static data if needed:{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                python3 scripts/sync_frontend_data.py
              </code>
              .
            </p>
          )}

          {tab === "committee" && !loading && !error && (
            <p className="text-sm text-muted-foreground">
              Committee fusion builds on the rules submission (Pass 2–filtered when{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">p3.pass2.enabled</code>{" "}
              is on), plus AI and ML. Switch to Rules to view the Pass 2 audit table.
            </p>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Violation type distribution</CardTitle>
              <CardDescription>
                Counts for the trades currently shown (after filters).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {violationChart.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  No data to chart.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={violationChart}
                    margin={{ top: 8, right: 16, left: 0, bottom: 48 }}
                  >
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11 }}
                      interval={0}
                      angle={-28}
                      textAnchor="end"
                      height={56}
                    />
                    <YAxis allowDecimals={false} width={40} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "8px",
                        border: "1px solid hsl(var(--border))",
                      }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48}>
                      {violationChart.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={BAR_COLORS[index % BAR_COLORS.length]}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="space-y-2">
                <label
                  htmlFor="p3-symbol"
                  className="text-sm font-medium text-foreground"
                >
                  Symbol
                </label>
                <select
                  id="p3-symbol"
                  className={cn(
                    "flex h-10 w-full min-w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm",
                    "ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  )}
                  value={symbolFilter}
                  onChange={(e) => setSymbolFilter(e.target.value)}
                >
                  <option value="">All symbols</option>
                  {uniqueSymbols.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2 sm:min-w-[220px]">
                <label
                  htmlFor="p3-trade-id"
                  className="text-sm font-medium text-foreground"
                >
                  Trade ID
                </label>
                <Input
                  id="p3-trade-id"
                  placeholder="Search trade_id…"
                  value={tradeIdQuery}
                  onChange={(e) => setTradeIdQuery(e.target.value)}
                />
              </div>
              <div className="space-y-2 sm:min-w-[200px]">
                <label
                  htmlFor="p3-wallet"
                  className="text-sm font-medium text-foreground"
                >
                  Wallet
                </label>
                <Input
                  id="p3-wallet"
                  placeholder="Contains wallet / trader_id…"
                  value={walletQuery}
                  onChange={(e) => setWalletQuery(e.target.value)}
                />
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                onClick={() =>
                  downloadCsv(filtered, tab === "rules" ? "rules" : "committee")
                }
                disabled={filtered.length === 0}
                title="symbol, date, trade_id, violation_type, remarks only"
              >
                <Download className="h-4 w-4" aria-hidden />
                Export CSV (submission)
              </Button>
              <Button
                type="button"
                variant="secondary"
                className="gap-2"
                onClick={() =>
                  downloadCsvWithTradeDetails(
                    filtered,
                    tab === "rules" ? "rules" : "committee"
                  )
                }
                disabled={filtered.length === 0}
              >
                <Download className="h-4 w-4" aria-hidden />
                Export with tape
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
              <div>
                <CardTitle className="text-lg">Flagged trades</CardTitle>
                <CardDescription>
                  Click a row to expand full remarks. Showing {filtered.length}{" "}
                  row{filtered.length === 1 ? "" : "s"}.
                </CardDescription>
              </div>
              {filtered.length > 0 && (
                <Badge variant="secondary">{tab === "rules" ? "Rules" : "Committee"}</Badge>
              )}
            </CardHeader>
            <CardContent className="p-0 sm:px-6 sm:pb-6">
              {filtered.length === 0 ? (
                <p className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No trades match the current filters.
                </p>
              ) : (
                <ScrollArea className="max-h-[min(520px,60vh)] rounded-md border">
                  <table className="w-full min-w-[880px] caption-bottom text-sm">
                    <thead className="sticky top-0 z-10 border-b bg-muted/80 backdrop-blur">
                      <tr className="text-left">
                        <th className="w-8 p-3" aria-hidden />
                        <th className="p-3 font-medium">Symbol</th>
                        <th className="p-3 font-medium">Date</th>
                        <th className="p-3 font-medium">Trade ID</th>
                        <th className="p-3 font-medium">Violation type</th>
                        <th className="p-3 font-medium">Remarks</th>
                        <th className="p-3 font-medium">Wallet</th>
                        <th className="p-3 font-medium">Side</th>
                        <th className="p-3 font-medium">Order type</th>
                        <th className="p-3 font-medium">Tape time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((row, i) => {
                        const open = expanded.has(i);
                        const preview =
                          row.remarks.length > 80
                            ? `${row.remarks.slice(0, 80)}…`
                            : row.remarks;
                        const wallet =
                          row.trader_id || row.wallet_id || "—";
                        return (
                          <React.Fragment key={`${row.trade_id}-${i}`}>
                            <tr
                              className={cn(
                                "cursor-pointer border-b transition-colors hover:bg-muted/50",
                                open && "bg-muted/30"
                              )}
                              onClick={() => toggleRow(i)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  toggleRow(i);
                                }
                              }}
                              tabIndex={0}
                              role="button"
                              aria-expanded={open}
                            >
                              <td className="p-3 text-muted-foreground">
                                {open ? (
                                  <ChevronDown className="h-4 w-4" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                              </td>
                              <td className="p-3 font-medium">{row.symbol}</td>
                              <td className="p-3 whitespace-nowrap text-muted-foreground">
                                {row.date}
                              </td>
                              <td className="p-3 font-mono text-xs">
                                {row.trade_id}
                              </td>
                              <td className="p-3">
                                <Badge variant="outline" className="font-normal">
                                  {row.violation_type || "—"}
                                </Badge>
                              </td>
                              <td className="max-w-[220px] p-3 text-muted-foreground">
                                <span className="line-clamp-2">
                                  {preview || "—"}
                                </span>
                              </td>
                              <td
                                className="max-w-[140px] p-3 font-mono text-xs text-muted-foreground"
                                title={wallet}
                              >
                                <span className="line-clamp-2">{wallet}</span>
                              </td>
                              <td className="p-3 text-muted-foreground">
                                {row.side || "—"}
                              </td>
                              <td className="p-3 text-muted-foreground">
                                {row.order_type || "—"}
                              </td>
                              <td className="whitespace-nowrap p-3 text-muted-foreground">
                                {row.timestamp || "—"}
                              </td>
                            </tr>
                            {open && (
                              <tr className="border-b bg-muted/20">
                                <td />
                                <td colSpan={9} className="px-3 pb-4 pt-0">
                                  <div className="space-y-4">
                                    <div className="rounded-md border bg-background p-4 text-sm leading-relaxed">
                                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        Full remarks
                                      </p>
                                      <p className="mt-2 whitespace-pre-wrap">
                                        {row.remarks || "—"}
                                      </p>
                                    </div>
                                    {(row.price ||
                                      row.quantity ||
                                      row.notional_usdt) && (
                                      <div className="rounded-md border bg-background p-4 text-sm">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                          Trade tape
                                        </p>
                                        <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                                          {row.price ? (
                                            <>
                                              <dt className="text-muted-foreground">
                                                Price
                                              </dt>
                                              <dd className="font-mono">
                                                {row.price}
                                              </dd>
                                            </>
                                          ) : null}
                                          {row.quantity ? (
                                            <>
                                              <dt className="text-muted-foreground">
                                                Quantity
                                              </dt>
                                              <dd className="font-mono">
                                                {row.quantity}
                                              </dd>
                                            </>
                                          ) : null}
                                          {row.notional_usdt ? (
                                            <>
                                              <dt className="text-muted-foreground">
                                                Notional (USDT)
                                              </dt>
                                              <dd className="font-mono">
                                                {row.notional_usdt}
                                              </dd>
                                            </>
                                          ) : null}
                                        </dl>
                                      </div>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
