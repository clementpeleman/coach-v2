"use client";

import { useEffect, useState } from "react";
import { fetchGarminActivities, type GarminActivity } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import MetricCard from "@/components/metric-card";
import { TrendingUp, Heart, Bike, Footprints } from "lucide-react";

type TrendRow = { week_start: string; sessions: number; distance_km: number; duration_hours: number; average_heart_rate: number | null };
type TypeDist = { [key: string]: number };

export default function TrendsPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [loading, setLoading] = useState(false);
  const [weeklyTrend, setWeeklyTrend] = useState<TrendRow[]>([]);
  const [typeDist, setTypeDist] = useState<TypeDist>({});
  const [activities, setActivities] = useState<GarminActivity[]>([]);

  useEffect(() => {
    if (!session.resolved || !userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const result = await fetchGarminActivities(userId, 500, 90);
        setActivities(result.activities ?? []);
        setWeeklyTrend(result.weekly_trend ?? []);
        setTypeDist(result.type_distribution ?? {});
      } catch { /* ignore */ }
      setLoading(false);
    };
    void load();
  }, [session.resolved, userId]);

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
        <p className="text-sm text-amber-800">Log eerst in om trends te zien.</p>
      </div>
    );
  }

  const totalSessions = Object.values(typeDist).reduce((s, v) => s + v, 0);
  const runCount = typeDist["RUNNING"] ?? 0;
  const cycleCount = typeDist["CYCLING"] ?? 0;

  const runActivities = activities.filter((a) => a.activity_type?.toUpperCase().includes("RUN"));
  const cycleActivities = activities.filter((a) => a.activity_type?.toUpperCase().includes("CYCL"));

  const avgRunHR = runActivities.length > 0
    ? Math.round(runActivities.reduce((s, a) => s + (a.average_heart_rate ?? 0), 0) / runActivities.filter((a) => a.average_heart_rate).length)
    : null;
  const avgCycleHR = cycleActivities.length > 0
    ? Math.round(cycleActivities.reduce((s, a) => s + (a.average_heart_rate ?? 0), 0) / cycleActivities.filter((a) => a.average_heart_rate).length)
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trends</h1>
        <p className="text-sm text-slate-500">Laatste 3 maanden</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Totaal sessies" value={String(totalSessions)} icon={<TrendingUp className="h-4 w-4" />} />
        <MetricCard
          label="Sportverdeling"
          value={`${runCount}R / ${cycleCount}C`}
          icon={
            <div className="flex gap-1">
              <Footprints className="h-3.5 w-3.5 text-blue-500" />
              <Bike className="h-3.5 w-3.5 text-amber-500" />
            </div>
          }
          sub={totalSessions > 0 ? `${Math.round((runCount / totalSessions) * 100)}% run` : undefined}
        />
        <MetricCard
          label="Gem. HR Run"
          value={avgRunHR != null ? `${avgRunHR} bpm` : "—"}
          icon={<Heart className="h-4 w-4 text-blue-500" />}
        />
        <MetricCard
          label="Gem. HR Fietsen"
          value={avgCycleHR != null ? `${avgCycleHR} bpm` : "—"}
          icon={<Heart className="h-4 w-4 text-amber-500" />}
        />
      </div>

      {totalSessions > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 font-semibold">Sportverdeling</h2>
          <div className="flex h-4 overflow-hidden rounded-full">
            {runCount > 0 && (
              <div
                className="bg-blue-500"
                style={{ width: `${(runCount / totalSessions) * 100}%` }}
                title={`Run: ${runCount}`}
              />
            )}
            {cycleCount > 0 && (
              <div
                className="bg-amber-500"
                style={{ width: `${(cycleCount / totalSessions) * 100}%` }}
                title={`Cycle: ${cycleCount}`}
              />
            )}
            {totalSessions - runCount - cycleCount > 0 && (
              <div
                className="bg-slate-300"
                style={{ width: `${((totalSessions - runCount - cycleCount) / totalSessions) * 100}%` }}
                title="Overig"
              />
            )}
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" /> Run ({runCount})</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Fietsen ({cycleCount})</span>
            {totalSessions - runCount - cycleCount > 0 && (
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-slate-300" /> Overig ({totalSessions - runCount - cycleCount})</span>
            )}
          </div>
        </div>
      )}

      {weeklyTrend.length > 1 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="font-semibold">Volume per week</h2>
          </div>

          <div className="px-5 py-4">
            <div className="flex items-end gap-1" style={{ height: 120 }}>
              {weeklyTrend.map((row) => {
                const maxDuration = Math.max(...weeklyTrend.map((r) => r.duration_hours), 1);
                const height = (row.duration_hours / maxDuration) * 100;
                return (
                  <div key={row.week_start} className="group relative flex-1" title={`${row.week_start}: ${row.duration_hours.toFixed(1)}h`}>
                    <div
                      className="mx-auto w-full max-w-8 rounded-t bg-emerald-500 transition-colors group-hover:bg-emerald-600"
                      style={{ height: `${Math.max(height, 2)}%` }}
                    />
                    <p className="mt-1 text-center text-[9px] text-slate-400">{row.week_start.slice(5)}</p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="overflow-x-auto border-t border-slate-100">
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
                    <td className="px-5 py-2.5 text-right tabular-nums">{row.average_heart_rate ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
