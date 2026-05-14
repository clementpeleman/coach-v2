"use client";

import { useEffect, useState } from "react";
import { fetchAthleteProfile, type AthleteProfile } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import MetricCard from "@/components/metric-card";
import {
  Heart, Route, Clock, Flame, Mountain, Footprints, Bike,
  Trophy, Calendar, Zap,
} from "lucide-react";

export default function ProfilePage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session.resolved || !userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchAthleteProfile(userId);
        setProfile(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Profiel laden mislukt");
      }
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

  if (!userId || error) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="text-sm text-amber-800">{error ?? "Log eerst in."}</p>
      </div>
    );
  }

  if (!profile) return null;

  const o = profile.overview;
  const run = profile.running;
  const cycle = profile.cycling;
  const zones = profile.heart_rate_zones;
  const prs = profile.personal_records;
  const patterns = profile.training_patterns;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Atleetprofiel</h1>
        <p className="text-sm text-slate-500">
          Gebaseerd op {o.total_activities} activiteiten
          {patterns.total_active_weeks > 0 ? ` over ${patterns.total_active_weeks} weken` : ""}
        </p>
      </div>

      {/* Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Activiteiten" value={String(o.total_activities)} icon={<Flame className="h-4 w-4" />} />
        <MetricCard label="Totale afstand" value={`${o.total_distance_km} km`} icon={<Route className="h-4 w-4" />} />
        <MetricCard label="Totale duur" value={`${o.total_duration_hours} h`} icon={<Clock className="h-4 w-4" />} />
        <MetricCard label="Calorieën" value={`${o.total_calories.toLocaleString()}`} icon={<Zap className="h-4 w-4" />} />
        <MetricCard label="Hoogtemeters" value={`${o.total_elevation_m} m`} icon={<Mountain className="h-4 w-4" />} />
      </div>

      {/* Heart rate zones */}
      {zones && (
        <Section title="Hartslagzones" icon={<Heart className="h-5 w-5 text-rose-500" />}>
          <p className="mb-3 text-xs text-slate-500">Gebaseerd op max HR: {zones.max_hr_observed} bpm</p>
          <div className="space-y-2">
            {(["zone1", "zone2", "zone3", "zone4", "zone5"] as const).map((zk, i) => {
              const z = zones[zk];
              const colors = ["bg-blue-200", "bg-green-300", "bg-yellow-300", "bg-orange-400", "bg-rose-500"];
              const width = 20 + i * 5;
              return (
                <div key={zk} className="flex items-center gap-3">
                  <div className="w-24 text-xs font-medium text-slate-600">Z{i + 1} {z.name}</div>
                  <div className="flex-1">
                    <div className={`h-5 rounded ${colors[i]}`} style={{ width: `${width}%` }} />
                  </div>
                  <div className="w-32 text-right text-xs tabular-nums text-slate-500">{z.range}</div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Running profile */}
      {run && (
        <Section title="Hardlopen" icon={<Footprints className="h-5 w-5 text-blue-600" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Sessies" value={String(run.total_sessions)} />
            <Stat label="Totale afstand" value={`${run.total_distance_km} km`} />
            <Stat label="Gem. afstand" value={run.avg_distance_km ? `${run.avg_distance_km} km` : "—"} />
            <Stat label="Gem. duur" value={run.avg_duration_min ? `${run.avg_duration_min} min` : "—"} />
            <Stat label="Gem. tempo" value={run.avg_pace_min_km ? `${run.avg_pace_min_km} min/km` : "—"} />
            <Stat label="Beste tempo" value={run.best_pace_min_km ? `${run.best_pace_min_km} min/km` : "—"} />
            <Stat label="Gem. HR" value={run.avg_heart_rate ? `${run.avg_heart_rate} bpm` : "—"} />
            <Stat label="Max HR" value={run.max_heart_rate_observed ? `${run.max_heart_rate_observed} bpm` : "—"} />
            <Stat label="Gem. cadans" value={run.avg_cadence_spm ? `${run.avg_cadence_spm} spm` : "—"} />
            <Stat label="Langste run" value={run.longest_run_km ? `${run.longest_run_km} km` : "—"} />
            <Stat label="Cal/sessie" value={run.avg_calories_per_session ? `${run.avg_calories_per_session}` : "—"} />
            <Stat label="Hoogtemeters" value={`${run.total_elevation_m} m`} />
          </div>
        </Section>
      )}

      {/* Cycling profile */}
      {cycle && (
        <Section title="Fietsen" icon={<Bike className="h-5 w-5 text-amber-600" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Sessies" value={String(cycle.total_sessions)} />
            <Stat label="Totale afstand" value={`${cycle.total_distance_km} km`} />
            <Stat label="Gem. afstand" value={cycle.avg_distance_km ? `${cycle.avg_distance_km} km` : "—"} />
            <Stat label="Gem. duur" value={cycle.avg_duration_min ? `${cycle.avg_duration_min} min` : "—"} />
            <Stat label="Gem. snelheid" value={cycle.avg_speed_kmh ? `${cycle.avg_speed_kmh} km/h` : "—"} />
            <Stat label="Max snelheid" value={cycle.max_speed_kmh ? `${cycle.max_speed_kmh} km/h` : "—"} />
            <Stat label="Gem. HR" value={cycle.avg_heart_rate ? `${cycle.avg_heart_rate} bpm` : "—"} />
            <Stat label="Max HR" value={cycle.max_heart_rate_observed ? `${cycle.max_heart_rate_observed} bpm` : "—"} />
            <Stat label="Gem. hoogtemeters" value={cycle.avg_elevation_m ? `${cycle.avg_elevation_m} m` : "—"} />
            <Stat label="Langste rit" value={cycle.longest_ride_km ? `${cycle.longest_ride_km} km` : "—"} />
            <Stat label="Cal/sessie" value={cycle.avg_calories_per_session ? `${cycle.avg_calories_per_session}` : "—"} />
            <Stat label="Hoogtemeters" value={`${cycle.total_elevation_m} m`} />
          </div>
        </Section>
      )}

      {/* Personal records */}
      {(prs.running || prs.cycling) && (
        <Section title="Persoonlijke records" icon={<Trophy className="h-5 w-5 text-yellow-500" />}>
          <div className="grid gap-4 sm:grid-cols-2">
            {prs.running && (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-blue-700">
                  <Footprints className="h-4 w-4" /> Hardlopen
                </p>
                <div className="space-y-2">
                  {Object.entries(prs.running).map(([key, pr]) => (
                    <PRCard key={key} label={key.replace(/_/g, " ")} value={`${pr.value} ${pr.unit}`} date={pr.date} activity={pr.activity} />
                  ))}
                </div>
              </div>
            )}
            {prs.cycling && (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-700">
                  <Bike className="h-4 w-4" /> Fietsen
                </p>
                <div className="space-y-2">
                  {Object.entries(prs.cycling).map(([key, pr]) => (
                    <PRCard key={key} label={key.replace(/_/g, " ")} value={`${pr.value} ${pr.unit}`} date={pr.date} activity={pr.activity} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Training patterns */}
      {patterns && (
        <Section title="Trainingspatronen" icon={<Calendar className="h-5 w-5 text-slate-500" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Sessies/week" value={String(patterns.sessions_per_week)} />
            <Stat label="Gem. dagen tussen sessies" value={patterns.avg_days_between_sessions ? String(patterns.avg_days_between_sessions) : "—"} />
            <Stat label="Max rustdagen" value={patterns.max_days_between_sessions ? String(patterns.max_days_between_sessions) : "—"} />
            <Stat label="Actieve weken" value={String(patterns.total_active_weeks)} />
          </div>
          {patterns.favorite_days.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-medium uppercase text-slate-400">Favoriete trainingsdagen</p>
              <div className="flex gap-2">
                {patterns.favorite_days.map((d) => (
                  <span key={d.day} className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                    {d.day} ({d.count}x)
                  </span>
                ))}
              </div>
            </div>
          )}
          {patterns.favorite_hours.length > 0 && (
            <div className="mt-3">
              <p className="mb-2 text-xs font-medium uppercase text-slate-400">Favoriete tijdstippen</p>
              <div className="flex gap-2">
                {patterns.favorite_hours.map((h) => (
                  <span key={h.hour} className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                    {String(h.hour).padStart(2, "0")}:00 ({h.count}x)
                  </span>
                ))}
              </div>
            </div>
          )}
        </Section>
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
      <p className="text-[11px] font-medium uppercase text-slate-400">{label}</p>
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
