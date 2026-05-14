"use client";

import { useEffect, useState } from "react";
import { fetchGarminActivities, fetchAthleteProfile, type AthleteProfile } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import MetricCard from "@/components/metric-card";
import {
  Heart, Route, Clock, Flame, Mountain, Footprints, Bike,
  Trophy, Calendar, Zap, TrendingUp, BarChart3,
} from "lucide-react";

type TrendRow = { week_start: string; sessions: number; distance_km: number; duration_hours: number; average_heart_rate: number | null };

export default function AnalysePage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"overzicht" | "hardlopen" | "fietsen" | "records">("overzicht");
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const [weeklyTrend, setWeeklyTrend] = useState<TrendRow[]>([]);
  const [typeDist, setTypeDist] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!session.resolved || !userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const [profileData, actData] = await Promise.all([
          fetchAthleteProfile(userId),
          fetchGarminActivities(userId, 500, 90),
        ]);
        setProfile(profileData);
        setWeeklyTrend(actData.weekly_trend ?? []);
        setTypeDist(actData.type_distribution ?? {});
      } catch { /* handled by empty state */ }
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

  if (!userId || !profile) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="text-sm text-amber-800">Log eerst in om je analyse te zien.</p>
      </div>
    );
  }

  const o = profile.overview;
  const run = profile.running;
  const cycle = profile.cycling;
  const zones = profile.heart_rate_zones;
  const prs = profile.personal_records;
  const patterns = profile.training_patterns;
  const totalSessions = Object.values(typeDist).reduce((s, v) => s + v, 0);
  const runCount = typeDist["RUNNING"] ?? 0;
  const cycleCount = typeDist["CYCLING"] ?? 0;

  const TABS = [
    { key: "overzicht" as const, label: "Overzicht" },
    { key: "hardlopen" as const, label: "Hardlopen" },
    { key: "fietsen" as const, label: "Fietsen" },
    { key: "records" as const, label: "Records" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Analyse</h1>
        <p className="text-xs text-slate-500">
          {o.total_activities} activiteiten · {patterns.total_active_weeks} weken
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overzicht" && (
        <div className="space-y-6">
          {/* Totalen */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard label="Activiteiten" value={String(o.total_activities)} icon={<Flame className="h-4 w-4" />} />
            <MetricCard label="Afstand" value={`${o.total_distance_km} km`} icon={<Route className="h-4 w-4" />} />
            <MetricCard label="Duur" value={`${o.total_duration_hours} u`} icon={<Clock className="h-4 w-4" />} />
            <MetricCard label="Calorieën" value={o.total_calories.toLocaleString()} icon={<Zap className="h-4 w-4" />} />
            <MetricCard label="Hoogtemeters" value={`${o.total_elevation_m} m`} icon={<Mountain className="h-4 w-4" />} />
          </div>

          {/* Sportverdeling */}
          {totalSessions > 0 && (
            <Section title="Sportverdeling" icon={<BarChart3 className="h-5 w-5 text-slate-500" />}>
              <div className="flex h-4 overflow-hidden rounded-full">
                {runCount > 0 && <div className="bg-blue-500" style={{ width: `${(runCount / totalSessions) * 100}%` }} />}
                {cycleCount > 0 && <div className="bg-amber-500" style={{ width: `${(cycleCount / totalSessions) * 100}%` }} />}
              </div>
              <div className="mt-2 flex gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" /> Hardlopen ({runCount})</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Fietsen ({cycleCount})</span>
              </div>
            </Section>
          )}

          {/* Hartslagzones */}
          {zones && (
            <Section title="Hartslagzones" icon={<Heart className="h-5 w-5 text-rose-500" />}>
              <p className="mb-3 text-xs text-slate-500">Op basis van max HR: {zones.max_hr_observed} bpm</p>
              <div className="space-y-2">
                {(["zone1", "zone2", "zone3", "zone4", "zone5"] as const).map((zk, i) => {
                  const z = zones[zk];
                  const colors = ["bg-blue-200", "bg-green-300", "bg-yellow-300", "bg-orange-400", "bg-rose-500"];
                  return (
                    <div key={zk} className="flex items-center gap-3">
                      <div className="w-20 text-xs font-medium text-slate-600">Z{i + 1} {z.name}</div>
                      <div className="flex-1"><div className={`h-4 rounded ${colors[i]}`} style={{ width: `${20 + i * 15}%` }} /></div>
                      <div className="w-28 text-right text-xs tabular-nums text-slate-500">{z.range}</div>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {/* Volume per week */}
          {weeklyTrend.length > 1 && (
            <Section title="Volume per week" icon={<TrendingUp className="h-5 w-5 text-emerald-600" />}>
              <div className="flex items-end gap-1" style={{ height: 100 }}>
                {weeklyTrend.map((row) => {
                  const maxD = Math.max(...weeklyTrend.map((r) => r.duration_hours), 1);
                  const h = (row.duration_hours / maxD) * 100;
                  return (
                    <div key={row.week_start} className="group relative flex-1" title={`${row.week_start}: ${row.duration_hours.toFixed(1)}u`}>
                      <div className="mx-auto w-full max-w-6 rounded-t bg-emerald-500 group-hover:bg-emerald-600" style={{ height: `${Math.max(h, 3)}%` }} />
                      <p className="mt-1 text-center text-[8px] text-slate-400">{row.week_start.slice(5)}</p>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {/* Trainingspatronen */}
          {patterns && (
            <Section title="Trainingspatronen" icon={<Calendar className="h-5 w-5 text-slate-500" />}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Sessies/week" value={String(patterns.sessions_per_week)} />
                <Stat label="Gem. rustdagen" value={patterns.avg_days_between_sessions ? String(patterns.avg_days_between_sessions) : "—"} />
                <Stat label="Max rustdagen" value={patterns.max_days_between_sessions ? String(patterns.max_days_between_sessions) : "—"} />
                <Stat label="Actieve weken" value={String(patterns.total_active_weeks)} />
              </div>
              {patterns.favorite_days.length > 0 && (
                <div className="mt-3">
                  <p className="mb-1.5 text-[10px] font-medium uppercase text-slate-400">Favoriete dagen</p>
                  <div className="flex flex-wrap gap-1.5">
                    {patterns.favorite_days.map((d) => (
                      <span key={d.day} className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">{d.day} ({d.count}x)</span>
                    ))}
                  </div>
                </div>
              )}
            </Section>
          )}
        </div>
      )}

      {tab === "hardlopen" && run && (
        <Section title="Hardlopen" icon={<Footprints className="h-5 w-5 text-blue-600" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Sessies" value={String(run.total_sessions)} />
            <Stat label="Totale afstand" value={`${run.total_distance_km} km`} />
            <Stat label="Gem. afstand" value={run.avg_distance_km ? `${run.avg_distance_km} km` : "—"} />
            <Stat label="Gem. duur" value={run.avg_duration_min ? `${run.avg_duration_min} min` : "—"} />
            <Stat label="Gem. tempo" value={run.avg_pace_min_km ? `${run.avg_pace_min_km} min/km` : "—"} />
            <Stat label="Beste tempo" value={run.best_pace_min_km ? `${run.best_pace_min_km} min/km` : "—"} />
            <Stat label="Gem. hartslag" value={run.avg_heart_rate ? `${run.avg_heart_rate} bpm` : "—"} />
            <Stat label="Max hartslag" value={run.max_heart_rate_observed ? `${run.max_heart_rate_observed} bpm` : "—"} />
            <Stat label="Gem. cadans" value={run.avg_cadence_spm ? `${run.avg_cadence_spm} spm` : "—"} />
            <Stat label="Langste run" value={run.longest_run_km ? `${run.longest_run_km} km` : "—"} />
            <Stat label="Cal/sessie" value={run.avg_calories_per_session ? `${run.avg_calories_per_session}` : "—"} />
            <Stat label="Hoogtemeters" value={`${run.total_elevation_m} m`} />
          </div>
        </Section>
      )}
      {tab === "hardlopen" && !run && <EmptyTab sport="hardlopen" />}

      {tab === "fietsen" && cycle && (
        <Section title="Fietsen" icon={<Bike className="h-5 w-5 text-amber-600" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Sessies" value={String(cycle.total_sessions)} />
            <Stat label="Totale afstand" value={`${cycle.total_distance_km} km`} />
            <Stat label="Gem. afstand" value={cycle.avg_distance_km ? `${cycle.avg_distance_km} km` : "—"} />
            <Stat label="Gem. duur" value={cycle.avg_duration_min ? `${cycle.avg_duration_min} min` : "—"} />
            <Stat label="Gem. snelheid" value={cycle.avg_speed_kmh ? `${cycle.avg_speed_kmh} km/u` : "—"} />
            <Stat label="Max snelheid" value={cycle.max_speed_kmh ? `${cycle.max_speed_kmh} km/u` : "—"} />
            <Stat label="Gem. hartslag" value={cycle.avg_heart_rate ? `${cycle.avg_heart_rate} bpm` : "—"} />
            <Stat label="Max hartslag" value={cycle.max_heart_rate_observed ? `${cycle.max_heart_rate_observed} bpm` : "—"} />
            <Stat label="Gem. hoogtemeters" value={cycle.avg_elevation_m ? `${cycle.avg_elevation_m} m` : "—"} />
            <Stat label="Langste rit" value={cycle.longest_ride_km ? `${cycle.longest_ride_km} km` : "—"} />
            <Stat label="Cal/sessie" value={cycle.avg_calories_per_session ? `${cycle.avg_calories_per_session}` : "—"} />
            <Stat label="Hoogtemeters" value={`${cycle.total_elevation_m} m`} />
          </div>
        </Section>
      )}
      {tab === "fietsen" && !cycle && <EmptyTab sport="fietsen" />}

      {tab === "records" && (
        <div className="space-y-4">
          {prs.running && (
            <Section title="Hardlopen" icon={<Trophy className="h-5 w-5 text-yellow-500" />}>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(prs.running).map(([key, pr]) => (
                  <PRCard key={key} label={key.replace(/_/g, " ")} value={`${pr.value} ${pr.unit}`} date={pr.date} activity={pr.activity} />
                ))}
              </div>
            </Section>
          )}
          {prs.cycling && (
            <Section title="Fietsen" icon={<Trophy className="h-5 w-5 text-yellow-500" />}>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(prs.cycling).map(([key, pr]) => (
                  <PRCard key={key} label={key.replace(/_/g, " ")} value={`${pr.value} ${pr.unit}`} date={pr.date} activity={pr.activity} />
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center gap-2">
        {icon}
        <h2 className="font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-[10px] font-medium uppercase text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function PRCard({ label, value, date, activity }: { label: string; value: string; date: string | null; activity: string | null }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium capitalize text-slate-500">{label}</p>
        <p className="text-sm font-bold tabular-nums">{value}</p>
      </div>
      {(date || activity) && (
        <p className="mt-1 text-[10px] text-slate-400">
          {activity}{date ? ` · ${new Date(date).toLocaleDateString("nl-BE", { day: "numeric", month: "short" })}` : ""}
        </p>
      )}
    </div>
  );
}

function EmptyTab({ sport }: { sport: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-10 text-center">
      <p className="text-sm text-slate-500">Nog geen {sport} data beschikbaar.</p>
    </div>
  );
}
