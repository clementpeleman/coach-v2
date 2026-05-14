"use client";

import { useMemo, useState } from "react";
import { startDirectGarminOAuth } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const hasValidEmail = useMemo(() => email.includes("@"), [email]);

  const handleDirectGarminConnect = async () => {
    try {
      setLoading(true);
      setSavedMessage("");
      const rawUserId = window.localStorage.getItem("sportsHubUserId");
      const parsedUserId = rawUserId ? Number(rawUserId) : NaN;
      const response = await startDirectGarminOAuth({
        userId: Number.isInteger(parsedUserId) && parsedUserId > 0 ? parsedUserId : undefined,
        email: hasValidEmail ? email : undefined,
        displayName: displayName || undefined,
      });
      window.localStorage.setItem("sportsHubUserId", String(response.user_id));
      window.location.href = response.authorization_url;
    } catch (error) {
      setSavedMessage(error instanceof Error ? error.message : "Directe Garmin OAuth start mislukt.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold">Login & Garmin koppeling</h1>
      <p className="mt-2 text-sm text-slate-600">
        Koppel direct met Garmin OAuth. De app maakt automatisch een interne user en slaat je
        user ID lokaal op.
      </p>
      <p className="mt-1 text-sm text-slate-600">
        Als je al eerder bent ingelogd op dit toestel, hoef je email/naam niet opnieuw in te vullen.
      </p>

      <div className="mt-6 max-w-sm">
        <label className="mb-2 block text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          placeholder="jij@voorbeeld.com"
        />
        <label className="mb-2 mt-3 block text-sm font-medium" htmlFor="display-name">
          Naam (optioneel)
        </label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          placeholder="Jouw naam"
        />
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleDirectGarminConnect}
            disabled={loading}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm text-white"
          >
            {loading ? "Bezig..." : "Connect Garmin direct"}
          </button>
        </div>
        {savedMessage ? <p className="mt-3 text-sm text-slate-700">{savedMessage}</p> : null}
      </div>
    </section>
  );
}
