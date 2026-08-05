export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 px-6 py-4 backdrop-blur">
      <h1 className="text-lg font-semibold text-slate-50">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
    </header>
  );
}
