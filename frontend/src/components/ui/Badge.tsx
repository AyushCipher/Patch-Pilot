import clsx from "clsx";
import type { ReactNode } from "react";

type BadgeTone = "teal" | "green" | "red" | "amber" | "slate";

const TONE_CLASSES: Record<BadgeTone, string> = {
  teal: "bg-teal-500/10 text-teal-400 ring-teal-500/30",
  green: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/30",
  red: "bg-rose-500/10 text-rose-400 ring-rose-500/30",
  amber: "bg-amber-500/10 text-amber-400 ring-amber-500/30",
  slate: "bg-slate-500/10 text-slate-300 ring-slate-500/30",
};

export function Badge({ tone = "slate", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONE_CLASSES[tone],
      )}
    >
      {children}
    </span>
  );
}

export function difficultyTone(difficulty: string): BadgeTone {
  if (difficulty === "easy") return "green";
  if (difficulty === "medium") return "amber";
  if (difficulty === "hard") return "red";
  return "slate";
}
