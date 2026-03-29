"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchJSON, postJSON, uploadFile } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Upload,
} from "lucide-react";

type RunResponse = {
  pipeline: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  elapsed_sec: number;
};

type OutputFileStatus = {
  name: string;
  exists: boolean;
  size_bytes: number;
  row_count: number | null;
  last_modified: string | null;
};

type UploadResponse = {
  uploaded_rows: number;
  flags_found: number;
  flags: Record<string, unknown>[];
  stdout?: string;
  stderr?: string;
};

const PIPELINE_STEPS: {
  id: string;
  name: string;
  description: string;
  path: string;
}[] = [
  {
    id: "p1",
    name: "P1 Equity Rules",
    description: "Equity order-book surveillance and anomaly flags.",
    path: "/api/run/p1",
  },
  {
    id: "p2",
    name: "P2 SEC Rules",
    description: "SEC-style surveillance signals from trade data.",
    path: "/api/run/p2",
  },
  {
    id: "p3",
    name: "P3 Crypto Rules",
    description: "Crypto-specific detection pipeline.",
    path: "/api/run/p3",
  },
  {
    id: "ground-truth",
    name: "AI Ground Truth",
    description: "Generate or refresh AI ground-truth labels.",
    path: "/api/run/ground-truth",
  },
  {
    id: "compare",
    name: "Compare",
    description: "Compare model outputs against ground truth.",
    path: "/api/run/compare",
  },
  {
    id: "reranker",
    name: "ML Re-Ranker",
    description: "Run the ML re-ranking stage on candidates.",
    path: "/api/run/reranker",
  },
  {
    id: "committee",
    name: "Committee Fusion",
    description: "Fuse committee decisions into final submission.",
    path: "/api/run/committee",
  },
  {
    id: "tune",
    name: "Parameter Tuning",
    description: "Hyperparameter search / tuning for pipeline models.",
    path: "/api/run/tune",
  },
  {
    id: "all",
    name: "Run All",
    description: "Execute the full pipeline end-to-end.",
    path: "/api/run/all",
  },
];

