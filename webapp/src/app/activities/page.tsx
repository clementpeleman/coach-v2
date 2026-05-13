"use client";

import { useEffect, useState } from "react";
import { fetchGarminActivities, type GarminActivity } from "@/lib/api";

export default function ActivitiesPage() {
  const [activities, setActivities] = useState<GarminActivity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const rawUserId = window.localStorage.getItem("sportsHubUserId");
        const parsed = rawUserId ? Number(rawUserId) : NaN;
        if (!Number.isInteger(parsed) || parsed <= 0) {
          setError("Geen user ID gevonden. Stel eerst een user ID in op de login pagina.");
          return;
        }

        const result = await fetchGarminActivities(parsed, 50);
        setActivities(result.activities);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Onbekende fout");
      }
    };

    void load();
  }, []);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold">Activities</h1>
      {error ? <p className="mt-3 text-sm text-rose-700">{error}</p> : null}

      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="px-2 py-2">Type</th>
              <th className="px-2 py-2">Datum</th>
              <th className="px-2 py-2">Afstand</th>
              <th className="px-2 py-2">Duur</th>
              <th className="px-2 py-2">Avg HR</th>
            </tr>
          </thead>
          <tbody>
            {activities.map((activity) => (
              <tr key={activity.id} className="border-b border-slate-100">
                <td className="px-2 py-2">{activity.activity_type}</td>
                <td className="px-2 py-2">
                  {new Date(activity.start_time).toLocaleString()}
                </td>
                <td className="px-2 py-2">{((activity.distance_meters ?? 0) / 1000).toFixed(1)} km</td>
                <td className="px-2 py-2">{Math.round((activity.duration_seconds ?? 0) / 60)} min</td>
                <td className="px-2 py-2">{activity.average_heart_rate ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
