const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATIC_MAP: Record<string, string> = {
  "/api/outputs/submission": "/data/submission.json",
  "/api/outputs/submission_committee": "/data/submission_committee.json",
  "/api/outputs/submission_with_trades": "/data/submission_with_trades.json",
  "/api/outputs/submission_committee_with_trades":
    "/data/submission_committee_with_trades.json",
  "/api/outputs/submission_ml": "/data/submission_ml.json",
  "/api/outputs/ground_truth": "/data/ground_truth.json",
  "/api/outputs/comparison_report": "/data/comparison_report.json",
  "/api/outputs/p1_alerts": "/data/p1_alerts.json",
  "/api/outputs/p2_signals": "/data/p2_signals.json",
  "/api/outputs/p3_pass2_audit": "/data/p3_pass2_audit.json",
  "/api/reports/committee_report": "/data/committee_report.json",
  "/api/reports/reranker_report": "/data/reranker_report.json",
  "/api/reports/tuning_report": "/data/tuning_report.json",
  "/api/status": "/data/status.json",
  "/api/decisions": "/data/decisions.json",
  "/api/ml/health": "/data/ml_health.json",
};

function staticPath(apiPath: string): string | null {
  const base = apiPath.split("?")[0];
  return STATIC_MAP[base] ?? null;
}

export async function fetchJSON<T = any>(path: string): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`);
    if (res.ok) return res.json();
  } catch {
    /* API unreachable — fall through to static */
  }

  const fallback = staticPath(path);
  if (fallback) {
    const res = await fetch(fallback);
    if (res.ok) return res.json();
  }

  throw new Error(`Data unavailable for ${path}`);
}

export async function postJSON<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function uploadFile<T = any>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}
