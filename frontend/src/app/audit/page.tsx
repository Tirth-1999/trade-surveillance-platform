"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchJSON, postJSON } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { Download, Loader2 } from "lucide-react";

type ProblemId = "P1" | "P2" | "P3";
type ActionId = "confirm" | "reject" | "escalate";

type HitlDecision = {
  problem: string;
  row_id: string;
  action: string;
  violation_type?: string | null;
  remarks?: string | null;
  timestamp: string;
};

const FIELD =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

const TEXTAREA_FIELD =
  "min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

function normalizeDecisions(raw: unknown): HitlDecision[] {
  if (!Array.isArray(raw)) return [];
  return raw as HitlDecision[];
}

function parseTs(ts: string | undefined): number {
  if (!ts) return 0;
  const n = Date.parse(ts);
  return Number.isNaN(n) ? 0 : n;
}

function formatTimestamp(ts: string | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function ActionBadge({ action }: { action: string }) {
  const a = (action ?? "").toLowerCase();
  if (a === "confirm") {
    return (
      <Badge
        className="border-transparent bg-emerald-600/15 text-emerald-800 hover:bg-emerald-600/20 dark:bg-emerald-500/20 dark:text-emerald-300"
        variant="outline"
      >
        confirm
      </Badge>
    );
  }
  if (a === "reject") {
    return <Badge variant="destructive">reject</Badge>;
  }
  if (a === "escalate") {
    return (
      <Badge
        className="border-transparent bg-amber-500/20 text-amber-900 hover:bg-amber-500/25 dark:bg-amber-500/15 dark:text-amber-200"
        variant="outline"
      >
        escalate
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="capitalize">
      {action || "—"}
    </Badge>
  );
}

export default function AuditTrailPage() {
  const [decisions, setDecisions] = useState<HitlDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [problem, setProblem] = useState<ProblemId>("P1");
  const [rowId, setRowId] = useState("");
  const [action, setAction] = useState<ActionId>("confirm");
  const [violationType, setViolationType] = useState("");
  const [remarks, setRemarks] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formMessage, setFormMessage] = useState<{
    type: "ok" | "err";
    text: string;
  } | null>(null);

  const [filterProblem, setFilterProblem] = useState<string>("all");
  const [filterAction, setFilterAction] = useState<string>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const raw = await fetchJSON<unknown>("/api/decisions");
      setDecisions(normalizeDecisions(raw));
    } catch (e) {
      setDecisions([]);
      setLoadError(e instanceof Error ? e.message : "Failed to load decisions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredSorted = useMemo(() => {
    return decisions
      .filter((d) => {
        if (filterProblem !== "all" && (d.problem ?? "").toUpperCase() !== filterProblem) {
          return false;
        }
        if (filterAction !== "all" && (d.action ?? "").toLowerCase() !== filterAction) {
          return false;
        }
        return true;
      })
      .sort((a, b) => parseTs(b.timestamp) - parseTs(a.timestamp));
  }, [decisions, filterProblem, filterAction]);

  const stats = useMemo(() => {
    const list = filteredSorted;
    const total = list.length;
    let confirmed = 0;
    let rejected = 0;
    let escalated = 0;
    for (const d of list) {
      const a = (d.action ?? "").toLowerCase();
      if (a === "confirm") confirmed += 1;
      else if (a === "reject") rejected += 1;
      else if (a === "escalate") escalated += 1;
    }
    return { total, confirmed, rejected, escalated };
  }, [filteredSorted]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormMessage(null);
    const rid = rowId.trim();
    if (!rid) {
      setFormMessage({ type: "err", text: "Row ID is required." });
      return;
    }
    setSubmitting(true);
    try {
      await postJSON("/api/decisions", {
        problem,
        row_id: rid,
        action,
        violation_type: violationType.trim() || null,
        remarks: remarks.trim() || null,
      });
      setFormMessage({ type: "ok", text: "Decision recorded successfully." });
      setRowId("");
      setViolationType("");
      setRemarks("");
      await load();
    } catch (err) {
      setFormMessage({
        type: "err",
        text: err instanceof Error ? err.message : "Failed to save decision",
      });
    } finally {
      setSubmitting(false);
    }
  }

  function downloadJson() {
    const blob = new Blob([JSON.stringify(decisions, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hitl-decisions-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Audit Trail — HITL Decisions
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Human-in-the-loop decisions are logged to the API and listed below.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Add decision</h2>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New HITL decision</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="audit-problem">
                    Problem
                  </label>
                  <select
                    id="audit-problem"
                    className={FIELD}
                    value={problem}
                    onChange={(e) => setProblem(e.target.value as ProblemId)}
                  >
                    <option value="P1">P1 — Equity</option>
                    <option value="P2">P2 — SEC</option>
                    <option value="P3">P3 — Crypto</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="audit-row-id">
                    Row ID
                  </label>
                  <Input
                    id="audit-row-id"
                    placeholder="e.g. trade or alert identifier"
                    value={rowId}
                    onChange={(e) => setRowId(e.target.value)}
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="audit-action">
                    Action
                  </label>
                  <select
                    id="audit-action"
                    className={FIELD}
                    value={action}
                    onChange={(e) => setAction(e.target.value as ActionId)}
                  >
                    <option value="confirm">Confirm</option>
                    <option value="reject">Reject</option>
                    <option value="escalate">Escalate</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium"
                    htmlFor="audit-violation"
                  >
                    Violation type <span className="font-normal text-muted-foreground">(optional)</span>
                  </label>
                  <Input
                    id="audit-violation"
                    placeholder="e.g. wash trade"
                    value={violationType}
                    onChange={(e) => setViolationType(e.target.value)}
                    autoComplete="off"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="audit-remarks">
                  Remarks
                </label>
                <textarea
                  id="audit-remarks"
                  className={cn(TEXTAREA_FIELD, "resize-y")}
                  placeholder="Context or rationale for this decision"
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  rows={4}
                />
              </div>
              {formMessage && (
                <p
                  className={cn(
                    "text-sm",
                    formMessage.type === "ok"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-destructive"
                  )}
                  role="alert"
                >
                  {formMessage.text}
                </p>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Submit decision"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>

      <Separator />

      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-medium">Decision log</h2>
            <p className="text-sm text-muted-foreground">
              Newest first. Use filters to narrow the table; counts match the filtered set.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="filter-problem">
                Problem
              </label>
              <select
                id="filter-problem"
                className={cn(FIELD, "h-9 min-w-[120px]")}
                value={filterProblem}
                onChange={(e) => setFilterProblem(e.target.value)}
              >
                <option value="all">All</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="filter-action">
                Action
              </label>
              <select
                id="filter-action"
                className={cn(FIELD, "h-9 min-w-[140px]")}
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
              >
                <option value="all">All</option>
                <option value="confirm">Confirm</option>
                <option value="reject">Reject</option>
                <option value="escalate">Escalate</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Total decisions", value: stats.total },
            { label: "Confirmed", value: stats.confirmed },
            { label: "Rejected", value: stats.rejected },
            { label: "Escalated", value: stats.escalated },
          ].map(({ label, value }) => (
            <Card key={label}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {loadError && (
          <Card className="border-destructive/50 bg-destructive/5">
            <CardContent className="pt-6">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
                Retry
              </Button>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <Card>
            <CardContent className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Loading decisions…</span>
            </CardContent>
          </Card>
        ) : filteredSorted.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <p className="font-medium text-foreground">
                {decisions.length === 0
                  ? "No decisions yet"
                  : "No decisions match these filters"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {decisions.length === 0
                  ? "Submit a decision above or wait for pipeline activity."
                  : "Try clearing filters or choosing “All” for problem and action."}
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b bg-muted/40 text-left text-muted-foreground">
                    <th className="px-4 py-3 font-medium">Timestamp</th>
                    <th className="px-4 py-3 font-medium">Problem</th>
                    <th className="px-4 py-3 font-medium">Row ID</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Violation type</th>
                    <th className="px-4 py-3 font-medium">Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSorted.map((d, i) => (
                    <tr
                      key={`${d.timestamp}-${d.row_id}-${i}`}
                      className="border-b border-border/60 last:border-0 hover:bg-muted/30"
                    >
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums text-muted-foreground">
                        {formatTimestamp(d.timestamp)}
                      </td>
                      <td className="px-4 py-3 font-medium">{d.problem ?? "—"}</td>
                      <td className="max-w-[140px] truncate px-4 py-3 font-mono text-xs">
                        {d.row_id ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <ActionBadge action={d.action} />
                      </td>
                      <td className="max-w-[160px] truncate px-4 py-3 text-muted-foreground">
                        {d.violation_type?.trim() || "—"}
                      </td>
                      <td className="max-w-[280px] px-4 py-3 text-muted-foreground">
                        <span className="line-clamp-2 whitespace-pre-wrap break-words">
                          {d.remarks?.trim() || "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      <Separator />

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Export</h2>
        <Card>
          <CardContent className="flex flex-col gap-3 py-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Download the full decision list ({decisions.length} record
              {decisions.length === 1 ? "" : "s"}) as JSON.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={downloadJson}
              disabled={decisions.length === 0}
            >
              <Download className="mr-2 h-4 w-4" />
              Download JSON
            </Button>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
