import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";
import { Layout } from "../components/layout/Layout";
import { TopBar } from "../components/layout/TopBar";
import { StatCard } from "../components/ui/StatCard";
import { Badge, difficultyTone } from "../components/ui/Badge";
import { getEvalReport } from "../api/client";
import type { Difficulty, HarnessReport } from "../types";
import { formatPct, formatSeconds, formatTier, formatUsd } from "../utils/format";

type SortKey = "bug_id" | "difficulty" | "iterations" | "wall_clock_seconds";
type FilterDifficulty = Difficulty | "all";
type FilterOutcome = "all" | "pass" | "fail";

export function EvalLeaderboardPage() {
  const [report, setReport] = useState<HarnessReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [difficultyFilter, setDifficultyFilter] = useState<FilterDifficulty>("all");
  const [outcomeFilter, setOutcomeFilter] = useState<FilterOutcome>("all");
  const [sortKey, setSortKey] = useState<SortKey>("bug_id");

  useEffect(() => {
    getEvalReport()
      .then(setReport)
      .catch((err) =>
        setError(
          err?.response?.status === 404
            ? "No eval report yet. Run `python eval/run_harness.py` to generate one."
            : "Failed to load eval report.",
        ),
      );
  }, []);

  const filteredResults = useMemo(() => {
    if (!report) return [];
    return report.results
      .filter((r) => difficultyFilter === "all" || r.difficulty === difficultyFilter)
      .filter(
        (r) =>
          outcomeFilter === "all" ||
          (outcomeFilter === "pass" ? r.success : !r.success),
      )
      .sort((a, b) => {
        if (sortKey === "bug_id") return a.bug_id.localeCompare(b.bug_id);
        if (sortKey === "difficulty") return a.difficulty.localeCompare(b.difficulty);
        if (sortKey === "iterations") return b.iterations - a.iterations;
        return b.wall_clock_seconds - a.wall_clock_seconds;
      });
  }, [report, difficultyFilter, outcomeFilter, sortKey]);

  if (error) {
    return (
      <Layout>
        <TopBar title="Eval Leaderboard" />
        <p className="mt-6 text-sm text-slate-400">{error}</p>
      </Layout>
    );
  }

  if (!report) {
    return (
      <Layout>
        <TopBar title="Eval Leaderboard" />
        <p className="mt-6 text-sm text-slate-500">Loading...</p>
      </Layout>
    );
  }

  const agg = report.aggregate;

  return (
    <Layout>
      <TopBar
        title="Eval Leaderboard"
        subtitle={`${agg.total_passed}/${agg.total_bugs} bugs fixed across the seeded bug bank`}
      />

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Overall pass rate" value={formatPct(agg.overall_pass_rate)} />
        <StatCard
          label="Easy"
          value={formatTier(agg.by_difficulty.easy)}
        />
        <StatCard
          label="Medium"
          value={formatTier(agg.by_difficulty.medium)}
        />
        <StatCard
          label="Hard"
          value={formatTier(agg.by_difficulty.hard)}
        />
        <StatCard
          label="Avg iterations to success"
          value={agg.avg_iterations_to_success?.toFixed(1) ?? "-"}
          hint={`avg to give up: ${agg.avg_iterations_to_giveup?.toFixed(1) ?? "-"}`}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard
          label="Estimated cost"
          value={formatUsd(agg.total_estimated_cost_usd)}
          hint={`${formatUsd(agg.avg_cost_per_successful_fix_usd)} avg per successful fix`}
        />
        <StatCard
          label="Latency (avg / median)"
          value={`${formatSeconds(agg.avg_wall_clock_seconds)} / ${formatSeconds(agg.median_wall_clock_seconds)}`}
          hint={`p90: ${formatSeconds(agg.p90_wall_clock_seconds)}`}
        />
        <StatCard
          label="Tokens (in / out)"
          value={`${agg.total_input_tokens.toLocaleString()} / ${agg.total_output_tokens.toLocaleString()}`}
        />
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <select
          value={difficultyFilter}
          onChange={(e) => setDifficultyFilter(e.target.value as FilterDifficulty)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="all">All difficulties</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <select
          value={outcomeFilter}
          onChange={(e) => setOutcomeFilter(e.target.value as FilterOutcome)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="all">All outcomes</option>
          <option value="pass">Passed</option>
          <option value="fail">Failed</option>
        </select>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="bug_id">Sort: bug id</option>
          <option value="difficulty">Sort: difficulty</option>
          <option value="iterations">Sort: iterations</option>
          <option value="wall_clock_seconds">Sort: time</option>
        </select>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Bug</th>
              <th className="px-4 py-3">Difficulty</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Iterations</th>
              <th className="px-4 py-3">Time (s)</th>
              <th className="px-4 py-3">Tokens (in/out)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {filteredResults.map((r) => (
              <tr key={r.bug_id} className="hover:bg-slate-900/40">
                <td className="px-4 py-3">
                  <Link to={`/bugs/${r.bug_id}`} className="font-medium text-teal-400 hover:underline">
                    {r.bug_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={difficultyTone(r.difficulty)}>{r.difficulty}</Badge>
                </td>
                <td className="px-4 py-3">
                  {r.success ? (
                    <span className="inline-flex items-center gap-1 text-emerald-400">
                      <CheckCircle2 size={14} /> Pass
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-rose-400">
                      <XCircle size={14} /> Fail
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-300">{r.iterations}</td>
                <td className="px-4 py-3 text-slate-300">{r.wall_clock_seconds.toFixed(1)}</td>
                <td className="px-4 py-3 text-slate-400">
                  {r.input_tokens}/{r.output_tokens}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}

