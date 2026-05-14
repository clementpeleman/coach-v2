"use client";

import { useEffect, useState } from "react";
import { fetchGarminAuthStatus, fetchWebUser, startDirectGarminOAuth, type WebUser } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import { Link2, UserCircle, Shield } from "lucide-react";

export default function SettingsPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [garminConnected, setGarminConnected] = useState(false);
  const [garminId, setGarminId] = useState<string | null>(null);
  const [user, setUser] = useState<WebUser | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!session.resolved || !userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const [status, webUser] = await Promise.all([
          fetchGarminAuthStatus(userId),
          fetchWebUser(userId).catch(() => null),
        ]);
        setGarminConnected(status.authenticated);
        setGarminId(status.garmin_user_id ?? null);
        setUser(webUser);
      } catch { /* ignore */ }
      setLoading(false);
    };
    void load();
  }, [session.resolved, userId]);

  const handleReconnect = async () => {
    if (!userId) return;
    try {
      const result = await startDirectGarminOAuth({ userId });
      window.location.href = result.authorization_url;
    } catch { /* ignore */ }
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
        <p className="text-sm text-amber-800">Log eerst in.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-bold">Instellingen</h1>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <UserCircle className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold">Profiel</h2>
        </div>
        <div className="space-y-3 px-5 py-4">
          <Row label="User ID" value={String(userId)} />
          {user?.email && <Row label="Email" value={user.email} />}
          {user?.display_name && <Row label="Naam" value={user.display_name} />}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <Link2 className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold">Garmin koppeling</h2>
        </div>
        <div className="space-y-3 px-5 py-4">
          <Row
            label="Status"
            value={
              <span className={garminConnected ? "text-emerald-600" : "text-amber-600"}>
                {garminConnected ? "Verbonden" : "Niet verbonden"}
              </span>
            }
          />
          {garminId && <Row label="Garmin ID" value={garminId} />}
          <button
            onClick={handleReconnect}
            className="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            {garminConnected ? "Opnieuw verbinden" : "Verbind Garmin"}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <Shield className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold">Privacy</h2>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm text-slate-600">
            Al je data wordt lokaal opgeslagen en enkel gebruikt voor jouw coaching.
          </p>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
