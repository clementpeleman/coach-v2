"use client";

import { useEffect, useState } from "react";
import { fetchGarminActivities, requestSmartActivityBackfill, type GarminActivity } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import MetricCard from "@/components/metric-card";
import SportBadge from "@/components/sport-badge";
import PeriodPicker from "@/components/period-picker";
import { usePeriodDays } from "@/lib/period";
import { Clock, Route, Heart, Flame, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

type TrendRow = { week_start: string; sessions: number; distance_km: number; duration_hours: number; average_heart_rate: number | null };
type Summary = { sessions: number; distance_km: number; duration_hours: number; average_heart_rate: number | null; longest_session_minutes: number; max_heart_rate: number | null };

export default function ActivitiesPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [weeklyTrend, setWeeklyTrend] = useState<TrendRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncNote, setSyncNote] = useState<string | null>(null);
  const periodDays = usePeriodDays();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    if (!session.resolved || !userId) return;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchGarminActivities(userId, 500, periodDays);
        setActivities(result.activities ?? []);
        setSummary(result.summary ?? null);
        setWeeklyTrend(result.weekly_trend ?? []);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Onbekende fout");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [session.resolved, userId, periodDays]);

  const handleSync = async () => {
    if (!userId) return;
    try {
      setSyncing(true);
      setSyncNote(null);
      const result = await requestSmartActivityBackfill(userId, periodDays > 60 ? 120 : 30);
      setSyncNote(result.message ?? "Sync gestart. Data komt binnen via webhooks.");
    } catch {
      setSyncNote("Sync mislukt. Probeer later opnieuw.");
    } finally {
      setSyncing(false);
    }
  };

  if (!session.resolved || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-emerald-600" />
      </div>
    );
  }

  if (!userId) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="text-sm text-amber-800">Log eerst in om activiteiten te zien.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Activiteiten</h1>
        <div className="flex items-center gap-2">
          <PeriodPicker />
          <button
            onClick={handleSync}
            disabled={syncing}
            className="ml-1 flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
            Sync
          </button>
        </div>
      </div>

      {syncNote && (
        <p className="rounded-lg bg-blue-50 px-4 py-2 text-xs text-blue-700">{syncNote}</p>
      )}

      {error && (
        <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">{error}</p>
      )}

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Sessies" value={String(summary.sessions)} icon={<Flame className="h-4 w-4" />} />
          <MetricCard label="Afstand" value={`${summary.distance_km.toFixed(1)} km`} icon={<Route className="h-4 w-4" />} />
          <MetricCard label="Duur" value={`${summary.duration_hours.toFixed(1)} h`} icon={<Clock className="h-4 w-4" />} />
          <MetricCard
            label="Gem. HR"
            value={summary.average_heart_rate != null ? `${summary.average_heart_rate} bpm` : "-"}
            icon={<Heart className="h-4 w-4" />}
          />
        </div>
      )}

      {weeklyTrend.length > 1 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="font-semibold">Wekelijkse trend</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-500">
                  <th className="px-5 py-2.5 font-medium">Week</th>
                  <th className="px-3 py-2.5 font-medium text-right">Sessies</th>
                  <th className="px-3 py-2.5 font-medium text-right">Afstand</th>
                  <th className="px-3 py-2.5 font-medium text-right">Duur</th>
                  <th className="px-5 py-2.5 font-medium text-right">Gem. HR</th>
                </tr>
              </thead>
              <tbody>
                {weeklyTrend.map((row) => (
                  <tr key={row.week_start} className="border-b border-slate-50">
                    <td className="px-5 py-2.5 font-medium">{row.week_start}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{row.sessions}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{row.distance_km.toFixed(1)} km</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{row.duration_hours.toFixed(1)} h</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{row.average_heart_rate ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold">Alle activiteiten ({activities.length})</h2>
        </div>
        {activities.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-slate-500">
            Geen activiteiten gevonden in deze periode.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {activities.map((a) => (
              <li key={a.id}>
                <button
                  onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
                  className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-slate-50"
                >
                  <SportBadge type={a.activity_type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {a.activity_name ?? a.activity_type}
                    </p>
                    <p className="text-xs text-slate-500">
                      {new Date(a.start_time).toLocaleDateString("nl-BE", {
                        weekday: "short",
                        day: "numeric",
                        month: "short",
                      })}
                    </p>
                  </div>
                  <div className="text-right text-xs tabular-nums text-slate-600">
                    <p>{((a.distance_meters ?? 0) / 1000).toFixed(1)} km</p>
                    <p>{Math.round((a.duration_seconds ?? 0) / 60)} min</p>
                  </div>
                  {a.average_heart_rate && (
                    <div className="hidden items-center gap-1 text-xs text-slate-500 sm:flex">
                      <Heart className="h-3 w-3" />
                      {a.average_heart_rate}
                    </div>
                  )}
                  {expandedId === a.id ? (
                    <ChevronUp className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  )}
                </button>
                {expandedId === a.id && (
                  <div className="grid gap-3 bg-slate-50 px-5 py-4 sm:grid-cols-3 lg:grid-cols-5">
                    <Detail label="Afstand" value={`${((a.distance_meters ?? 0) / 1000).toFixed(2)} km`} />
                    <Detail label="Duur" value={`${Math.round((a.duration_seconds ?? 0) / 60)} min`} />
                    <Detail label="Gem. HR" value={a.average_heart_rate ? `${a.average_heart_rate} bpm` : "-"} />
                    <Detail label="Max HR" value={a.max_heart_rate ? `${a.max_heart_rate} bpm` : "-"} />
                    <Detail label="Calorieën" value={a.calories ? `${a.calories} kcal` : "-"} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase text-slate-400">{label}</p>
      <p className="text-sm font-medium tabular-nums">{value}</p>
    </div>
  );
}
