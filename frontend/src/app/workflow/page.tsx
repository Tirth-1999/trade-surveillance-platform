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
      "Hand-crafted heuristics scan every trade for known manipulation patterns. Three problem tracks: P3 (crypto trade surveillance), P1 (equity order book anomalies), P2 (SEC 8-K pre-announcement drift). Rules are fast and fully interpretable.",
    inputs: ["Raw trade/market DataFrames", "config.yaml thresholds"],
    outputs: ["submission.csv (P3 flags)", "p1_alerts.csv", "p2_signals.csv"],
    tech: ["numpy", "pandas", "rolling z-scores", "merge_asof"],
    keyInsight: "Detects 8 violation types: wash trading, spoofing, layering, pump-and-dump, ramping, AML structuring, peg manipulation, bar-range anomalies.",
  },
  ai: {
    title: "AI Ground Truth",
    icon: <Brain className="h-5 w-5" />,
    color: "bg-purple-500/15 text-purple-700 dark:text-purple-300",
    description:
      "A large language model independently evaluates every trade. Uses a two-pass strategy: fast stub analysis first to identify borderline cases, then deep LLM evaluation on the suspicious subset. Returns verdicts (suspicious/benign/uncertain), confidence scores, and reasoning.",
    inputs: ["Raw trade data", "OpenRouter API key", "Bar context per trade"],
    outputs: ["ground_truth.csv (312 suspicious out of 19,256)"],
    tech: ["OpenRouter API", "nvidia/nemotron", "ThreadPoolExecutor", "retry logic"],
    keyInsight: "The AI often catches structuring and ramping patterns that rules miss — complementary perspective vs fixed thresholds.",
  },
  compare: {
    title: "Comparison Engine",
    icon: <GitCompare className="h-5 w-5" />,
    color: "bg-green-500/15 text-green-700 dark:text-green-300",
    description:
      "Aligns rule-based flags against AI verdicts to measure agreement. For every trade, marks whether rules flagged it, AI flagged it, or both. Calculates per-symbol and per-violation-type agreement rates. This comparison is the training signal for the ML re-ranker.",
    inputs: ["submission.csv", "ground_truth.csv"],
    outputs: ["comparison_report.csv"],
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
    keyInsight: "CLI: python run.py train-ml or infer-ml. Threshold is chosen on a time-based holdout to balance precision vs recall.",
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
    inputs: ["submission.csv", "ground_truth.csv", "submission_ml.csv"],
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
    outputs: ["submission*.csv", "ground_truth.csv", "comparison_report.csv", "training_snapshot.csv", "ml_baseline_report.txt", "ml_evaluation_report.txt", "*.txt reports"],
    tech: ["CSV format", "JSONL for audit log"],
    keyInsight: "The committee submission is the final, highest-confidence output — it represents the combined intelligence of rules, AI, and ML.",
  },
  dashboard: {
    title: "Dashboard (You Are Here)",
    icon: <Monitor className="h-5 w-5" />,
    color: "bg-orange-500/15 text-orange-700 dark:text-orange-300",
    description:
      "Next.js + shadcn/ui frontend with FastAPI backend. Seven analytical pages plus this workflow view. Analysts can browse flagged trades, drill into committee zones, compare approaches, trigger pipeline runs, upload new data, and record HITL decisions.",
    inputs: ["FastAPI endpoints", "outputs/*.csv", "outputs/*.txt", "/api/ml/health"],
    outputs: ["Interactive visualizations", "HITL decisions (feedback/decisions.jsonl)"],
    tech: ["Next.js 16", "React 19", "shadcn/ui", "Recharts", "React Flow", "FastAPI"],
    keyInsight: "After train-ml, run python3 scripts/sync_frontend_data.py so static fallback JSON (including ml_health) matches your latest run — or use the API on localhost:8000.",
  },
};

/* ------------------------------------------------------------------ */
/*  Custom node component                                             */
/* ------------------------------------------------------------------ */

function PipelineNode({ data }: { data: { label: string; nodeId: string; tier: string; emoji: string } }) {
  const tierColors: Record<string, string> = {
    input: "border-blue-400/60 bg-blue-50 dark:bg-blue-950/40",
    detection: "border-amber-400/60 bg-amber-50 dark:bg-amber-950/40",
    ai: "border-purple-400/60 bg-purple-50 dark:bg-purple-950/40",
    analysis: "border-green-400/60 bg-green-50 dark:bg-green-950/40",
    ml: "border-rose-400/60 bg-rose-50 dark:bg-rose-950/40",
    fusion: "border-indigo-400/60 bg-indigo-50 dark:bg-indigo-950/40",
    tuning: "border-teal-400/60 bg-teal-50 dark:bg-teal-950/40",
    output: "border-cyan-400/60 bg-cyan-50 dark:bg-cyan-950/40",
    ui: "border-orange-400/60 bg-orange-50 dark:bg-orange-950/40",
  };

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground !w-2 !h-2" />
      <div
        className={cn(
          "rounded-xl border-2 px-5 py-3 shadow-md transition-shadow hover:shadow-lg cursor-pointer min-w-[160px] text-center",
          tierColors[data.tier] ?? "border-border bg-card"
        )}
      >
        <div className="text-lg mb-0.5">{data.emoji}</div>
        <div className="text-sm font-semibold leading-tight">{data.label}</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground !w-2 !h-2" />
    </>
  );
}

