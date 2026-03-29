"use client";

import { useCallback, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Database,
  Search,
  Brain,
  GitCompare,
  Cpu,
  Users,
  SlidersHorizontal,
  FileOutput,
  Monitor,
  X,
  ShieldCheck,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Node detail panels — shown when a node is clicked                 */
/* ------------------------------------------------------------------ */

type StepDetail = {
  title: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  inputs: string[];
  outputs: string[];
  tech: string[];
  keyInsight: string;
};

const STEP_DETAILS: Record<string, StepDetail> = {
  input: {
    title: "Input Data",
    icon: <Database className="h-5 w-5" />,
    color: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
    description:
      "Raw market data from crypto and equity exchanges. Eight crypto symbol pairs (BTC, ETH, SOL, XRP, DOGE, LTC, BAT, USDC) with both OHLCV bars and individual trade records. Equity data includes order book snapshots and trade executions.",
    inputs: ["crypto-market/*.csv (OHLCV bars)", "crypto-trades/*.csv (raw trades)", "equity/market_data.csv", "equity/trade_data.csv", "equity/ohlcv.csv"],
    outputs: ["DataFrames in memory"],
    tech: ["pandas", "pathlib"],
    keyInsight: "~2M+ crypto trades across 8 symbols, processed per-symbol for efficiency.",
  },
  rules: {
    title: "Rule-Based Detectors",
    icon: <Search className="h-5 w-5" />,
    color: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    description:
      "Hand-crafted heuristics scan every trade for known manipulation patterns: P3 (crypto), P1 (equity order book), P2 (SEC / drift). For P3 crypto, detectors merge with priority and trim caps; the next canvas node (Pass 2) confirms candidates before anything is written to submission.csv.",
    inputs: ["Raw trade/market DataFrames", "config.yaml thresholds"],
    outputs: [
      "P3: merged candidate rows (trim + priority dedupe)",
      "P1: outputs/p1_alerts.csv",
      "P2: outputs/p2_signals.csv",
    ],
    tech: ["numpy", "pandas", "rolling z-scores", "merge_asof"],
    keyInsight:
      "P3 crypto emits many violation types (wash, spoofing, layering_echo, pump_and_dump, …). Only Pass 2–confirmed P3 rows become submission.csv.",
  },
  pass2: {
    title: "P3 Pass 2 — Detector confirmation",
    icon: <ShieldCheck className="h-5 w-5" />,
    color: "bg-sky-500/15 text-sky-800 dark:text-sky-300",
    description:
      "Runs immediately after P3 rule merge in code (bits_hackathon/detectors/p3_pass2.py). Each row must appear in the detector output for its violation_type; peg_break and spoofing optionally use stricter thresholds (p3.pass2 in config.yaml). Dropped rows never reach submission.csv.",
    inputs: [
      "Merged P3 candidate rows from p3_crypto.run_all_detectors",
      "config.yaml → p3.pass2.enabled, write_audit, spoofing_bps_multiplier, peg_deviation_multiplier",
    ],
    outputs: [
      "outputs/submission.csv (judge CSV; Pass 2–filtered)",
      "outputs/p3_second_pass_audit.csv (trade_id, violation_type, decision, reason)",
      "GET /api/outputs/p3_pass2_audit (JSON)",
      "frontend/public/data/p3_pass2_audit.json (after sync_frontend_data.py)",
    ],
    tech: ["pandas", "same detectors re-run for membership + stricter peg/spoof"],
    keyInsight:
      "This is separate from the AI “two-pass” LLM review. Pass 2 is deterministic rules verification aligned to the competition schema.",
  },
  ai: {
    title: "AI Ground Truth",
    icon: <Brain className="h-5 w-5" />,
    color: "bg-purple-500/15 text-purple-700 dark:text-purple-300",
    description:
      "A large language model independently evaluates every trade. Uses a two-pass strategy: fast stub analysis first to identify borderline cases, then deep LLM evaluation on the suspicious subset. Returns verdicts (suspicious/benign/uncertain), confidence scores, and reasoning.",
    inputs: ["Raw trade data", "OpenRouter API key", "Bar context per trade"],
    outputs: ["ground_truth.csv (LLM verdicts per trade)"],
    tech: ["OpenRouter API", "nvidia/nemotron", "ThreadPoolExecutor", "retry logic"],
    keyInsight: "The AI often catches structuring and ramping patterns that rules miss — complementary perspective vs fixed thresholds.",
  },
  compare: {
    title: "Comparison Engine",
    icon: <GitCompare className="h-5 w-5" />,
    color: "bg-green-500/15 text-green-700 dark:text-green-300",
    description:
      "Aligns rule-based flags against AI verdicts to measure agreement. For every trade, marks whether rules flagged it, AI flagged it, or both. Calculates per-symbol and per-violation-type agreement rates. This comparison is the training signal for the ML re-ranker.",
    inputs: [
      "outputs/submission.csv (Pass 2–confirmed P3 rules)",
      "outputs/ground_truth.csv",
    ],
    outputs: ["outputs/comparison_report.csv", "GET /api/outputs/comparison_report"],
    tech: ["pandas merge", "set operations"],
    keyInsight: "Agreement rate reveals which rule detectors are accurate (wash trade rules agree ~80% with AI) vs noisy (pump-and-dump rules disagree ~90%).",
  },
  ml1: {
    title: "ML Stage 1 — Binary triage",
    icon: <Cpu className="h-5 w-5" />,
    color: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
    description:
      "HistGradientBoosting + probability calibration (isotonic/sigmoid). Trained on weak labels from rules vs AI agreement (labels.py) with sample weights. Produces p_suspicious for every trade and a tuned threshold; artifacts saved under artifacts/stage1_*.joblib + stage1_meta.json.",
    inputs: ["comparison_report.csv", "ground_truth.csv", "Engineered trade+bar features (ml_features.py)"],
    outputs: ["artifacts/stage1_*.joblib", "stage1_meta.json", "training_snapshot.csv"],
    tech: ["scikit-learn", "HistGradientBoostingClassifier", "CalibratedClassifierCV", "StandardScaler"],
    keyInsight:
      "Training loads the same trade + bar tables as rules (no separate line on the diagram). CLI: python run.py train-ml or infer-ml. Threshold uses a time-based holdout.",
  },
  ml2: {
    title: "ML Stage 2 — Violation type",
    icon: <Cpu className="h-5 w-5" />,
    color: "bg-pink-500/15 text-pink-700 dark:text-pink-300",
    description:
      "Second classifier on high-confidence positive rows predicts violation_type (multiclass). Low confidence falls back to anomaly / GT lookup. Writes stage2 artifacts when enough class support exists; otherwise skipped with meta only.",
    inputs: ["Stage-1 scored frame", "label_violation_type from weak labels"],
    outputs: ["artifacts/stage2_*.joblib", "submission_ml.csv (with ml_p_suspicious, ml_stage2_confidence)"],
    tech: ["HistGradientBoostingClassifier", "LabelEncoder", "Per-class min count → other bucket"],
    keyInsight: "Committee can prefer ML type when ml_stage2_confidence ≥ config threshold (committee.use_staged_ml_types).",
  },
  committee: {
    title: "Committee Fusion",
    icon: <Users className="h-5 w-5" />,
    color: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
    description:
      "Three-way voting system combining Rules, AI, and ML. Tier 1 (2+ sources agree) is auto-included. Tier 2 (single source) is selectively triaged: AI-only flags kept if confidence ≥ threshold, most rule-only flags dropped (noisy heuristics), ML-only flags dropped (insufficient corroboration).",
    inputs: [
      "outputs/submission.csv",
      "outputs/ground_truth.csv",
      "outputs/submission_ml.csv",
    ],
    outputs: ["submission_committee.csv", "committee_report.txt"],
    tech: ["set intersection/difference", "confidence thresholds per violation type"],
    keyInsight: "Tier 1 = two or more of {rules, AI, ML} agree; Tier 2 triages single-source rows using confidence and violation-type rules. Zone counts vary per run.",
  },
  tuning: {
    title: "Parameter Tuning",
    icon: <SlidersHorizontal className="h-5 w-5" />,
    color: "bg-teal-500/15 text-teal-700 dark:text-teal-300",
    description:
      "Analyzes where rules over-flag or under-flag relative to AI, and suggests specific threshold adjustments. Feeds back into config.yaml so the next pipeline run benefits from learned insights.",
    inputs: ["comparison_report.csv", "Current config.yaml thresholds"],
    outputs: ["tuning_report.txt"],
    tech: ["Statistical analysis", "per-violation-type breakdown"],
    keyInsight: "Creates a feedback loop: run pipeline → compare → tune → re-run with better thresholds. Each iteration improves precision.",
  },
  outputs: {
    title: "Output Artifacts",
    icon: <FileOutput className="h-5 w-5" />,
    color: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-300",
    description:
      "All pipeline stages write their results to the outputs/ directory. CSV files contain the flagged trades with violation types and remarks. Text reports contain human-readable summaries of metrics and recommendations.",
    inputs: ["All pipeline stages"],
    outputs: [
      "submission*.csv",
      "p3_second_pass_audit.csv",
      "ground_truth.csv",
      "comparison_report.csv",
      "training_snapshot.csv",
      "ml_baseline_report.txt",
      "ml_evaluation_report.txt",
      "*.txt reports",
    ],
    tech: ["CSV format", "JSONL for audit log"],
    keyInsight: "The committee submission is the final, highest-confidence output — it represents the combined intelligence of rules, AI, and ML.",
  },
  dashboard: {
    title: "Dashboard (You Are Here)",
    icon: <Monitor className="h-5 w-5" />,
    color: "bg-orange-500/15 text-orange-700 dark:text-orange-300",
    description:
      "Next.js + shadcn/ui frontend with FastAPI backend. Seven analytical pages plus this workflow view. Analysts can browse flagged trades, drill into committee zones, compare approaches, trigger pipeline runs, upload new data, and record HITL decisions.",
    inputs: [
      "FastAPI /api/outputs/*",
      "outputs/*.csv (incl. submission.csv, p3_second_pass_audit.csv)",
      "outputs/*.txt",
      "/api/ml/health",
    ],
    outputs: ["Interactive visualizations", "HITL decisions (feedback/decisions.jsonl)"],
    tech: ["Next.js 16", "React 19", "shadcn/ui", "Recharts", "React Flow", "FastAPI"],
    keyInsight:
      "After pipeline runs, run python3 scripts/sync_frontend_data.py so public/data/*.json (submission, p3_pass2_audit, ml_health, …) matches outputs/ — or use the API on localhost:8000.",
  },
};

/* ------------------------------------------------------------------ */
/*  Custom node component — multi-handle layout to avoid edge spaghetti */
/* ------------------------------------------------------------------ */

const handleClass =
  "!border-2 !border-background !bg-muted-foreground !w-2.5 !h-2.5";

function PipelineNode({ data }: { data: { label: string; nodeId: string; tier: string; emoji: string } }) {
  const tierColors: Record<string, string> = {
    input: "border-blue-400/60 bg-blue-50 dark:bg-blue-950/40",
    detection: "border-amber-400/60 bg-amber-50 dark:bg-amber-950/40",
    verify: "border-sky-400/60 bg-sky-50 dark:bg-sky-950/40",
    ai: "border-purple-400/60 bg-purple-50 dark:bg-purple-950/40",
    analysis: "border-green-400/60 bg-green-50 dark:bg-green-950/40",
    ml: "border-rose-400/60 bg-rose-50 dark:bg-rose-950/40",
    fusion: "border-indigo-400/60 bg-indigo-50 dark:bg-indigo-950/40",
    tuning: "border-teal-400/60 bg-teal-50 dark:bg-teal-950/40",
    output: "border-cyan-400/60 bg-cyan-50 dark:bg-cyan-950/40",
    ui: "border-orange-400/60 bg-orange-50 dark:bg-orange-950/40",
  };

  const id = data.nodeId;

  return (
    <>
      {/* ---- Targets (top / left) ---- */}
      {id === "rules" && (
        <>
          <Handle id="in-input" type="target" position={Position.Top} style={{ left: "38%" }} className={handleClass} />
          <Handle id="in-tune" type="target" position={Position.Top} style={{ left: "62%" }} className={handleClass} />
        </>
      )}
      {id === "ai" && <Handle id="in-input" type="target" position={Position.Top} className={handleClass} />}
      {id === "compare" && (
        <Handle id="in-merge" type="target" position={Position.Top} className={handleClass} />
      )}
      {id === "committee" && (
        <>
          <Handle id="in-rules" type="target" position={Position.Top} style={{ left: "18%" }} className={handleClass} />
          <Handle id="in-ml" type="target" position={Position.Top} style={{ left: "50%" }} className={handleClass} />
          <Handle id="in-ai" type="target" position={Position.Top} style={{ left: "82%" }} className={handleClass} />
        </>
      )}
      {(id === "ml1" || id === "ml2" || id === "outputs" || id === "dashboard") && (
        <Handle id="in-main" type="target" position={Position.Top} className={handleClass} />
      )}
      {id === "tuning" && (
        <Handle id="in-compare" type="target" position={Position.Left} className={handleClass} />
      )}

      <div
        className={cn(
          "rounded-xl border-2 px-5 py-3 shadow-md transition-shadow hover:shadow-lg cursor-pointer min-w-[160px] max-w-[200px] text-center",
          tierColors[data.tier] ?? "border-border bg-card"
        )}
      >
        <div className="text-lg mb-0.5">{data.emoji}</div>
        <div className="text-sm font-semibold leading-tight whitespace-pre-line">{data.label}</div>
      </div>

      {/* ---- Sources (bottom / right) ---- */}
      {id === "input" && (
        <>
          <Handle id="out-rules" type="source" position={Position.Bottom} style={{ left: "32%" }} className={handleClass} />
          <Handle id="out-ai" type="source" position={Position.Bottom} style={{ left: "68%" }} className={handleClass} />
        </>
      )}
      {id === "rules" && (
        <Handle id="out-pass2" type="source" position={Position.Bottom} className={handleClass} />
      )}
      {id === "pass2" && (
        <>
          <Handle id="in-rules" type="target" position={Position.Top} className={handleClass} />
          <Handle id="out-compare" type="source" position={Position.Bottom} style={{ left: "35%" }} className={handleClass} />
          <Handle id="out-committee" type="source" position={Position.Bottom} style={{ left: "65%" }} className={handleClass} />
        </>
      )}
      {id === "ai" && (
        <>
          <Handle id="out-compare" type="source" position={Position.Bottom} style={{ left: "35%" }} className={handleClass} />
          <Handle id="out-committee" type="source" position={Position.Bottom} style={{ left: "65%" }} className={handleClass} />
        </>
      )}
      {id === "compare" && (
        <>
          <Handle id="out-ml1" type="source" position={Position.Bottom} className={handleClass} />
          <Handle id="out-tuning" type="source" position={Position.Right} className={handleClass} />
        </>
      )}
      {id === "ml1" && <Handle id="out" type="source" position={Position.Bottom} className={handleClass} />}
      {id === "ml2" && <Handle id="out" type="source" position={Position.Bottom} className={handleClass} />}
      {id === "committee" && <Handle id="out" type="source" position={Position.Bottom} className={handleClass} />}
      {id === "outputs" && <Handle id="out" type="source" position={Position.Bottom} className={handleClass} />}
      {id === "tuning" && (
        <Handle id="out-rules" type="source" position={Position.Bottom} className={handleClass} />
      )}
    </>
  );
}

const nodeTypes: NodeTypes = {
  pipeline: PipelineNode,
};

/* ------------------------------------------------------------------ */
/*  Graph definition                                                  */
/* ------------------------------------------------------------------ */

/* Center spine x ≈ 420; detectors on wings; orthogonal step edges + handle IDs reduce crossings. */
const initialNodes: Node[] = [
  { id: "input", type: "pipeline", position: { x: 380, y: 0 }, data: { label: "Input Data", nodeId: "input", tier: "input", emoji: "📊" } },

  { id: "rules", type: "pipeline", position: { x: 40, y: 160 }, data: { label: "Rule-Based\nDetectors", nodeId: "rules", tier: "detection", emoji: "🔍" } },
  {
    id: "pass2",
    type: "pipeline",
    position: { x: 40, y: 268 },
    data: { label: "P3 Pass 2\nConfirm", nodeId: "pass2", tier: "verify", emoji: "✓" },
  },
  { id: "ai", type: "pipeline", position: { x: 760, y: 160 }, data: { label: "AI Ground\nTruth (LLM)", nodeId: "ai", tier: "ai", emoji: "🧠" } },

  { id: "compare", type: "pipeline", position: { x: 380, y: 380 }, data: { label: "Comparison\nEngine", nodeId: "compare", tier: "analysis", emoji: "⚖️" } },

  { id: "ml1", type: "pipeline", position: { x: 380, y: 560 }, data: { label: "ML Stage 1\n(Binary triage)", nodeId: "ml1", tier: "ml", emoji: "🤖" } },
  { id: "ml2", type: "pipeline", position: { x: 380, y: 720 }, data: { label: "ML Stage 2\n(Violation type)", nodeId: "ml2", tier: "ml", emoji: "🎯" } },

  { id: "tuning", type: "pipeline", position: { x: 700, y: 360 }, data: { label: "Parameter\nTuning", nodeId: "tuning", tier: "tuning", emoji: "🎛️" } },

  { id: "committee", type: "pipeline", position: { x: 380, y: 880 }, data: { label: "Committee\nFusion", nodeId: "committee", tier: "fusion", emoji: "🗳️" } },

  { id: "outputs", type: "pipeline", position: { x: 380, y: 1040 }, data: { label: "Output\nArtifacts", nodeId: "outputs", tier: "output", emoji: "📁" } },

  { id: "dashboard", type: "pipeline", position: { x: 380, y: 1200 }, data: { label: "Dashboard", nodeId: "dashboard", tier: "ui", emoji: "🖥️" } },
];

const markerEnd = { type: MarkerType.ArrowClosed, width: 18, height: 18 };

const edgeStep = {
  type: "step" as const,
  pathOptions: { borderRadius: 14 },
  markerEnd,
};

const strokeMain = "hsl(var(--primary))";
const strokeSide = "hsl(var(--muted-foreground) / 0.55)";
const strokeFeedback = "hsl(var(--muted-foreground) / 0.45)";

const initialEdges: Edge[] = [
  {
    id: "e-input-rules",
    source: "input",
    target: "rules",
    sourceHandle: "out-rules",
    targetHandle: "in-input",
    label: "trades + bars",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-input-ai",
    source: "input",
    target: "ai",
    sourceHandle: "out-ai",
    targetHandle: "in-input",
    label: "trades + context",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-rules-pass2",
    source: "rules",
    target: "pass2",
    sourceHandle: "out-pass2",
    targetHandle: "in-rules",
    label: "P3 candidates",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-pass2-compare",
    source: "pass2",
    target: "compare",
    sourceHandle: "out-compare",
    targetHandle: "in-merge",
    label: "rule flags",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-ai-compare",
    source: "ai",
    target: "compare",
    sourceHandle: "out-compare",
    targetHandle: "in-merge",
    label: "AI verdicts",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-compare-ml1",
    source: "compare",
    target: "ml1",
    sourceHandle: "out-ml1",
    targetHandle: "in-main",
    label: "weak labels",
    ...edgeStep,
    animated: true,
    style: { strokeWidth: 2.5, stroke: strokeMain },
  },
  {
    id: "e-ml1-ml2",
    source: "ml1",
    target: "ml2",
    sourceHandle: "out",
    targetHandle: "in-main",
    label: "scores",
    ...edgeStep,
    animated: true,
    style: { strokeWidth: 2.5, stroke: strokeMain },
  },
  {
    id: "e-ml2-committee",
    source: "ml2",
    target: "committee",
    sourceHandle: "out",
    targetHandle: "in-ml",
    label: "submission_ml",
    ...edgeStep,
    animated: true,
    style: { strokeWidth: 2.5, stroke: strokeMain },
  },
  {
    id: "e-pass2-committee",
    source: "pass2",
    target: "committee",
    sourceHandle: "out-committee",
    targetHandle: "in-rules",
    label: "submission.csv",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide, strokeDasharray: "8 5" },
  },
  {
    id: "e-ai-committee",
    source: "ai",
    target: "committee",
    sourceHandle: "out-committee",
    targetHandle: "in-ai",
    label: "GT suspicious",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide, strokeDasharray: "8 5" },
  },
  {
    id: "e-committee-outputs",
    source: "committee",
    target: "outputs",
    sourceHandle: "out",
    targetHandle: "in-main",
    label: "final flags",
    ...edgeStep,
    animated: true,
    style: { strokeWidth: 2.5, stroke: strokeMain },
  },
  {
    id: "e-outputs-dashboard",
    source: "outputs",
    target: "dashboard",
    sourceHandle: "out",
    targetHandle: "in-main",
    label: "CSV / JSON",
    ...edgeStep,
    animated: true,
    style: { strokeWidth: 2.5, stroke: strokeMain },
  },
  {
    id: "e-compare-tuning",
    source: "compare",
    target: "tuning",
    sourceHandle: "out-tuning",
    targetHandle: "in-compare",
    label: "agreement",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeSide },
  },
  {
    id: "e-tuning-rules",
    source: "tuning",
    target: "rules",
    sourceHandle: "out-rules",
    targetHandle: "in-tune",
    label: "config hints",
    ...edgeStep,
    animated: false,
    style: { strokeWidth: 2, stroke: strokeFeedback, strokeDasharray: "6 6" },
  },
];

