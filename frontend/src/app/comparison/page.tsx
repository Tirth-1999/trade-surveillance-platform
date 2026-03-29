"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchJSON } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type ComparisonRow = {
  symbol: string;
  date: string;
  trade_id: string;
  rule_flag: number | string;
  gt_flag: number | string;
  agreement: string;
  gt_verdict: string;
  gt_confidence: number | string | null;
  violation_type_rules: string;
  violation_type_gt: string;
  type_match?: boolean | number | string | null;
};

/** Backend CSV uses agreement ∈ both_flag | rules_only | gt_only (not "agree"). Normalize legacy rows. */
function normalizeComparisonRows(raw: unknown[]): ComparisonRow[] {
  return raw.map((item) => {
    const r = item as Record<string, unknown>;
    const agreement = String(r.agreement ?? "");
    let ruleFlag = r.rule_flag;
    let gtFlag = r.gt_flag;
    if (ruleFlag === undefined || gtFlag === undefined) {
      if (agreement === "both_flag") {
        ruleFlag = 1;
        gtFlag = 1;
      } else if (agreement === "rules_only") {
        ruleFlag = 1;
        gtFlag = 0;
      } else if (agreement === "gt_only") {
        ruleFlag = 0;
        gtFlag = 1;
      } else {
        ruleFlag = 0;
        gtFlag = 0;
      }
    }
    const vRules = r.violation_type_rules ?? r.rules_violation_type;
    const vGt = r.violation_type_gt ?? r.gt_violation_type;
    return {
      symbol: String(r.symbol ?? ""),
      date: String(r.date ?? ""),
      trade_id: String(r.trade_id ?? ""),
      rule_flag: ruleFlag as number | string,
      gt_flag: gtFlag as number | string,
      agreement,
      gt_verdict: String(r.gt_verdict ?? ""),
      gt_confidence: (r.gt_confidence as number | string | null) ?? null,
      violation_type_rules: vRules === null || vRules === undefined ? "" : String(vRules),
      violation_type_gt: vGt === null || vGt === undefined ? "" : String(vGt),
      type_match: r.type_match as boolean | number | string | null | undefined,
    };
  });
}

function truthyTypeMatch(v: boolean | number | string | null | undefined): boolean {
  if (v === true || v === 1) return true;
  if (typeof v === "string") {
    const s = v.toLowerCase();
    return s === "true" || s === "1" || s === "yes";
  }
  return false;
}

function flagOn(v: number | string | null | undefined): boolean {
  if (v === null || v === undefined) return false;
  const n = Number(v);
  if (!Number.isNaN(n)) return n === 1;
  const s = String(v).toLowerCase();
  return s === "1" || s === "true" || s === "yes";
}

function filterBySymbol(rows: ComparisonRow[], q: string): ComparisonRow[] {
  const t = q.trim().toLowerCase();
  if (!t) return rows;
  return rows.filter((r) => (r.symbol ?? "").toLowerCase().includes(t));
}

