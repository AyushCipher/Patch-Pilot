// Loose (== null) checks throughout: a report generated before a field
// existed, or any other payload missing a key, yields `undefined` here, not
// `null` - the JSON on the wire is never as guaranteed as the TS type
// claims, and a strict `=== null` check let a real crash through once
// (see EvalLeaderboardPage rendering against an older harness_report.json).

export function formatPct(value: number | null | undefined): string {
  return value == null ? "-" : `${Math.round(value * 100)}%`;
}

export function formatUsd(value: number | null | undefined): string {
  return value == null ? "-" : `$${value.toFixed(4)}`;
}

export function formatSeconds(value: number | null | undefined): string {
  return value == null ? "-" : `${value.toFixed(1)}s`;
}

export function formatTier(stats: { passed: number; total: number; pass_rate: number | null }): string {
  if (stats.total === 0) return "-";
  return `${stats.passed}/${stats.total}`;
}
