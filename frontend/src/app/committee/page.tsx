"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type CommitteeReport = { text: string };
type CommitteeRow = {
  symbol: string;
  date: string;
  trade_id: string;
  violation_type: string;
  remarks: string;
};

type ZoneCard = {
  name: string;
  count: number;
  tier: 1 | 2 | "total";
  detail?: string;
};

type MlHealth = {
  artifacts_dir?: string;
  stage1?: Record<string, unknown> | null;
  stage2?: Record<string, unknown> | null;
  stage1_previous?: Record<string, unknown> | null;
  evaluation_report_preview?: string | null;
  artifacts_present?: { stage1?: boolean; stage2?: boolean };
};

const TIER1_NAMES = new Set([
  "All 3 agree",
  "Rules + AI",
  "Rules + ML",
  "AI + ML",
]);

const CHART_COLORS = [
  "hsl(var(--primary))",
  "hsl(199 89% 48%)",
  "hsl(142 71% 45%)",
  "hsl(47 96% 53%)",
  "hsl(280 65% 60%)",
  "hsl(24 95% 53%)",
  "hsl(340 75% 55%)",
  "hsl(200 80% 50%)",
];

async function tryFetchJSON<T>(path: string): Promise<T | null> {
  try {
    return await fetchJSON<T>(path);
  } catch {
    return null;
  }
}

function parseZoneBreakdown(text: string): ZoneCard[] {
  const zones: ZoneCard[] = [];
  const lines = text.split("\n");
  let inZone = false;
  for (const line of lines) {
    if (line.includes("Zone breakdown:")) {
      inZone = true;
      continue;
    }
    if (!inZone) continue;
    if (!line.trim()) break;

    const m = line.match(/^\s{2,}(.+?):\s+(\d+)/);
    if (!m) continue;
    const name = m[1].trim();
    const count = parseInt(m[2], 10);
    const kept = line.match(/\(kept (\d+), dropped (\d+)\)/);
    const tier: 1 | 2 = TIER1_NAMES.has(name) ? 1 : 2;
    zones.push({
      name,
      count,
      tier,
      detail: kept ? `Kept ${kept[1]}, dropped ${kept[2]}` : undefined,
    });
  }

  const totalM = text.match(/FINAL SUBMISSION TOTAL:\s+(\d+)/);
  if (totalM) {
    zones.push({
      name: "Final submission total",
      count: parseInt(totalM[1], 10),
      tier: "total",
    });
  }

  return zones;
}

function parseRerankerMetrics(text: string): Partial<
  Record<"Precision" | "Recall" | "F1" | "AUC", string>
> {
  const out: Partial<Record<"Precision" | "Recall" | "F1" | "AUC", string>> =
    {};
  const pairs: [RegExp, keyof typeof out][] = [
    [/Precision:\s*([\d.]+(?:e[+-]?\d+)?)/i, "Precision"],
    [/Recall:\s*([\d.]+(?:e[+-]?\d+)?)/i, "Recall"],
    [/F1:\s*([\d.]+(?:e[+-]?\d+)?)/i, "F1"],
    [/AUC:\s*([\d.]+(?:e[+-]?\d+)?)/i, "AUC"],
  ];
  for (const [re, key] of pairs) {
    const m = text.match(re);
    if (m) out[key] = m[1];
  }
  return out;
}

function buildViolationChartData(rows: CommitteeRow[]) {
  const symbols = [...new Set(rows.map((r) => r.symbol).filter(Boolean))].sort();
  const typeKeys = [
    ...new Set(rows.map((r) => r.violation_type || "(none)")),
  ].sort();
  const chartData = symbols.map((sym) => {
    const row: Record<string, string | number> = { symbol: sym };
    for (const t of typeKeys) row[t] = 0;
    for (const r of rows) {
      if (r.symbol !== sym) continue;
      const vt = r.violation_type || "(none)";
      row[vt] = (row[vt] as number) + 1;
    }
    return row;
  });
  return { chartData, typeKeys: typeKeys.length ? typeKeys : ["(none)"] };
}

function symbolTableRows(rows: CommitteeRow[]) {
  const symbols = [...new Set(rows.map((r) => r.symbol).filter(Boolean))].sort();
  return symbols.map((sym) => {
    const subset = rows.filter((r) => r.symbol === sym);
    const byType = new Map<string, number>();
    for (const r of subset) {
      const k = r.violation_type || "(none)";
      byType.set(k, (byType.get(k) ?? 0) + 1);
    }
    return { symbol: sym, total: subset.length, byType };
  });
}

