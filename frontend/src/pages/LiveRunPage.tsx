import { useEffect, useMemo, useState } from "react";
import { PlayCircle, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Layout } from "../components/layout/Layout";
import { TopBar } from "../components/layout/TopBar";
import { TraceStep } from "../components/trace/TraceStep";
import { Badge, difficultyTone } from "../components/ui/Badge";
import { getRunStatus, listBugs, startRunAgainstBug } from "../api/client";
import { useRunTraceSocket } from "../hooks/useWebSocket";
import type { BugBankEntry, RunStatus } from "../types";

export function LiveRunPage() {
  const [bugs, setBugs] = useState<BugBankEntry[]>([]);
  const [selectedBugId, setSelectedBugId] = useState<string>("");
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const { events, finished } = useRunTraceSocket(runId);

  useEffect(() => {
    listBugs()
      .then((data) => {
        setBugs(data);
        if (data.length > 0) setSelectedBugId(data[0].bug_id);
      })
      .catch(() => setStartError("Could not reach the PatchPilot API. Is the backend running?"));
  }, []);

  useEffect(() => {
    if (!runId || !finished) return;
    getRunStatus(runId).then(setRunStatus);
  }, [runId, finished]);

  const selectedBug = useMemo(
    () => bugs.find((b) => b.bug_id === selectedBugId),
    [bugs, selectedBugId],
  );

  async function handleStart() {
    if (!selectedBugId) return;
    setStarting(true);
    setStartError(null);
    setRunStatus(null);
    try {
      const summary = await startRunAgainstBug(selectedBugId);
      setRunId(summary.run_id);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }

  const isRunning = runId !== null && !finished;

  return (
    <Layout>
      <TopBar
        title="Live Run"
        subtitle="Watch PatchPilot investigate and fix a bug step by step"
      />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <div className="w-full shrink-0 lg:w-80">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <label className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Bug bank entry
            </label>
            <select
              value={selectedBugId}
              onChange={(e) => setSelectedBugId(e.target.value)}
              disabled={isRunning}
              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 disabled:opacity-50"
            >
              {bugs.map((bug) => (
                <option key={bug.bug_id} value={bug.bug_id}>
                  {bug.bug_id}
                </option>
              ))}
            </select>

            {selectedBug && (
              <div className="mt-3 flex flex-col gap-2">
                <Badge tone={difficultyTone(selectedBug.difficulty)}>{selectedBug.difficulty}</Badge>
                <p className="text-xs text-slate-400">{selectedBug.description}</p>
              </div>
            )}

            <button
              onClick={handleStart}
              disabled={starting || isRunning || !selectedBugId}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-teal-500 px-3 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRunning ? <Loader2 size={16} className="animate-spin" /> : <PlayCircle size={16} />}
              {isRunning ? "Running..." : "Run PatchPilot"}
            </button>

            {startError && <p className="mt-3 text-xs text-rose-400">{startError}</p>}
          </div>

          {runStatus?.result && (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex items-center gap-2">
                {runStatus.result.success ? (
                  <CheckCircle2 className="text-emerald-400" size={18} />
                ) : (
                  <XCircle className="text-rose-400" size={18} />
                )}
                <span className="text-sm font-semibold">
                  {runStatus.result.success ? "Tests passing" : "Did not converge"}
                </span>
              </div>
              <dl className="mt-3 space-y-1 text-xs text-slate-400">
                <div className="flex justify-between">
                  <dt>Iterations</dt>
                  <dd>{runStatus.result.iterations}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Input tokens</dt>
                  <dd>{runStatus.result.input_tokens}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Output tokens</dt>
                  <dd>{runStatus.result.output_tokens}</dd>
                </div>
              </dl>
              {runStatus.result.summary && (
                <p className="mt-3 rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
                  {runStatus.result.summary}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-200">Reasoning trace</h2>
            {events.length === 0 ? (
              <p className="text-sm text-slate-500">
                Select a bug and click "Run PatchPilot" to watch the agent work.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {events.map((event, i) => (
                  <TraceStep key={i} event={event} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
