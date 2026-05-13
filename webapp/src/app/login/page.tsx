"use client";

import { useMemo, useState } from "react";
import { getGarminAuthStartUrl } from "@/lib/api";

export default function LoginPage() {
  const [userIdInput, setUserIdInput] = useState("");
  const [savedMessage, setSavedMessage] = useState("");

  const parsedUserId = useMemo(() => Number(userIdInput), [userIdInput]);
  const hasValidUserId = Number.isInteger(parsedUserId) && parsedUserId > 0;

  const handleSaveUserId = () => {
    if (!hasValidUserId) {
      setSavedMessage("Voer een geldige numerieke user ID in.");
      return;
    }

    window.localStorage.setItem("sportsHubUserId", String(parsedUserId));
    setSavedMessage(`User ID ${parsedUserId} opgeslagen.`);
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold">Login & Garmin koppeling</h1>
      <p className="mt-2 text-sm text-slate-600">
        Voor deze eerste versie werken we met een vaste interne user ID. Deze ID gebruiken we
        om Garmin OAuth te starten en later je dashboard te laden.
      </p>

      <div className="mt-6 max-w-sm">
        <label className="mb-2 block text-sm font-medium" htmlFor="user-id">
          User ID
        </label>
        <input
          id="user-id"
          type="number"
          min={1}
          value={userIdInput}
          onChange={(event) => setUserIdInput(event.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          placeholder="Bijv. 12345"
        />
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleSaveUserId}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white"
          >
            Save user ID
          </button>
          <a
            href={hasValidUserId ? getGarminAuthStartUrl(parsedUserId) : "#"}
            className={`rounded-md px-4 py-2 text-sm ${
              hasValidUserId
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