function formatBytes(n: number): string {
  if (n === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(n) / Math.log(k));
  return `${parseFloat((n / k ** i).toFixed(2))} ${sizes[i]}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function ControlPage() {
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, RunResponse | null>>(
    {}
  );
  const [runErrors, setRunErrors] = useState<Record<string, string>>({});
  const [outputOpen, setOutputOpen] = useState<Record<string, boolean>>({});

  const [status, setStatus] = useState<OutputFileStatus[] | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(
    null
  );
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const data = await fetchJSON<OutputFileStatus[]>("/api/status");
      setStatus(Array.isArray(data) ? data : []);
    } catch (e) {
      setStatus(null);
      setStatusError(e instanceof Error ? e.message : "Failed to load status");
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const runStep = async (id: string, path: string) => {
    setRunning((r) => ({ ...r, [id]: true }));
    setRunErrors((e) => {
      const next = { ...e };
      delete next[id];
      return next;
    });
    try {
      const data = await postJSON<RunResponse>(path);
      setResults((prev) => ({ ...prev, [id]: data }));
    } catch (e) {
      setResults((prev) => ({ ...prev, [id]: null }));
      setRunErrors((prev) => ({
        ...prev,
        [id]: e instanceof Error ? e.message : "Request failed",
      }));
    } finally {
      setRunning((r) => ({ ...r, [id]: false }));
    }
  };

  const toggleOutput = (id: string) => {
    setOutputOpen((o) => ({ ...o, [id]: !o[id] }));
  };

  const flagColumns = useMemo(() => {
    const flags = uploadResult?.flags ?? [];
    if (flags.length === 0) return [] as string[];
    const keys = new Set<string>();
    for (const row of flags) {
      Object.keys(row).forEach((k) => keys.add(k));
    }
    return Array.from(keys).sort();
  }, [uploadResult?.flags]);

  const onFile = async (file: File | null) => {
    if (!file) return;
    setUploadBusy(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const data = await uploadFile<UploadResponse>("/api/upload", file);
      setUploadResult(data);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploadBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-10 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Pipeline Control Center
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Trigger pipeline stages against the FastAPI backend and inspect
          outputs.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">
          Pipeline steps
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PIPELINE_STEPS.map((step) => {
            const isRunning = running[step.id];
            const res = results[step.id];
            const err = runErrors[step.id];
            const open = outputOpen[step.id];
            const hasOutput =
              (res && (res.stdout || res.stderr)) || err !== undefined;

            return (
              <Card key={step.id} className="flex flex-col">
                <CardHeader className="space-y-1 pb-3">
                  <CardTitle className="text-base">{step.name}</CardTitle>
                  <CardDescription className="line-clamp-2">
                    {step.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="mt-auto flex flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant={step.id === "all" ? "success" : "default"}
                      size="sm"
                      disabled={isRunning}
                      onClick={() => void runStep(step.id, step.path)}
                    >
                      {isRunning ? (
                        <>
                          <Loader2
                            className="h-4 w-4 animate-spin"
                            aria-hidden
                          />
                          Running…
                        </>
                      ) : step.id === "all" ? (
                        "Run All"
                      ) : (
                        "Run"
                      )}
                    </Button>
                    {!isRunning && res && (
                      <>
                        <Badge
                          variant={
                            res.exit_code === 0 ? "success" : "destructive"
                          }
                        >
                          exit {res.exit_code}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {res.elapsed_sec}s
                        </span>
                      </>
                    )}
                    {!isRunning && err && !res && (
                      <Badge variant="destructive">Error</Badge>
                    )}
                  </div>

                  {hasOutput && (
                    <div className="border-t pt-3">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-ml-2 h-8 gap-1 px-2 text-muted-foreground"
                        onClick={() => toggleOutput(step.id)}
                        aria-expanded={open}
                      >
                        {open ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                        Output
                      </Button>
                      {open && (
                        <ScrollArea className="mt-2 max-h-48 rounded-md border bg-muted/30 p-3 font-mono text-xs">
                          {err && !res && (
                            <pre className="whitespace-pre-wrap break-words text-destructive">
                              {err}
                            </pre>
                          )}
                          {res?.stdout ? (
                            <div className="mb-2">
                              <span className="font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                                stdout
                              </span>
                              <pre className="mt-1 whitespace-pre-wrap break-words">
                                {res.stdout}
                              </pre>
                            </div>
                          ) : null}
                          {res?.stderr ? (
                            <div>
                              <span className="font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                                stderr
                              </span>
                              <pre className="mt-1 whitespace-pre-wrap break-words text-destructive/90">
                                {res.stderr}
                              </pre>
                            </div>
                          ) : null}
                          {!err &&
                            res &&
                            !res.stdout &&
                            !res.stderr && (
                              <p className="text-muted-foreground">
                                No stdout/stderr.
                              </p>
                            )}
                        </ScrollArea>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">File upload</h2>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upload CSV</CardTitle>
            <CardDescription>
              Drag a CSV here or click to browse. Required columns include{" "}
              <span className="font-mono text-xs">
                trade_id, symbol, timestamp, price, quantity, side
              </span>
              .
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(false);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(false);
                const f = e.dataTransfer.files?.[0];
                if (f?.name?.toLowerCase().endsWith(".csv")) {
                  void onFile(f);
                } else {
                  setUploadError("Please drop a .csv file.");
                }
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors ${
                dragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-muted/30"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  void onFile(f ?? null);
                }}
              />
              {uploadBusy ? (
                <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
              ) : (
                <Upload className="h-10 w-10 text-muted-foreground" />
              )}
              <div>
                <p className="text-sm font-medium">
                  {uploadBusy ? "Uploading…" : "Drop CSV or click to select"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Only .csv files are accepted
                </p>
              </div>
            </div>

            {uploadError && (
              <p className="text-sm text-destructive">{uploadError}</p>
            )}

            {uploadResult && (
              <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                <div className="flex flex-wrap gap-3 text-sm">
                  <span>
                    <span className="text-muted-foreground">Uploaded rows: </span>
                    <strong>{uploadResult.uploaded_rows}</strong>
                  </span>
                  <span>
                    <span className="text-muted-foreground">Flags found: </span>
                    <strong>{uploadResult.flags_found}</strong>
                  </span>
                </div>
                {flagColumns.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No flag rows returned.
                  </p>
                ) : (
                  <div className="overflow-x-auto rounded-md border bg-background">
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead className="border-b bg-muted/50">
                        <tr>
                          {flagColumns.map((col) => (
                            <th
                              key={col}
                              className="whitespace-nowrap p-2 font-medium"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(uploadResult.flags ?? []).map((row, i) => (
                          <tr
                            key={i}
                            className="border-b last:border-0 hover:bg-muted/20"
                          >
                            {flagColumns.map((col) => (
                              <td
                                key={col}
                                className="max-w-[240px] truncate p-2 font-mono text-xs"
                                title={String(row[col] ?? "")}
                              >
                                {row[col] === null || row[col] === undefined
                                  ? "—"
                                  : String(row[col])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold tracking-tight">
            Output status
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={statusLoading}
            onClick={() => void loadStatus()}
            className="gap-2 self-start sm:self-auto"
          >
            {statusLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            Refresh
          </Button>
        </div>

        {statusLoading && !status ? (
          <div className="flex items-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            Loading output file status…
          </div>
        ) : statusError ? (
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="text-destructive text-base">
                Could not load status
              </CardTitle>
              <CardDescription>{statusError}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" onClick={() => void loadStatus()}>
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="p-3 font-medium">File name</th>
                  <th className="p-3 font-medium">Exists</th>
                  <th className="p-3 font-medium">Rows</th>
                  <th className="p-3 font-medium">Size</th>
                  <th className="p-3 font-medium">Last modified</th>
                </tr>
              </thead>
              <tbody>
                {(status ?? []).map((row) => (
                  <tr
                    key={row.name}
                    className="border-b last:border-0 hover:bg-muted/20"
                  >
                    <td className="p-3 font-mono text-xs">{row.name}</td>
                    <td className="p-3">
                      {row.exists ? (
                        <Badge variant="success">Yes</Badge>
                      ) : (
                        <Badge variant="destructive">No</Badge>
                      )}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {row.row_count != null ? row.row_count : "—"}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {row.exists ? formatBytes(row.size_bytes) : "—"}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {formatDate(row.last_modified)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
