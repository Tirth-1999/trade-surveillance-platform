"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchJSON } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ExternalLink, Loader2 } from "lucide-react";

export type P2Signal = {
  sec_id: string;
  event_date: string;
  event_type: string;
  headline: string;
  source_url: string;
  pre_drift_flag: number;
  suspicious_window_start: string;
  remarks: string;
  time_to_run: string;
};

function isDriftFlag(v: unknown): boolean {
  return v === 1 || v === "1" || v === true;
}

function normalizeSignals(raw: unknown): P2Signal[] {
  if (!Array.isArray(raw)) return [];
  return raw as P2Signal[];
}

export default function P2SecPage() {
  const [signals, setSignals] = useState<P2Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await fetchJSON<unknown>("/api/outputs/p2_signals");
      setSignals(normalizeSignals(raw));
    } catch (e) {
      setSignals([]);
      setError(e instanceof Error ? e.message : "Failed to load signals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const t = eventTypeFilter.trim().toLowerCase();
    return signals.filter((s) => {
      if (t && !(s.event_type ?? "").toLowerCase().includes(t)) return false;
      return true;
    });
  }, [signals, eventTypeFilter]);

  const stats = useMemo(() => {
    const uniqueSec = new Set(filtered.map((s) => s.sec_id).filter(Boolean));
    const driftCount = filtered.filter((s) => isDriftFlag(s.pre_drift_flag))
      .length;
    return {
      total: filtered.length,
      uniqueSecurities: uniqueSec.size,
      driftCount,
    };
  }, [filtered]);

  const eventTypeChartData = useMemo(() => {
    const counts = filtered.reduce<Record<string, number>>((acc, s) => {
      const key = (s.event_type ?? "Unknown").trim() || "Unknown";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [filtered]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        <p>Loading P2 signals…</p>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="max-w-lg border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Could not load data</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button type="button" onClick={() => void load()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          P2 — SEC 8-K / Pre-Announcement Drift
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Filings, headlines, and pre-announcement drift flags
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Signals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Unique Securities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.uniqueSecurities}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Events with drift flag
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-destructive">
              {stats.driftCount}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Event type distribution</CardTitle>
        </CardHeader>
        <CardContent>
          {eventTypeChartData.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data to chart.</p>
          ) : (
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={eventTypeChartData}
                  margin={{ top: 8, right: 8, left: 0, bottom: 64 }}
                >
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    interval={0}
                    angle={-35}
                    textAnchor="end"
                    height={70}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid hsl(var(--border))",
                    }}
                    formatter={(value) => [value ?? "—", "Count"]}
                  />
                  <Bar
                    dataKey="count"
                    name="Signals"
                    fill="hsl(var(--primary))"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filter</CardTitle>
        </CardHeader>
        <CardContent className="max-w-md space-y-2">
          <label htmlFor="p2-event" className="text-sm font-medium">
            Event type
          </label>
          <Input
            id="p2-event"
            placeholder="Filter by event_type…"
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Signals</CardTitle>
        </CardHeader>
        <CardContent>
          {signals.length === 0 ? (
            <div className="space-y-4 rounded-lg border border-dashed bg-muted/30 p-6">
              <p className="text-sm font-medium text-foreground">
                No P2 rows loaded — the API returned an empty list.
              </p>
              <p className="text-sm text-muted-foreground">
                That usually means <code className="rounded bg-muted px-1.5 py-0.5 text-xs">outputs/p2_signals.csv</code>{" "}
                is missing or has <strong>only a header</strong> (zero filing rows). P2 is not broken in the UI; the
                backend file has no data yet.
              </p>
              <ul className="list-inside list-disc space-y-2 text-sm text-muted-foreground">
                <li>
                  Run from the repo root:{" "}
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">python3 run.py p2</code> (needs{" "}
                  <strong>internet</strong> for SEC <code className="text-xs">data.sec.gov</code>).
                </li>
                <li>
                  Or use <strong>Pipeline</strong> in the sidebar → <strong>Run</strong> on &quot;P2 SEC Rules&quot; and
                  check the log for errors (403, timeout, missing tickers).
                </li>
                <li>
                  Ensure <code className="text-xs">student-pack/equity/ohlcv.csv</code> and tickers align with SEC&apos;s
                  company list; P2 skips tickers with no CIK match.
                </li>
                <li>
                  Filings classified as <code className="text-xs">other</code> are dropped — if everything is
                  &quot;other&quot;, the CSV stays empty.
                </li>
              </ul>
              <Button type="button" variant="secondary" onClick={() => void load()}>
                Reload from API
              </Button>
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No signals match the current filter.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full min-w-[960px] text-left text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="p-3 font-medium">sec_id</th>
                    <th className="p-3 font-medium">event_date</th>
                    <th className="p-3 font-medium">event_type</th>
                    <th className="p-3 font-medium">headline</th>
                    <th className="p-3 font-medium">source_url</th>
                    <th className="p-3 font-medium">pre_drift</th>
                    <th className="p-3 font-medium">suspicious_window_start</th>
                    <th className="p-3 font-medium">remarks</th>
                    <th className="p-3 font-medium">time_to_run</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, idx) => {
                    const drift = isDriftFlag(row.pre_drift_flag);
                    const key = `${row.sec_id}-${row.event_date}-${idx}`;
                    return (
                      <tr
                        key={key}
                        className="border-b last:border-0 hover:bg-muted/30"
                      >
                        <td className="p-3 align-middle">{row.sec_id}</td>
                        <td className="p-3 align-middle">{row.event_date}</td>
                        <td className="p-3 align-middle">{row.event_type}</td>
                        <td className="max-w-[240px] p-3 align-middle text-muted-foreground">
                          {row.headline || "—"}
                        </td>
                        <td className="max-w-[180px] p-3 align-middle">
                          {row.source_url ? (
                            <a
                              href={row.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
                            >
                              <span className="truncate">Open</span>
                              <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="p-3 align-middle">
                          {drift ? (
                            <Badge variant="destructive">DRIFT</Badge>
                          ) : (
                            <Badge variant="success">NORMAL</Badge>
                          )}
                        </td>
                        <td className="p-3 align-middle text-xs">
                          {row.suspicious_window_start || "—"}
                        </td>
                        <td className="max-w-[200px] p-3 align-middle text-muted-foreground">
                          <span className="line-clamp-2">{row.remarks || "—"}</span>
                        </td>
                        <td className="p-3 align-middle text-xs text-muted-foreground">
                          {row.time_to_run}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