function ComparisonTable({
  rows,
  columns,
}: {
  rows: ComparisonRow[];
  columns: { key: keyof ComparisonRow; label: string }[];
}) {
  if (rows.length === 0) {
    return (
      <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
        No rows match the current filters.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/40 text-left">
            {columns.map((c) => (
              <th key={c.label} className="whitespace-nowrap px-4 py-3 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.trade_id}-${r.date}-${i}`} className="border-b last:border-0">
              {columns.map((c) => {
                const v = r[c.key];
                const display =
                  v === null || v === undefined || v === "" ? "—" : String(v);
                return (
                  <td key={c.label} className="max-w-[220px] truncate px-4 py-2 font-mono text-xs">
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ComparisonPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<ComparisonRow[]>([]);

  const [symbolGtOnly, setSymbolGtOnly] = useState("");
  const [symbolRulesOnly, setSymbolRulesOnly] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchJSON<unknown[]>("/api/outputs/comparison_report");
        if (cancelled) return;
        setRows(Array.isArray(data) ? normalizeComparisonRows(data) : []);
      } catch (e) {
        if (cancelled) return;
        setRows([]);
        setError(e instanceof Error ? e.message : "Failed to load comparison report.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const total = rows.length;
    let bothFlag = 0;
    let rulesOnly = 0;
    let gtOnly = 0;
    let typeMatchAmongBoth = 0;
    for (const r of rows) {
      const a = r.agreement;
      if (a === "both_flag") {
        bothFlag += 1;
        if (truthyTypeMatch(r.type_match)) typeMatchAmongBoth += 1;
      } else if (a === "rules_only") rulesOnly += 1;
      else if (a === "gt_only") gtOnly += 1;
    }
    const typeRate =
      bothFlag > 0 ? Math.round((typeMatchAmongBoth / bothFlag) * 1000) / 10 : null;
    return {
      total,
      bothFlag,
      rulesOnly,
      gtOnly,
      typeMatchAmongBoth,
      typeRate,
    };
  }, [rows]);

  const pieData = useMemo(
    () => [
      { name: "Both flagged", value: stats.bothFlag, fill: "hsl(262 83% 58%)" },
      { name: "Rules only", value: stats.rulesOnly, fill: "hsl(38 92% 50%)" },
      { name: "GT only", value: stats.gtOnly, fill: "hsl(199 89% 48%)" },
    ],
    [stats.bothFlag, stats.gtOnly, stats.rulesOnly]
  );

  const verdictBarData = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) {
      const k = (r.gt_verdict ?? "").trim() || "(empty)";
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([verdict, count]) => ({ verdict, count }))
      .sort((a, b) => b.count - a.count);
  }, [rows]);

  const gtOnlyRows = useMemo(
    () => rows.filter((r) => flagOn(r.gt_flag) && !flagOn(r.rule_flag)),
    [rows]
  );
  const rulesOnlyRows = useMemo(
    () => rows.filter((r) => flagOn(r.rule_flag) && !flagOn(r.gt_flag)),
    [rows]
  );
  const bothAgreeRows = useMemo(
    () => rows.filter((r) => flagOn(r.rule_flag) && flagOn(r.gt_flag)),
    [rows]
  );

  const gtOnlyFiltered = useMemo(
    () => filterBySymbol(gtOnlyRows, symbolGtOnly),
    [gtOnlyRows, symbolGtOnly]
  );
  const rulesOnlyFiltered = useMemo(
    () => filterBySymbol(rulesOnlyRows, symbolRulesOnly),
    [rulesOnlyRows, symbolRulesOnly]
  );
  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        Loading comparison report…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Rule-based vs AI Ground Truth Comparison
        </h1>
        <p className="text-sm text-muted-foreground">
          Each row is a trade where at least one side (rules or ground truth) marked it suspicious;
          benign-vs-benign pairs are omitted. Metrics use backend categories{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">both_flag</code>,{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">rules_only</code>,{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">gt_only</code>. Data from{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/outputs/comparison_report</code>.
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {!error && rows.length === 0 ? (
        <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
          No comparison rows returned. Generate the comparison report in the pipeline first.
        </p>
      ) : null}

      {!error && rows.length > 0 ? (
        <>
          <section className="space-y-4">
            <h2 className="text-lg font-medium">Agreement overview</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total compared
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold tabular-nums">{stats.total}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Both flagged
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold tabular-nums text-violet-600 dark:text-violet-400">
                    {stats.bothFlag}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Rules + GT suspicious</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Rules only
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
                    {stats.rulesOnly}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Not in GT suspicious set</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    GT only
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold tabular-nums text-sky-600 dark:text-sky-400">
                    {stats.gtOnly}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Rules did not flag</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Same violation type
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold tabular-nums">
                    {stats.bothFlag > 0
                      ? `${stats.typeMatchAmongBoth} / ${stats.bothFlag}`
                      : "—"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {stats.typeRate !== null
                      ? `${stats.typeRate}% when both flagged`
                      : "No both-flagged rows"}
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Overlap breakdown</CardTitle>
                  <CardDescription>
                    How rule-based alerts line up with ground-truth suspicious trades
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-[280px] w-full pt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={48}
                        outerRadius={88}
                        paddingAngle={2}
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          borderRadius: 8,
                          border: "1px solid hsl(var(--border))",
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Ground-truth verdict distribution</CardTitle>
                  <CardDescription>Count per unique gt_verdict</CardDescription>
                </CardHeader>
                <CardContent className="h-[280px] w-full pt-2">
                  {verdictBarData.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No verdict values to chart.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={verdictBarData}
                        layout="vertical"
                        margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                      >
                        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                        <YAxis
                          type="category"
                          dataKey="verdict"
                          width={120}
                          tick={{ fontSize: 11 }}
                        />
                        <Tooltip
                          contentStyle={{
                            borderRadius: 8,
                            border: "1px solid hsl(var(--border))",
                          }}
                        />
                        <Bar dataKey="count" name="Count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Drill-downs</h2>
            <Tabs defaultValue="gt-only">
              <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
                <TabsTrigger value="gt-only">GT-only flags</TabsTrigger>
                <TabsTrigger value="rules-only">Rules-only flags</TabsTrigger>
                <TabsTrigger value="both">Both agree</TabsTrigger>
                <TabsTrigger value="all">All data</TabsTrigger>
              </TabsList>

              <TabsContent value="gt-only" className="space-y-3 pt-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    Rows where <Badge variant="outline">gt_flag = 1</Badge> and{" "}
                    <Badge variant="outline">rule_flag = 0</Badge>
                    <span className="ml-2 text-xs">({gtOnlyFiltered.length} shown)</span>
                  </p>
                  <Input
                    className="max-w-xs"
                    placeholder="Filter by symbol"
                    value={symbolGtOnly}
                    onChange={(e) => setSymbolGtOnly(e.target.value)}
                    aria-label="Filter GT-only rows by symbol"
                  />
                </div>
                <ComparisonTable
                  rows={gtOnlyFiltered}
                  columns={[
                    { key: "symbol", label: "Symbol" },
                    { key: "date", label: "Date" },
                    { key: "trade_id", label: "Trade ID" },
                    { key: "gt_verdict", label: "GT verdict" },
                    { key: "gt_confidence", label: "GT confidence" },
                    { key: "violation_type_gt", label: "Violation (GT)" },
                  ]}
                />
              </TabsContent>

              <TabsContent value="rules-only" className="space-y-3 pt-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    Rows where <Badge variant="outline">rule_flag = 1</Badge> and{" "}
                    <Badge variant="outline">gt_flag = 0</Badge>
                    <span className="ml-2 text-xs">({rulesOnlyFiltered.length} shown)</span>
                  </p>
                  <Input
                    className="max-w-xs"
                    placeholder="Filter by symbol"
                    value={symbolRulesOnly}
                    onChange={(e) => setSymbolRulesOnly(e.target.value)}
                    aria-label="Filter rules-only rows by symbol"
                  />
                </div>
                <ComparisonTable
                  rows={rulesOnlyFiltered}
                  columns={[
                    { key: "symbol", label: "Symbol" },
                    { key: "date", label: "Date" },
                    { key: "trade_id", label: "Trade ID" },
                    { key: "violation_type_rules", label: "Violation (rules)" },
                  ]}
                />
              </TabsContent>

              <TabsContent value="both" className="space-y-3 pt-4">
                <p className="text-sm text-muted-foreground">
                  Rows where both <Badge variant="outline">rule_flag = 1</Badge> and{" "}
                  <Badge variant="outline">gt_flag = 1</Badge>
                  <span className="ml-2 text-xs">({bothAgreeRows.length} rows)</span>
                </p>
                <ComparisonTable
                  rows={bothAgreeRows}
                  columns={[
                    { key: "symbol", label: "Symbol" },
                    { key: "date", label: "Date" },
                    { key: "trade_id", label: "Trade ID" },
                    { key: "gt_verdict", label: "GT verdict" },
                    { key: "violation_type_rules", label: "Violation (rules)" },
                    { key: "violation_type_gt", label: "Violation (GT)" },
                    { key: "type_match", label: "Type match" },
                    { key: "agreement", label: "Category" },
                  ]}
                />
              </TabsContent>

              <TabsContent value="all" className="space-y-3 pt-4">
                <p className="text-sm text-muted-foreground">
                  Full comparison export
                  <span className="ml-2 text-xs">({rows.length} rows)</span>
                </p>
                <ComparisonTable
                  rows={rows}
                  columns={[
                    { key: "symbol", label: "Symbol" },
                    { key: "date", label: "Date" },
                    { key: "trade_id", label: "Trade ID" },
                    { key: "rule_flag", label: "Rule flag" },
                    { key: "gt_flag", label: "GT flag" },
                    { key: "agreement", label: "Agreement" },
                    { key: "gt_verdict", label: "GT verdict" },
                    { key: "gt_confidence", label: "GT confidence" },
                    { key: "violation_type_rules", label: "Violation (rules)" },
                    { key: "violation_type_gt", label: "Violation (GT)" },
                  ]}
                />
              </TabsContent>
            </Tabs>
          </section>
        </>
      ) : null}
    </div>
  );
}
