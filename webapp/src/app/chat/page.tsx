"use client";

import { useRef, useState } from "react";
import { sendChatMessage } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import { Send, Bot, User } from "lucide-react";

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
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const handleSend = async () => {
    if (!userId || !input.trim() || loading) return;

    const userMessage: UIMessage = { role: "user", content: input.trim() };
    const history = [...messages, userMessage];

    setMessages(history);
    setInput("");
    setLoading(true);
    setError(null);
    scrollToBottom();

    try {
      const response = await sendChatMessage({
        userId,
        message: userMessage.content,
        history: messages,
      });
      setMessages((current) => [...current, { role: "assistant", content: response.reply }]);
      scrollToBottom();
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "Chat request mislukt.");
    } finally {
      setLoading(false);
    }
  };

  if (!session.resolved) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-emerald-600" />
      </div>
    );
  }

  if (!userId) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="text-sm text-amber-800">Log eerst in om de coach te gebruiken.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col" style={{ height: "calc(100vh - 8rem)" }}>
      <div className="mb-4 flex items-center gap-3">
        <div className="rounded-lg bg-emerald-100 p-2">
          <Bot className="h-5 w-5 text-emerald-700" />
        </div>
        <div>
          <h1 className="text-lg font-bold">AI Coach</h1>
          <p className="text-xs text-slate-500">Stel vragen over je training, data of planning</p>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4"
      >
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Bot className="mb-3 h-10 w-10 text-slate-300" />
            <p className="text-sm font-medium text-slate-400">Hoe kan ik je helpen?</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {[
                "Hoe was mijn week?",
                "Wat moet ik morgen trainen?",
                "Analyseer mijn hartslag",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, idx) => (
          <div
            key={`${message.role}-${idx}`}
            className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}
          >
            {message.role === "assistant" && (
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                <Bot className="h-4 w-4 text-emerald-700" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                message.role === "user"
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
            {message.role === "user" && (
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200">
                <User className="h-4 w-4 text-slate-600" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100">
              <Bot className="h-4 w-4 text-emerald-700" />
            </div>
            <div className="rounded-2xl bg-slate-100 px-4 py-3">
              <div className="flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "150ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}

      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
          placeholder="Typ je vraag..."
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="flex h-[46px] w-[46px] items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
