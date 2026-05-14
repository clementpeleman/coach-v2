"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchGarminActivities,
  fetchGarminAuthStatus,
  fetchWeeklyAnalysis,
  type GarminActivity,
  type WeeklyAnalysis,
} from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import MetricCard from "@/components/metric-card";
import SportBadge from "@/components/sport-badge";
import {
  Heart, Clock, Route, Flame, ArrowRight, Zap,
  AlertTriangle, CheckCircle2, Info,
} from "lucide-react";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "14d", days: 14 },
  { label: "30d", days: 30 },
] as const;

export default function DashboardPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [loading, setLoading] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [weeklyAnalysis, setWeeklyAnalysis] = useState<WeeklyAnalysis | null>(null);
  const [periodDays, setPeriodDays] = useState(7);

  useEffect(() => {
    if (session.resolved && userId) {
      window.localStorage.setItem("sportsHubUserId", String(userId));
    }
  }, [session.resolved, userId]);

  useEffect(() => {
    if (!session.resolved || !userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const status = await fetchGarminAuthStatus(userId);
        setAuthenticated(status.authenticated);
        if (status.authenticated) {
          const [data, analysis] = await Promise.all([
            fetchGarminActivities(userId, 5, periodDays),
            fetchWeeklyAnalysis(userId, periodDays),
          ]);
          setActivities(data.activities);
          setWeeklyAnalysis(analysis);
        }
      } catch { /* empty state handles this */ }
      setLoading(false);
    };
    void load();
  }, [session.resolved, userId, periodDays]);

  if (!session.resolved || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-emerald-600" />
      </div>
    );
  }

  if (!userId) {
    return (
      <div className="mx-auto max-w-sm py-20 text-center">
        <Zap className="mx-auto mb-4 h-10 w-10 text-emerald-600" />
        <h1 className="text-xl font-bold">Welkom bij Sports Hub</h1>
        <p className="mt-2 text-sm text-slate-500">Verbind je Garmin om te starten.</p>
        <Link href="/login" className="mt-6 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white">
          Verbind Garmin
        </Link>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="mx-auto max-w-sm py-20 text-center">
        <h1 className="text-xl font-bold">Garmin niet verbonden</h1>
        <p className="mt-2 text-sm text-slate-500">Verbind opnieuw om je data te zien.</p>
        <Link href="/login" className="mt-6 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white">
          Verbind Garmin
        </Link>
      </div>
    );
  }

  const week = weeklyAnalysis?.current_week;
  const deltas = weeklyAnalysis?.deltas;
  const highlights = weeklyAnalysis?.highlights ?? [];
  const lastActivity = activities[0] ?? null;

  return (
    <div className="space-y-6">
      {/* Header met periode selector */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setPeriodDays(p.days)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                periodDays === p.days
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Visuele highlights */}
      {highlights.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {highlights.map((h, i) => (
            <HighlightChip key={i} type={h.type} label={h.label} text={h.text} />
          ))}
        </div>
      )}

      {/* Metrics */}
      {week && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Sessies"
            value={String(week.sessions)}
            icon={<Flame className="h-4 w-4" />}
            trend={deltas?.sessions_percent != null ? (deltas.sessions_percent > 0 ? "up" : deltas.sessions_percent < 0 ? "down" : "neutral") : undefined}
            trendLabel={deltas?.sessions_percent != null ? `${deltas.sessions_percent > 0 ? "+" : ""}${deltas.sessions_percent}%` : undefined}
          />
          <MetricCard
            label="Afstand"
            value={`${week.distance_km.toFixed(1)} km`}
            icon={<Route className="h-4 w-4" />}
            trend={deltas?.distance_percent != null ? (deltas.distance_percent > 0 ? "up" : deltas.distance_percent < 0 ? "down" : "neutral") : undefined}
            trendLabel={deltas?.distance_percent != null ? `${deltas.distance_percent > 0 ? "+" : ""}${deltas.distance_percent}%` : undefined}
          />
          <MetricCard
            label="Duur"
            value={`${week.duration_hours.toFixed(1)} u`}
            icon={<Clock className="h-4 w-4" />}
            trend={deltas?.duration_percent != null ? (deltas.duration_percent > 0 ? "up" : deltas.duration_percent < 0 ? "down" : "neutral") : undefined}
            trendLabel={deltas?.duration_percent != null ? `${deltas.duration_percent > 0 ? "+" : ""}${deltas.duration_percent}%` : undefined}
          />
          <MetricCard
            label="Gem. hartslag"
            value={week.average_heart_rate != null ? `${week.average_heart_rate} bpm` : "—"}
            icon={<Heart className="h-4 w-4" />}
            trend={deltas?.avg_heart_rate_delta != null ? (deltas.avg_heart_rate_delta > 2 ? "up" : deltas.avg_heart_rate_delta < -2 ? "down" : "neutral") : undefined}
            trendLabel={deltas?.avg_heart_rate_delta != null ? `${deltas.avg_heart_rate_delta > 0 ? "+" : ""}${deltas.avg_heart_rate_delta} bpm` : undefined}
          />
        </div>
      )}

      {/* Laatste activiteit */}
      {lastActivity && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Laatste activiteit</h2>
            <Link href="/activiteiten" className="flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700">
              Alles bekijken <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="mt-4 flex items-center gap-4">
            <SportBadge type={lastActivity.activity_type} />
            <div className="flex-1">
              <p className="font-medium">{lastActivity.activity_name ?? lastActivity.activity_type}</p>
              <p className="text-xs text-slate-500">
                {new Date(lastActivity.start_time).toLocaleDateString("nl-BE", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                })}
              </p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MiniStat label="Afstand" value={`${((lastActivity.distance_meters ?? 0) / 1000).toFixed(1)} km`} />
            <MiniStat label="Duur" value={`${Math.round((lastActivity.duration_seconds ?? 0) / 60)} min`} />
            <MiniStat label="Gem. HR" value={lastActivity.average_heart_rate ? `${lastActivity.average_heart_rate} bpm` : "—"} />
            <MiniStat label="Calorieën" value={lastActivity.calories ? `${lastActivity.calories} kcal` : "—"} />
          </div>
        </div>
      )}

      {/* Recente activiteiten */}
      {activities.length > 1 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-5 py-3">
            <h2 className="text-sm font-semibold">Recente activiteiten</h2>
          </div>
          <ul className="divide-y divide-slate-100">
            {activities.slice(1).map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-5 py-2.5">
                <SportBadge type={a.activity_type} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{a.activity_name ?? a.activity_type}</p>
                  <p className="text-xs text-slate-500">
                    {new Date(a.start_time).toLocaleDateString("nl-BE", { weekday: "short", day: "numeric", month: "short" })}
                  </p>
                </div>
                <div className="text-right text-xs tabular-nums text-slate-600">
                  <p>{((a.distance_meters ?? 0) / 1000).toFixed(1)} km</p>
                  <p>{Math.round((a.duration_seconds ?? 0) / 60)} min</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function HighlightChip({ type, label, text }: { type: string; label: string; text: string }) {
  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    info: "border-blue-200 bg-blue-50 text-blue-800",
  }[type] ?? "border-slate-200 bg-slate-50 text-slate-800";

  const Icon = type === "warning" ? AlertTriangle : type === "success" ? CheckCircle2 : Info;

  return (
    <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${styles}`}>
      <Icon className="h-3.5 w-3.5" />
      <span className="text-xs font-semibold">{label}</span>
      <span className="text-xs opacity-75">{text}</span>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-medium uppercase text-slate-400">{label}</p>
      <p className="text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}
