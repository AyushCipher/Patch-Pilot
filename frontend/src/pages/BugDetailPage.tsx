import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Layout } from "../components/layout/Layout";
import { TopBar } from "../components/layout/TopBar";
import { TraceStep } from "../components/trace/TraceStep";
import { DiffViewer } from "../components/ui/DiffViewer";
import { Badge, difficultyTone } from "../components/ui/Badge";
import { getBugDetail } from "../api/client";
import type { BugDetailResponse } from "../types";
import { formatUsd } from "../utils/format";

export function BugDetailPage() {
  const { bugId } = useParams<{ bugId: string }>();
  const [detail, setDetail] = useState<BugDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bugId) return;
    getBugDetail(bugId)
      .then(setDetail)
      .catch(() => setError(`No eval result found for ${bugId}.`));
  }, [bugId]);

  return (
    <Layout>
      <Link to="/leaderboard" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-400 hover:text-teal-400">
        <ArrowLeft size={14} /> Back to leaderboard
      </Link>
      <TopBar title={bugId ?? "Bug detail"} />

      {error && <p className="mt-6 text-sm text-slate-400">{error}</p>}

      {detail && (
        <div className="mt-6 flex flex-col gap-6 lg:flex-row">
          <div className="w-full lg:w-72 shrink-0">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <Badge tone={difficultyTone(detail.result.difficulty)}>{detail.result.difficulty}</Badge>
              <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">{detail.result.bug_type}</p>
              <dl className="mt-4 space-y-2 text-xs text-slate-400">
                <div className="flex justify-between">
                  <dt>Outcome</dt>
                  <dd className={detail.result.success ? "text-emerald-400" : "text-rose-400"}>
                    {detail.result.success ? "Pass" : "Fail"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>Iterations</dt>
                  <dd>{detail.result.iterations}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Wall clock</dt>
                  <dd>{detail.result.wall_clock_seconds.toFixed(1)}s</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Tokens (in/out)</dt>
                  <dd>
                    {detail.result.input_tokens}/{detail.result.output_tokens}
                  </dd>
                </div>
                {detail.result.estimated_cost_usd != null && (
                  <div className="flex justify-between">
                    <dt>Est. cost</dt>
                    <dd>{formatUsd(detail.result.estimated_cost_usd)}</dd>
                  </div>
                )}
                {detail.result.failure_mode && (
                  <div className="flex justify-between">
                    <dt>Failure mode</dt>
                    <dd>{detail.result.failure_mode}</dd>
                  </div>
                )}
              </dl>
              {detail.result.summary && (
                <p className="mt-4 rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
                  {detail.result.summary}
                </p>
              )}
              {!detail.result.success && detail.result.last_hypothesis && (
                <p className="mt-4 rounded-lg bg-slate-950 p-3 text-xs text-amber-300">
                  Last hypothesis: {detail.result.last_hypothesis}
                </p>
              )}
            </div>

            {detail.expected_diff && (
              <div className="mt-4">
                <h2 className="mb-2 text-sm font-semibold text-slate-200">Reference fix</h2>
                <DiffViewer diff={detail.expected_diff} />
              </div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h2 className="mb-3 text-sm font-semibold text-slate-200">Reasoning trace</h2>
            <div className="flex flex-col gap-2">
              {detail.trace.map((event, i) => (
                <TraceStep key={i} event={event} />
              ))}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
