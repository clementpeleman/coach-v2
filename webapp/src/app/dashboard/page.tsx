"use client";

import { useEffect, useState } from "react";
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
import { Heart, Clock, Route, Flame, TrendingUp, TrendingDown } from "lucide-react";

export default function DashboardPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [weeklyAnalysis, setWeeklyAnalysis] = useState<WeeklyAnalysis | null>(null);

  useEffect(() => {
    if (session.resolved && userId) {
      window.localStorage.setItem("sportsHubUserId", String(userId));
    }
  }, [session.resolved, userId]);

  useEffect(() => {
    if (!session.resolved || !userId) return;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const status = await fetchGarminAuthStatus(userId);
        setAuthenticated(status.authenticated);

        if (status.authenticated) {
          const [data, analysis] = await Promise.all([
            fetchGarminActivities(userId, 10),
            fetchWeeklyAnalysis(userId),
          ]);
          setActivities(data.activities);
          setWeeklyAnalysis(analysis);
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Onbekende fout");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [session.resolved, userId]);

  const week = weeklyAnalysis?.current_week;
  const deltas = weeklyAnalysis?.deltas;

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
        <p className="text-sm text-amber-800">Geen sessie gevonden. Ga naar Login om te starten.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-500">
            Garmin:{" "}
            <span className={authenticated ? "text-emerald-600" : "text-amber-600"}>
              {authenticated ? "Verbonden" : "Niet verbonden"}
            </span>
          </p>
        </div>
      </div>

      {week && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Sessies"
              value={String(week.sessions)}
              icon={<Flame className="h-4 w-4" />}
              trend={
                deltas?.sessions_percent != null
                  ? deltas.sessions_percent > 0
                    ? "up"
                    : deltas.sessions_percent < 0
                      ? "down"
                      : "neutral"
                  : undefined
              }
              trendLabel={
                deltas?.sessions_percent != null ? `${deltas.sessions_percent > 0 ? "+" : ""}${deltas.sessions_percent}%` : undefined
              }
              sub="vs baseline/week"
            />
            <MetricCard
              label="Afstand"
              value={`${week.distance_km.toFixed(1)} km`}
              icon={<Route className="h-4 w-4" />}
              trend={
                deltas?.distance_percent != null
                  ? deltas.distance_percent > 0
                    ? "up"
                    : deltas.distance_percent < 0
                      ? "down"
                      : "neutral"
                  : undefined
              }
              trendLabel={
                deltas?.distance_percent != null ? `${deltas.distance_percent > 0 ? "+" : ""}${deltas.distance_percent}%` : undefined
              }
              sub="vs baseline/week"
            />
            <MetricCard
              label="Duur"
              value={`${week.duration_hours.toFixed(1)} h`}
              icon={<Clock className="h-4 w-4" />}
              trend={
                deltas?.duration_percent != null
                  ? deltas.duration_percent > 0
                    ? "up"
                    : deltas.duration_percent < 0
                      ? "down"
                      : "neutral"
                  : undefined
              }
              trendLabel={
                deltas?.duration_percent != null ? `${deltas.duration_percent > 0 ? "+" : ""}${deltas.duration_percent}%` : undefined
              }
              sub="vs baseline/week"
            />
            <MetricCard
              label="Gem. HR"
              value={week.average_heart_rate != null ? `${week.average_heart_rate} bpm` : "—"}
              icon={<Heart className="h-4 w-4" />}
              trend={
                deltas?.avg_heart_rate_delta != null
                  ? deltas.avg_heart_rate_delta > 2
                    ? "up"
                    : deltas.avg_heart_rate_delta < -2
                      ? "down"
                      : "neutral"
                  : undefined
              }
              trendLabel={
                deltas?.avg_heart_rate_delta != null
                  ? `${deltas.avg_heart_rate_delta > 0 ? "+" : ""}${deltas.avg_heart_rate_delta} bpm`
                  : undefined
              }
              sub="vs baseline"
            />
          </div>

          {weeklyAnalysis?.summary && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-lg bg-emerald-100 p-1.5">
                  {weeklyAnalysis.load_ratio != null && weeklyAnalysis.load_ratio > 1.1 ? (
                    <TrendingUp className="h-4 w-4 text-emerald-700" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-emerald-700" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-semibold text-emerald-900">Wekelijkse samenvatting</p>
                  <p className="mt-1 text-sm leading-relaxed text-emerald-800">
                    {weeklyAnalysis.summary}
                  </p>
                  {weeklyAnalysis.load_ratio != null && (
                    <p className="mt-2 text-xs text-emerald-600">
                      Load ratio: {weeklyAnalysis.load_ratio}x
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold">Recente activiteiten</h2>
        </div>
        {activities.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-slate-500">
            Nog geen activiteiten. Verbind Garmin en sync je data.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {activities.map((a) => (
              <li key={a.id} className="flex items-center gap-4 px-5 py-3">
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
                <div className="text-right text-xs text-slate-600">
                  <p>{((a.distance_meters ?? 0) / 1000).toFixed(1)} km</p>
                  <p>{Math.round((a.duration_seconds ?? 0) / 60)} min</p>
                </div>
                {a.average_heart_rate && (
                  <div className="hidden items-center gap-1 text-xs text-slate-500 sm:flex">
                    <Heart className="h-3 w-3" />
                    {a.average_heart_rate}
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
