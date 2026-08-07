import { describe, expect, it } from "vitest";
import { formatPct, formatSeconds, formatTier, formatUsd } from "./format";

// Regression coverage for a real crash: EvalLeaderboardPage rendered against
// a harness_report.json predating the cost/latency fields threw
// "Cannot read properties of undefined (reading 'toFixed')" because the
// original checks were `value === null`, and a missing JSON key parses to
// `undefined`, not `null`. Caught via an actual browser run, not a type
// check - TypeScript's `number | null` claim doesn't hold at the JSON
// boundary.

describe("formatUsd", () => {
  it("formats a real number", () => {
    expect(formatUsd(0.0041)).toBe("$0.0041");
  });

  it("falls back to a dash for null", () => {
    expect(formatUsd(null)).toBe("-");
  });

  it("falls back to a dash for undefined (missing JSON key) instead of throwing", () => {
    expect(formatUsd(undefined)).toBe("-");
  });
});

describe("formatSeconds", () => {
  it("formats a real number", () => {
    expect(formatSeconds(12.34)).toBe("12.3s");
  });

  it("falls back to a dash for undefined instead of throwing", () => {
    expect(formatSeconds(undefined)).toBe("-");
  });
});

describe("formatPct", () => {
  it("formats a fraction as a rounded percentage", () => {
    expect(formatPct(0.833)).toBe("83%");
  });

  it("falls back to a dash for undefined instead of throwing", () => {
    expect(formatPct(undefined)).toBe("-");
  });
});

describe("formatTier", () => {
  it("formats passed/total", () => {
    expect(formatTier({ passed: 4, total: 6, pass_rate: 0.667 })).toBe("4/6");
  });

  it("falls back to a dash when the tier has no bugs", () => {
    expect(formatTier({ passed: 0, total: 0, pass_rate: null })).toBe("-");
  });
});
