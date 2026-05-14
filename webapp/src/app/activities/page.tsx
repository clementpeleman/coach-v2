"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fetchGarminActivities,
  type ActivitiesResponse,
  type GarminActivity,
} from "@/lib/api";
import { useSessionUserId } from "@/lib/session";

export default function ActivitiesPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [periodDays, setPeriodDays] = useState(30);
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [activityData, setActivityData] = useState<ActivitiesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session.resolved || !userId) {
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchGarminActivities(userId, 500, periodDays);
        setActivityData(result);
        setActivities(result.activities);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Onbekende fout");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [session.resolved, userId, periodDays]);

  const trendInsight = useMemo(() => {
    if (!activityData || activityData.weekly_trend.length < 2) {
      return "Nog te weinig wekelijkse datapunten voor trendinschatting.";
    }

    const trend = activityData.weekly_trend;
    const split = Math.ceil(trend.length / 2);
    const firstHalf = trend.slice(0, split);
    const secondHalf = trend.slice(split);

    const avg = (values: number[]) =>
      values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

    const durationFirst = avg(firstHalf.map((week) => week.duration_hours));
    const durationSecond = avg(secondHalf.map((week) => week.duration_hours));
    const distanceFirst = avg(firstHalf.map((week) => week.distance_km));
    const distanceSecond = avg(secondHalf.map((week) => week.distance_km));
    const hrFirst = avg(firstHalf.map((week) => week.average_heart_rate ?? 0).filter(Boolean));
    const hrSecond = avg(secondHalf.map((week) => week.average_heart_rate ?? 0).filter(Boolean));

    const durationDelta = durationFirst ? ((durationSecond - durationFirst) / durationFirst) * 100 : 0;
    const distanceDelta = distanceFirst ? ((distanceSecond - distanceFirst) / distanceFirst) * 100 : 0;
    const hrDelta = hrFirst && hrSecond ? hrSecond - hrFirst : 0;

    return `Volume trend: ${durationDelta >= 0 ? "+" : ""}${durationDelta.toFixed(1)}% duur/week, ${
      distanceDelta >= 0 ? "+" : ""
    }${distanceDelta.toFixed(1)}% afstand/week. HR trend: ${
      hrFirst && hrSecond ? `${hrDelta >= 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm` : "n.v.t."
    }.`;
  }, [activityData]);

  if (!session.resolved || loading) {
    return <p>Laden...</p>;
  }

  if (!userId) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
        Geen user ID gevonden. Log eerst in op de login pagina.
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold">Activities</h1>
        <p className="mt-2 text-sm text-slate-600">
          User ID: {userId} · focus op trends over de gekozen periode.
        </p>
        <div className="mt-4 flex gap-2">
          {[30, 90].map((days) => (
            <button
              key={days}
              onClick={() => setPeriodDays(days)}
              className={`rounded-md px-3 py-1.5 text-sm ${
                periodDays === days
                  ? "bg-slate-900 text-white"
                  : "border border-slate-300 bg-white text-slate-700"
              }`}
            >
              {days === 30 ? "1 maand" : "3 maanden"}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      {activityData ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="Sessies" value={String(activityData.summary.sessions)} />
            <MetricCard label="Afstand" value={`${activityData.summary.distance_km} km`} />
            <MetricCard label="Duur" value={`${activityData.summary.duration_hours} h`} />
            <MetricCard
              label="Gem. HR"
              value={activityData.summary.average_heart_rate ? `${activityData.summary.average_heart_rate} bpm` : "n.v.t."}
            />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold">Trend insight ({activityData.period_days} dagen)</h2>
            <p className="mt-2 text-sm text-slate-700">{trendInsight}</p>
            <p className="mt-2 text-sm text-slate-600">
              Run/Fiets verdeling: {activityData.summary.running_sessions} / {activityData.summary.cycling_sessions}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              Langste sessie: {activityData.summary.longest_session_minutes} min · Max HR:{" "}
              {activityData.summary.max_heart_rate ?? "n.v.t."}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold">Wekelijkse trend</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="px-2 py-2">Week start</th>
                    <th className="px-2 py-2">Sessies</th>
                    <th className="px-2 py-2">Afstand</th>
                    <th className="px-2 py-2">Duur</th>
                    <th className="px-2 py-2">Gem. HR</th>
                  </tr>
                </thead>
                <tbody>
                  {activityData.weekly_trend.map((week) => (
                    <tr key={week.week_start} className="border-b border-slate-100">
                      <td className="px-2 py-2">{week.week_start}</td>
                      <td className="px-2 py-2">{week.sessions}</td>
                      <td className="px-2 py-2">{week.distance_km} km</td>
                      <td className="px-2 py-2">{week.duration_hours} h</td>
                      <td className="px-2 py-2">{week.average_heart_rate ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">Activiteit details</h2>
        <div className="mt-5 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="px-2 py-2">Type</th>
                <th className="px-2 py-2">Naam</th>
                <th className="px-2 py-2">Datum</th>
                <th className="px-2 py-2">Afstand</th>
                <th className="px-2 py-2">Duur</th>
                <th className="px-2 py-2">Avg HR</th>
                <th className="px-2 py-2">Max HR</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((activity) => (
                <tr key={activity.id} className="border-b border-slate-100">
                  <td className="px-2 py-2">{activity.activity_type}</td>
                  <td className="px-2 py-2">{activity.activity_name ?? "-"}</td>
                  <td className="px-2 py-2">{new Date(activity.start_time).toLocaleString()}</td>
                  <td className="px-2 py-2">{((activity.distance_meters ?? 0) / 1000).toFixed(1)} km</td>
                  <td className="px-2 py-2">{Math.round((activity.duration_seconds ?? 0) / 60)} min</td>
                  <td className="px-2 py-2">{activity.average_heart_rate ?? "-"}</td>
                  <td className="px-2 py-2">{activity.max_heart_rate ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
