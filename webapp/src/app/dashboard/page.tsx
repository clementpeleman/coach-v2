"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchGarminActivities, fetchGarminAuthStatus, type GarminActivity } from "@/lib/api";

export default function DashboardPage() {
  const [userId] = useState<number | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }

    const rawUserId = window.localStorage.getItem("sportsHubUserId");
    const parsed = rawUserId ? Number(rawUserId) : NaN;
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  });
  const [loading, setLoading] = useState(userId !== null);
  const [error, setError] = useState<string | null>(
    userId ? null : "Geen user ID gevonden. Ga eerst naar Login.",
  );
  const [authenticated, setAuthenticated] = useState(false);
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    if (!userId) {
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const status = await fetchGarminAuthStatus(userId);
        setAuthenticated(status.authenticated);

        if (status.authenticated) {
          const data = await fetchGarminActivities(userId, 10);
          setActivities(data.activities);
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Onbekende fout");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [userId]);

  const weeklySummary = useMemo(() => {
    const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
    const recentActivities = activities.filter(
      (activity) => new Date(activity.start_time).getTime() >= sevenDaysAgo,
    );
    const totalDistanceMeters = recentActivities.reduce(
      (sum, activity) => sum + (activity.distance_meters ?? 0),
      0,
    );
    const totalDurationSeconds = recentActivities.reduce(
      (sum, activity) => sum + (activity.duration_seconds ?? 0),
      0,
    );

    return {
      sessions: recentActivities.length,
      distanceKm: (totalDistanceMeters / 1000).toFixed(1),
      durationHours: (totalDurationSeconds / 3600).toFixed(1),
    };
  }, [activities, now]);

  if (loading) {
    return <p>Laden...</p>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
        {error}
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">User ID: {userId}</p>
        <p className="mt-1 text-sm">
          Garmin status:{" "}
          <span className={authenticated ? "text-emerald-700" : "text-amber-700"}>
            {authenticated ? "Verbonden" : "Niet verbonden"}
          </span>
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Sessies (7d)" value={String(weeklySummary.sessions)} />
        <MetricCard label="Afstand (7d)" value={`${weeklySummary.distanceKm} km`} />
        <MetricCard label="Duur (7d)" value={`${weeklySummary.durationHours} h`} />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">Recente activiteiten</h2>
        {activities.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">
            Nog geen activiteiten gevonden. Verbind Garmin en sync data.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {activities.map((activity) => (
              <li key={activity.id} className="rounded-md border border-slate-200 p-3 text-sm">
                <p className="font-medium">{activity.activity_name ?? activity.activity_type}</p>
                <p className="text-slate-600">
                  {new Date(activity.start_time).toLocaleString()} ·{" "}
                  {((activity.distance_meters ?? 0) / 1000).toFixed(1)} km ·{" "}
                  {Math.round((activity.duration_seconds ?? 0) / 60)} min
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-600">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
