export type Difficulty = "easy" | "medium" | "hard";

export interface TraceEvent {
  type: string;
  timestamp: number;
  [key: string]: unknown;
}

export interface RunSummary {
  run_id: string;
  bug_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
}

export interface AgentReport {
  run_id: string;
  success: boolean;
  iterations: number;
  last_hypothesis: string | null;
  summary: string | null;
  input_tokens: number;
  output_tokens: number;
  trace_path: string;
}

export interface RunStatus {
  run_id: string;
  bug_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  result: AgentReport | null;
  error: string | null;
}

export interface BugBankEntry {
  bug_id: string;
  difficulty: Difficulty;
  bug_type: string;
  description: string;
}

export interface EvalResult {
  bug_id: string;
  difficulty: Difficulty;
  bug_type: string;
  success: boolean;
  iterations: number;
  wall_clock_seconds: number;
  input_tokens: number;
  output_tokens: number;
  last_hypothesis: string | null;
  summary: string | null;
  trace_path: string;
  error: string | null;
  failure_mode: string | null;
}

export interface TierStats {
  total: number;
  passed: number;
  pass_rate: number | null;
}

export interface EvalAggregate {
  total_bugs: number;
  total_passed: number;
  overall_pass_rate: number | null;
  by_difficulty: Record<Difficulty, TierStats>;
  avg_iterations_to_success: number | null;
  avg_iterations_to_giveup: number | null;
  most_common_failure_mode: string | null;
  failure_mode_breakdown: Record<string, number>;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface HarnessReport {
  generated_at: number;
  results: EvalResult[];
  aggregate: EvalAggregate;
}

export interface BugDetailResponse {
  result: EvalResult;
  trace: TraceEvent[];
  expected_diff: string | null;
}
