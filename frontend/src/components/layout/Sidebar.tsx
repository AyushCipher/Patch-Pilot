import { NavLink } from "react-router-dom";
import { Activity, Trophy, Bug } from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", label: "Live Run", icon: Activity },
  { to: "/leaderboard", label: "Eval Leaderboard", icon: Trophy },
];

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-950 p-4">
      <div className="mb-8 flex items-center gap-2 px-2">
        <Bug className="text-teal-400" size={22} />
        <span className="text-lg font-semibold text-slate-50">PatchPilot</span>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-teal-500/10 text-teal-400"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200",
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
