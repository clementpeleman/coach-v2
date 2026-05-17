"use client";

import { useState } from "react";
import { startDirectGarminOAuth } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import { Zap, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const session = useSessionUserId();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await startDirectGarminOAuth({
        userId: session.userId ?? undefined,
      });
      window.localStorage.setItem("sportsHubUserId", String(response.user_id));
      window.location.href = response.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Garmin OAuth start mislukt.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-sm flex-col items-center py-20 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100">
        <Zap className="h-8 w-8 text-emerald-600" />
      </div>

      <h1 className="text-2xl font-bold">Verbind je Garmin</h1>
      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Koppel je Garmin account om je activiteiten, hartslag en meer automatisch te
        synchroniseren met Sports Hub.
      </p>

      <button
        onClick={handleConnect}
        disabled={loading}
        className="mt-8 flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
      >
        {loading ? (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <ArrowRight className="h-4 w-4" />
        )}
        {loading ? "Bezig..." : "Verbind met Garmin"}
      </button>

      {error && (
        <p className="mt-4 rounded-lg bg-rose-50 px-4 py-2 text-xs text-rose-700">{error}</p>
      )}

      {session.userId && (
        <p className="mt-6 text-xs text-slate-400">
          Ingelogd als user {session.userId}
        </p>
      )}
    </div>
  );
}
