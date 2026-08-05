import clsx from "clsx";

function lineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) {
    return "text-slate-400";
  }
  if (line.startsWith("@@")) {
    return "text-teal-400";
  }
  if (line.startsWith("+")) {
    return "text-emerald-400 bg-emerald-500/10";
  }
  if (line.startsWith("-")) {
    return "text-rose-400 bg-rose-500/10";
  }
  return "text-slate-300";
}

export function DiffViewer({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs leading-relaxed">
      <code>
        {lines.map((line, i) => (
          <div key={i} className={clsx("whitespace-pre px-1", lineClass(line))}>
            {line || " "}
          </div>
        ))}
      </code>
    </pre>
  );
}