/* ------------------------------------------------------------------ */
/*  Detail panel                                                      */
/* ------------------------------------------------------------------ */

function DetailPanel({
  stepId,
  onClose,
}: {
  stepId: string;
  onClose: () => void;
}) {
  const detail = STEP_DETAILS[stepId];
  if (!detail) return null;

  return (
    <Card className="absolute right-4 top-4 z-50 w-[380px] max-h-[calc(100%-2rem)] overflow-y-auto shadow-xl border-2">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn("rounded-lg p-2", detail.color)}>{detail.icon}</span>
            <CardTitle className="text-base">{detail.title}</CardTitle>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 hover:bg-muted transition-colors"
            aria-label="Close detail panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-muted-foreground leading-relaxed">{detail.description}</p>

        <div>
          <h4 className="font-semibold mb-1.5">Inputs</h4>
          <ul className="space-y-1">
            {detail.inputs.map((inp) => (
              <li key={inp} className="flex items-start gap-2 text-muted-foreground">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                <span className="font-mono text-xs">{inp}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="font-semibold mb-1.5">Outputs</h4>
          <ul className="space-y-1">
            {detail.outputs.map((out) => (
              <li key={out} className="flex items-start gap-2 text-muted-foreground">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
                <span className="font-mono text-xs">{out}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="font-semibold mb-1.5">Tech Stack</h4>
          <div className="flex flex-wrap gap-1.5">
            {detail.tech.map((t) => (
              <Badge key={t} variant="secondary" className="text-xs">
                {t}
              </Badge>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-1">
            Key Insight
          </h4>
          <p className="text-sm leading-relaxed">{detail.keyInsight}</p>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default function WorkflowPage() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      <div className="mb-4 space-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Pipeline Workflow
          </h1>
          <p className="text-sm text-muted-foreground">
            Click a node for details. Drag nodes to rearrange; scroll to zoom. The{" "}
            <span className="text-sky-600 dark:text-sky-400 font-medium">
              P3 Pass 2
            </span>{" "}
            node sits under Rule-Based Detectors: it confirms crypto rule candidates
            before{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[10px]">submission.csv</code>{" "}
            and{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[10px]">
              outputs/p3_second_pass_audit.csv
            </code>{" "}
            are written. The{" "}
            <span className="text-primary font-medium">green primary path</span> is
            the main spine (compare → ML → committee → outputs). Wing links and dashed
            lines are supporting feeds and feedback.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground border rounded-lg bg-muted/20 px-3 py-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-6 rounded-full bg-sky-500" aria-hidden />
            P3 Pass 2 verify
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-6 rounded-full bg-primary" aria-hidden />
            Main spine
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-6 rounded-full bg-muted-foreground/50" aria-hidden />
            Side inputs
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-0.5 w-6 rounded-full border border-dashed border-muted-foreground/50 bg-transparent"
              aria-hidden
            />
            Direct feed / feedback
          </span>
        </div>
      </div>

      <div className="relative flex-1 rounded-lg border bg-card overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15, maxZoom: 1.25 }}
          minZoom={0.22}
          maxZoom={1.65}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: "step" }}
        >
          <Background gap={20} size={1} />
          <Controls showInteractive={false} />
          <MiniMap
            nodeStrokeWidth={3}
            zoomable
            pannable
            className="!bg-muted/50 !border-border rounded-lg"
          />
        </ReactFlow>

        {selectedNode && (
          <DetailPanel
            stepId={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
