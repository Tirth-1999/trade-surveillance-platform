"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { fetchJSON } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

export type P1Alert = {
  alert_id: string;
  sec_id: string;
  trade_date: string;
  time_window_start: string;
  anomaly_type: string;
  severity: string;
  remarks: string;
  time_to_run: string;
};

function severityBadgeVariant(
  severity: string
): "destructive" | "secondary" | "outline" {
  const s = severity?.toUpperCase?.() ?? "";
  if (s === "HIGH") return "destructive";
  if (s === "MEDIUM") return "secondary";
  return "outline";
}

function normalizeAlerts(raw: unknown): P1Alert[] {
  if (!Array.isArray(raw)) return [];
  return raw as P1Alert[];
}

export default function P1EquityPage() {
  const [alerts, setAlerts] = useState<P1Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secFilter, setSecFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await fetchJSON<unknown>("/api/outputs/p1_alerts");
      setAlerts(normalizeAlerts(raw));
    } catch (e) {
      setAlerts([]);
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const s = secFilter.trim().toLowerCase();
    const t = typeFilter.trim().toLowerCase();
    return alerts.filter((a) => {
      if (s && !(a.sec_id ?? "").toLowerCase().includes(s)) return false;
      if (t && !(a.anomaly_type ?? "").toLowerCase().includes(t)) return false;
      return true;
    });
  }, [alerts, secFilter, typeFilter]);

  const stats = useMemo(() => {
    const uniqueSec = new Set(filtered.map((a) => a.sec_id).filter(Boolean));
    const uniqueTypes = new Set(
      filtered.map((a) => a.anomaly_type).filter(Boolean)
    );
    const severityCounts = filtered.reduce<Record<string, number>>((acc, a) => {
      const key = (a.severity ?? "Unknown").trim() || "Unknown";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    return {
      total: filtered.length,
      uniqueSecurities: uniqueSec.size,
      anomalyTypes: uniqueTypes.size,
      severityCounts,
    };
  }, [filtered]);

  const toggleRow = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        <p>Loading P1 alerts…</p>
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
          P1 — Equity Order Book Surveillance
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Order-book anomalies and severity breakdown
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Alerts
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
              Anomaly Types (distinct)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.anomalyTypes}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Severity distribution</CardTitle>
        </CardHeader>
        <CardContent>
          {Object.keys(stats.severityCounts).length === 0 ? (
            <p className="text-sm text-muted-foreground">No rows match filters.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.severityCounts)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([sev, count]) => (
                  <Badge
                    key={sev}
                    variant={severityBadgeVariant(sev)}
                    className="gap-1.5"
                  >
                    {sev}
                    <span className="opacity-80">({count})</span>
                  </Badge>
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row">
          <div className="flex-1 space-y-2">
            <label htmlFor="p1-sec" className="text-sm font-medium">
              Security ID
            </label>
            <Input
              id="p1-sec"
              placeholder="Filter by sec_id…"
              value={secFilter}
              onChange={(e) => setSecFilter(e.target.value)}
            />
          </div>
          <div className="flex-1 space-y-2">
            <label htmlFor="p1-type" className="text-sm font-medium">
              Anomaly type
            </label>
            <Input
              id="p1-type"
              placeholder="Filter by anomaly_type…"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No alerts returned from the API.
            </p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No alerts match the current filters.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="w-10 p-3" aria-label="Expand" />
                    <th className="p-3 font-medium">alert_id</th>
                    <th className="p-3 font-medium">sec_id</th>
                    <th className="p-3 font-medium">trade_date</th>
                    <th className="p-3 font-medium">time_window_start</th>
                    <th className="p-3 font-medium">anomaly_type</th>
                    <th className="p-3 font-medium">severity</th>
                    <th className="p-3 font-medium">remarks</th>
                    <th className="p-3 font-medium">time_to_run</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => {
                    const id = row.alert_id ?? `${row.sec_id}-${row.trade_date}`;
                    const isOpen = expanded.has(id);
                    const remarksPreview =
                      (row.remarks ?? "").length > 80
                        ? `${(row.remarks ?? "").slice(0, 80)}…`
                        : row.remarks ?? "—";
                    return (
                      <Fragment key={id}>
                        <tr className="border-b last:border-0 hover:bg-muted/30">
                          <td className="p-2 align-middle">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              aria-expanded={isOpen}
                              onClick={() => toggleRow(id)}
                            >
                              {isOpen ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </Button>
                          </td>
                          <td className="p-3 align-middle font-mono text-xs">
                            {row.alert_id}
                          </td>
                          <td className="p-3 align-middle">{row.sec_id}</td>
                          <td className="p-3 align-middle">{row.trade_date}</td>
                          <td className="p-3 align-middle">
                            {row.time_window_start}
                          </td>
                          <td className="p-3 align-middle">{row.anomaly_type}</td>
                          <td className="p-3 align-middle">
                            <Badge variant={severityBadgeVariant(row.severity)}>
                              {row.severity || "—"}
                            </Badge>
                          </td>
                          <td className="max-w-[200px] p-3 align-middle text-muted-foreground">
                            {isOpen ? "—" : remarksPreview}
                          </td>
                          <td className="p-3 align-middle text-xs text-muted-foreground">
                            {row.time_to_run}
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className="border-b bg-muted/20">
                            <td colSpan={9} className="p-4 text-sm">
                              <span className="font-medium text-foreground">
                                Full remarks:{" "}
                              </span>
                              <span className="whitespace-pre-wrap">
                                {row.remarks || "—"}
                              </span>
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