export default function CommitteePage() {
  const [loading, setLoading] = useState(true);
  const [committee, setCommittee] = useState<CommitteeReport | null>(null);
  const [submission, setSubmission] = useState<CommitteeRow[] | null>(null);
  const [reranker, setReranker] = useState<CommitteeReport | null>(null);
  const [tuning, setTuning] = useState<CommitteeReport | null>(null);
  const [mlHealth, setMlHealth] = useState<MlHealth | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const [c, s, r, t, h] = await Promise.all([
        tryFetchJSON<CommitteeReport>("/api/reports/committee_report"),
        tryFetchJSON<CommitteeRow[]>("/api/outputs/submission_committee"),
        tryFetchJSON<CommitteeReport>("/api/reports/reranker_report"),
        tryFetchJSON<CommitteeReport>("/api/reports/tuning_report"),
        tryFetchJSON<MlHealth>("/api/ml/health"),
      ]);
      if (cancelled) return;
      setCommittee(c);
      setSubmission(s);
      setReranker(r);
      setTuning(t);
      setMlHealth(h);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const zones = useMemo(
    () => (committee?.text ? parseZoneBreakdown(committee.text) : []),
    [committee]
  );

  const { chartData, typeKeys } = useMemo(
    () => buildViolationChartData(submission ?? []),
    [submission]
  );

  const symbolRows = useMemo(
    () => symbolTableRows(submission ?? []),
    [submission]
  );

  const mlMetrics = useMemo(
    () => (reranker?.text ? parseRerankerMetrics(reranker.text) : {}),
    [reranker]
  );

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        Loading committee analytics…
      </div>
    );
  }

  const missingCommittee = !committee?.text;
  const missingSubmission = submission === null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Committee Analytics
        </h1>
        <p className="text-sm text-muted-foreground">
          Three-way committee zones, violation mix, ML re-ranker metrics, and
          tuning notes from the pipeline outputs.
        </p>
      </div>

      <Tabs defaultValue="zones">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="zones">Zone Breakdown</TabsTrigger>
          <TabsTrigger value="ml">ML Metrics</TabsTrigger>
          <TabsTrigger value="tuning">Tuning</TabsTrigger>
        </TabsList>

        <TabsContent value="zones" className="space-y-8 pt-4">
          <section className="space-y-4">
            <h2 className="text-lg font-medium">Zone breakdown</h2>
            {missingCommittee ? (
              <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
                Committee report not found. Run pipeline first.
              </p>
            ) : zones.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Could not parse zone lines from the report.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {zones.map((z) => (
                  <Card
                    key={z.name}
                    className={cn(
                      z.tier === 1 &&
                        "border-primary/40 bg-primary/5 shadow-sm ring-1 ring-primary/15",
                      z.tier === 2 && "border-muted-foreground/20 bg-muted/20",
                      z.tier === "total" &&
                        "border-foreground/30 bg-accent/30 font-medium ring-1 ring-border"
                    )}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between gap-2">
                        <CardTitle className="text-base font-semibold leading-tight">
                          {z.name}
                        </CardTitle>
                        {z.tier === 1 && (
                          <Badge variant="default" className="shrink-0 text-xs">
                            Tier 1
                          </Badge>
                        )}
                        {z.tier === 2 && (
                          <Badge variant="secondary" className="shrink-0 text-xs">
                            Tier 2
                          </Badge>
                        )}
                        {z.tier === "total" && (
                          <Badge variant="outline" className="shrink-0 text-xs">
                            Total
                          </Badge>
                        )}
                      </div>
                      {z.detail ? (
                        <CardDescription>{z.detail}</CardDescription>
                      ) : null}
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tabular-nums">{z.count}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Violation distribution</h2>
            {missingSubmission ? (
              <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
                Committee submission not found. Run pipeline first.
              </p>
            ) : (submission?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">
                No rows in submission_committee.
              </p>
            ) : (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      By symbol (stacked)
                    </CardTitle>
                    <CardDescription>
                      Count of violation types per symbol in the committee
                      submission.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[320px] w-full pt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="symbol" tick={{ fontSize: 12 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                        <Tooltip
                          contentStyle={{
                            borderRadius: 8,
                            border: "1px solid hsl(var(--border))",
                          }}
                        />
                        <Legend />
                        {typeKeys.map((key, i) => (
                          <Bar
                            key={key}
                            dataKey={key}
                            stackId="violations"
                            fill={CHART_COLORS[i % CHART_COLORS.length]}
                            radius={[0, 0, 0, 0]}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      Per-symbol breakdown
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-x-auto p-0">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/40 text-left">
                          <th className="px-6 py-3 font-medium">Symbol</th>
                          <th className="px-4 py-3 font-medium">Total</th>
                          <th className="px-4 py-3 font-medium">Violation mix</th>
                        </tr>
                      </thead>
                      <tbody>
                        {symbolRows.map((sr) => (
                          <tr key={sr.symbol} className="border-b last:border-0">
                            <td className="px-6 py-3 font-mono text-xs">
                              {sr.symbol}
                            </td>
                            <td className="px-4 py-3 tabular-nums">{sr.total}</td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-1">
                                {[...sr.byType.entries()]
                                  .sort((a, b) => b[1] - a[1])
                                  .map(([vt, n]) => (
                                    <Badge
                                      key={vt}
                                      variant="outline"
                                      className="font-normal"
                                    >
                                      {vt}: {n}
                                    </Badge>
                                  ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              </>
            )}
          </section>
        </TabsContent>

        <TabsContent value="ml" className="space-y-4 pt-4">
          {mlHealth?.stage1 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Model health (staged ML)</CardTitle>
                <CardDescription>
                  From saved artifacts — run{" "}
                  <code className="rounded bg-muted px-1 text-xs">
                    python run.py train-ml
                  </code>{" "}
                  locally to refresh.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-muted-foreground">
                  <span className="font-medium text-foreground">Stage-1</span>{" "}
                  threshold{" "}
                  <span className="font-mono tabular-nums">
                    {String(mlHealth.stage1.threshold ?? "—")}
                  </span>
                  , PR-AUC (test){" "}
                  <span className="font-mono tabular-nums">
                    {Number(mlHealth.stage1.pr_auc_test ?? 0).toFixed(4)}
                  </span>
                  , trained{" "}
                  <span className="font-mono text-xs">
                    {String(mlHealth.stage1.trained_at ?? "—")}
                  </span>
                </p>
                {mlHealth.stage2 && !mlHealth.stage2.skipped ? (
                  <p className="text-muted-foreground">
                    <span className="font-medium text-foreground">Stage-2</span>{" "}
                    macro-F1 (test){" "}
                    <span className="font-mono tabular-nums">
                      {Number(mlHealth.stage2.test_macro_f1 ?? 0).toFixed(4)}
                    </span>
                    , classes:{" "}
                    <span className="text-xs">
                      {Array.isArray(mlHealth.stage2.classes)
                        ? (mlHealth.stage2.classes as string[]).slice(0, 6).join(", ")
                        : "—"}
                      …
                    </span>
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Stage-2 not trained or skipped (insufficient class data).
                  </p>
                )}
                {mlHealth.artifacts_present && (
                  <p className="text-xs text-muted-foreground">
                    Artifacts: stage1={String(mlHealth.artifacts_present.stage1)}, stage2=
                    {String(mlHealth.artifacts_present.stage2)}
                  </p>
                )}
              </CardContent>
            </Card>
          )}
          {!reranker?.text ? (
            <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
              Re-ranker report not found. Run{" "}
              <code className="rounded bg-muted px-1 text-xs">python run.py reranker</code>{" "}
              or <code className="rounded bg-muted px-1 text-xs">train-ml</code>.
            </p>
          ) : (
            <>
              {Object.keys(mlMetrics).length > 0 && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {(
                    ["Precision", "Recall", "F1", "AUC"] as const
                  ).map((k) =>
                    mlMetrics[k] ? (
                      <Card key={k}>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-sm font-medium text-muted-foreground">
                            {k}
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="text-2xl font-semibold tabular-nums">
                            {mlMetrics[k]}
                          </p>
                        </CardContent>
                      </Card>
                    ) : null
                  )}
                </div>
              )}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">ML re-ranker report</CardTitle>
                  <CardDescription>Raw metrics and diagnostics</CardDescription>
                </CardHeader>
                <CardContent>
                  <pre className="max-h-[480px] overflow-auto rounded-md border bg-muted/40 p-4 text-xs leading-relaxed">
                    <code>{reranker.text}</code>
                  </pre>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="tuning" className="space-y-4 pt-4">
          {!tuning?.text ? (
            <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
              Tuning report not found. Run pipeline first.
            </p>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Parameter tuning</CardTitle>
                <CardDescription>
                  Suggestions from the tuning pass
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[560px] overflow-auto rounded-md border bg-muted/40 p-4 text-xs leading-relaxed">
                  <code>{tuning.text}</code>
                </pre>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
