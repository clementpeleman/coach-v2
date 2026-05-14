"use client";

import { useState } from "react";
import { sendChatMessage } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";

type UIMessage = {
  role: "user" | "assistant";
  content: string;
};

export default function ChatPage() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async () => {
    if (!userId || !input.trim() || loading) {
      return;
    }

    const userMessage: UIMessage = { role: "user", content: input.trim() };
    const history = [...messages, userMessage];

    setMessages(history);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await sendChatMessage({
        userId,
        message: userMessage.content,
        history: messages,
      });
      setMessages((current) => [...current, { role: "assistant", content: response.reply }]);
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "Chat request mislukt.");
    } finally {
      setLoading(false);
    }
  };

  if (!session.resolved) {
    return <p>Laden...</p>;
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold">Coach Chat</h1>
      <p className="mt-2 text-sm text-slate-600">User ID: {userId ?? "niet ingelogd"}</p>

      <div className="mt-4 h-80 overflow-y-auto rounded-md border border-slate-200 p-3">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">Start een gesprek met je coach.</p>
        ) : (
          <ul className="space-y-3">
            {messages.map((message, idx) => (
              <li
                key={`${message.role}-${idx}`}
                className={`rounded-md p-2 text-sm ${
                  message.role === "user" ? "bg-slate-100" : "bg-emerald-50"
                }`}
              >
                <p className="mb-1 text-xs font-semibold uppercase text-slate-500">{message.role}</p>
                <p className="whitespace-pre-wrap">{message.content}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void handleSend();
            }
          }}
          placeholder="Typ je vraag..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-2"
        />
        <button
          onClick={handleSend}
          disabled={loading || !userId}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {loading ? "Bezig..." : "Verstuur"}
        </button>
      </div>

      {!userId ? (
        <p className="mt-3 text-sm text-rose-700">
          Geen user ID gevonden. Log eerst in op de login pagina.
        </p>
      ) : null}
      {error ? <p className="mt-3 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}
