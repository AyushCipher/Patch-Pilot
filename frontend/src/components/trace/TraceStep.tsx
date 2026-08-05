import { useState } from "react";
import { ChevronDown, ChevronRight, FileSearch, PlayCircle, Wrench, MessageSquare, FlaskConical } from "lucide-react";
import type { TraceEvent } from "../../types";

const ICONS: Record<string, typeof Wrench> = {
  tool_call: Wrench,
  tool_result: FileSearch,
  llm_message: MessageSquare,
  initial_test_result: FlaskConical,
  post_patch_test_result: FlaskConical,
  run_started: PlayCircle,
};

function summarize(event: TraceEvent): string {
  switch (event.type) {
    case "run_started":
      return "Run started";
    case "sandbox_ready":
      return "Sandbox prepared";
    case "initial_test_result":
      return `Initial tests: ${event.passed} passed, ${event.failed} failed, ${event.errors} errors`;
    case "iteration_started":
      return `Iteration ${event.iteration} started`;
    case "llm_message":
      return `Agent reasoning (iteration ${event.iteration})`;
    case "tool_call":
      return `Calling tool: ${event.tool}`;
    case "tool_result":
      return `Result from ${event.tool}`;
    case "post_patch_test_result":
      return `Re-ran tests: ${event.passed} passed, ${event.failed} failed, ${event.errors} errors`;
    case "agent_stopped_without_patch":
      return "Agent paused without writing a patch";
    case "run_completed":
      return event.success ? "Run completed - tests passing" : "Run completed - tests still failing";
    case "run_failed":
      return `Run failed: ${event.reason}`;
    case "llm_error":
      return `LLM error: ${event.error}`;
    default:
      return event.type;
  }
}

export function TraceStep({ event }: { event: TraceEvent }) {
  const [open, setOpen] = useState(false);
  const Icon = ICONS[event.type] ?? PlayCircle;
  const hasDetail = Object.keys(event).length > 2;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40">
      <button
        onClick={() => hasDetail && setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800/40"
      >
        <Icon size={15} className="shrink-0 text-teal-400" />
        <span className="flex-1 truncate">{summarize(event)}</span>
        {hasDetail && (open ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
      </button>
      {open && hasDetail && (
        <pre className="overflow-x-auto border-t border-slate-800 bg-slate-950 p-3 text-xs text-slate-400">
          {JSON.stringify(event, null, 2)}
        </pre>
      )}
    </div>
  );
}
