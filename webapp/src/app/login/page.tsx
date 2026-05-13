"use client";

import { useMemo, useState } from "react";
import { getGarminAuthStartUrl, loginWebUser } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [resolvedUserId, setResolvedUserId] = useState<number | null>(null);
  const [savedMessage, setSavedMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const hasValidEmail = useMemo(() => email.includes("@"), [email]);
  const canConnectGarmin = resolvedUserId !== null;

  const handleLogin = async () => {
    if (!hasValidEmail) {
      setSavedMessage("Voer een geldig email adres in.");
      return;
    }

    try {
      setLoading(true);
      setSavedMessage("");
      const user = await loginWebUser(email, displayName || undefined);
      window.localStorage.setItem("sportsHubUserId", String(user.user_id));
      setResolvedUserId(user.user_id);
      setSavedMessage(
        user.created
          ? `Account aangemaakt. User ID ${user.user_id} opgeslagen.`
          : `Welkom terug. User ID ${user.user_id} geladen.`,
      );
    } catch (error) {
      setSavedMessage(error instanceof Error ? error.message : "Login mislukt.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold">Login & Garmin koppeling</h1>
      <p className="mt-2 text-sm text-slate-600">
        Log in met je email. De app maakt of hergebruikt je interne user account en gebruikt
        daarna die user ID voor Garmin OAuth.
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
            onClick={handleLogin}
            disabled={loading}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white"
          >
            {loading ? "Bezig..." : "Login"}
          </button>
          <a
            href={canConnectGarmin ? getGarminAuthStartUrl(resolvedUserId) : "#"}
            className={`rounded-md px-4 py-2 text-sm ${
              canConnectGarmin
                ? "bg-emerald-600 text-white"
                : "cursor-not-allowed bg-slate-200 text-slate-500"
            }`}
          >
            Connect Garmin
          </a>
        </div>
        {savedMessage ? <p className="mt-3 text-sm text-slate-700">{savedMessage}</p> : null}
      </div>
    </section>
  );
}
