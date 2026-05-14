"use client";

import { PERIODS, usePeriodDays, setPeriodDays } from "@/lib/period";

export default function PeriodPicker() {
  const current = usePeriodDays();

  return (
    <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5">
      {PERIODS.map((p) => (
        <button
          key={p.days}
          onClick={() => setPeriodDays(p.days)}
          className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
            current === p.days
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