const nodeTypes: NodeTypes = {
  pipeline: PipelineNode,
};

/* ------------------------------------------------------------------ */
/*  Graph definition                                                  */
/* ------------------------------------------------------------------ */

const initialNodes: Node[] = [
  { id: "input", type: "pipeline", position: { x: 400, y: 0 }, data: { label: "Input Data", nodeId: "input", tier: "input", emoji: "📊" } },

  { id: "rules", type: "pipeline", position: { x: 120, y: 130 }, data: { label: "Rule-Based\nDetectors", nodeId: "rules", tier: "detection", emoji: "🔍" } },
  { id: "ai", type: "pipeline", position: { x: 680, y: 130 }, data: { label: "AI Ground\nTruth (LLM)", nodeId: "ai", tier: "ai", emoji: "🧠" } },

  { id: "compare", type: "pipeline", position: { x: 400, y: 270 }, data: { label: "Comparison\nEngine", nodeId: "compare", tier: "analysis", emoji: "⚖️" } },

  { id: "ml1", type: "pipeline", position: { x: 220, y: 400 }, data: { label: "ML Stage 1\n(Binary triage)", nodeId: "ml1", tier: "ml", emoji: "🤖" } },
  { id: "ml2", type: "pipeline", position: { x: 400, y: 400 }, data: { label: "ML Stage 2\n(Violation type)", nodeId: "ml2", tier: "ml", emoji: "🎯" } },
  { id: "tuning", type: "pipeline", position: { x: 680, y: 400 }, data: { label: "Parameter\nTuning", nodeId: "tuning", tier: "tuning", emoji: "🎛️" } },

  { id: "committee", type: "pipeline", position: { x: 400, y: 560 }, data: { label: "Committee\nFusion", nodeId: "committee", tier: "fusion", emoji: "🗳️" } },

  { id: "outputs", type: "pipeline", position: { x: 400, y: 700 }, data: { label: "Output\nArtifacts", nodeId: "outputs", tier: "output", emoji: "📁" } },

  { id: "dashboard", type: "pipeline", position: { x: 400, y: 840 }, data: { label: "Dashboard", nodeId: "dashboard", tier: "ui", emoji: "🖥️" } },
];

const edgeDefaults = {
  animated: true,
  style: { strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
};

const initialEdges: Edge[] = [
  { id: "e-input-rules", source: "input", target: "rules", label: "trades + bars", ...edgeDefaults },
  { id: "e-input-ai", source: "input", target: "ai", label: "trades + context", ...edgeDefaults },
  { id: "e-input-ml1", source: "input", target: "ml1", label: "features", ...edgeDefaults, style: { strokeWidth: 1.5, strokeDasharray: "5 3" } },
  { id: "e-rules-compare", source: "rules", target: "compare", label: "rule flags", ...edgeDefaults },
  { id: "e-ai-compare", source: "ai", target: "compare", label: "AI verdicts", ...edgeDefaults },
  { id: "e-compare-ml1", source: "compare", target: "ml1", label: "weak labels", ...edgeDefaults },
  { id: "e-ml1-ml2", source: "ml1", target: "ml2", label: "p_suspicious", ...edgeDefaults },
  { id: "e-compare-tuning", source: "compare", target: "tuning", label: "agreement stats", ...edgeDefaults },
  { id: "e-rules-committee", source: "rules", target: "committee", label: "rule flags", ...edgeDefaults, style: { strokeWidth: 1.5, strokeDasharray: "6 3" } },
  { id: "e-ai-committee", source: "ai", target: "committee", label: "AI flags", ...edgeDefaults, style: { strokeWidth: 1.5, strokeDasharray: "6 3" } },
  { id: "e-ml2-committee", source: "ml2", target: "committee", label: "submission_ml", ...edgeDefaults },
  { id: "e-committee-outputs", source: "committee", target: "outputs", label: "final flags", ...edgeDefaults },
  { id: "e-outputs-dashboard", source: "outputs", target: "dashboard", label: "CSV / JSON / ml/health", ...edgeDefaults },
  { id: "e-tuning-rules", source: "tuning", target: "rules", label: "threshold updates", ...edgeDefaults, style: { strokeWidth: 1.5, strokeDasharray: "4 4" }, animated: true },
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
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">
          Pipeline Workflow
        </h1>
        <p className="text-sm text-muted-foreground">
          Interactive mind map of the trade surveillance pipeline. Click any node for details. Drag to rearrange, scroll to zoom.
        </p>
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
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
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
