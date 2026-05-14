import type { ReactNode } from "react";

type Props = {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
};

export default function MetricCard({ label, value, sub, icon, trend, trendLabel }: Props) {
  const trendColor =
    trend === "up" ? "text-emerald-600" : trend === "down" ? "text-rose-600" : "text-slate-500";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {icon ? <span className="text-slate-400">{icon}</span> : null}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {(sub || trendLabel) && (
        <p className="mt-1 text-xs text-slate-500">
          {trendLabel && <span className={`font-medium ${trendColor}`}>{trendLabel} </span>}
          {sub}
        </p>
      )}
    </div>
  );
}
