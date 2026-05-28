"use client";

import { useRef, useState } from "react";
import { sendChatMessage } from "@/lib/api";
import { useSessionUserId } from "@/lib/session";
import { MessageCircle, X, Send, Bot, User } from "lucide-react";

type UIMessage = {
  role: "user" | "assistant";
  content: string;
  analysis_result?: {
    title?: string;
    summary?: string;
    metrics?: Array<{ label: string; value: string | number | null; unit?: string }>;
    confidence?: { level?: string; label?: string };
    coverage?: { sessions?: number };
  };
};

export default function CoachChat() {
  const session = useSessionUserId();
  const userId = session.userId;
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const handleSend = async (text?: string) => {
    const msg = text ?? input.trim();
    if (!userId || !msg || loading) return;

    const userMessage: UIMessage = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const response = await sendChatMessage({
        userId,
        message: msg,
        history: messages,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.reply,
          analysis_result: response.analysis_result,
        },
      ]);
      scrollToBottom();
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Er ging iets mis. Probeer het opnieuw." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!session.resolved || !userId) return null;

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-20 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600 text-white shadow-lg transition-transform hover:scale-105 lg:bottom-6"
        >
          <MessageCircle className="h-6 w-6" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-0 right-0 z-40 flex h-[80vh] w-full flex-col border-l border-t border-slate-200 bg-white shadow-2xl sm:bottom-4 sm:right-4 sm:h-[70vh] sm:w-96 sm:rounded-2xl sm:border lg:bottom-6 lg:right-6">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-emerald-100 p-1.5">
                <Bot className="h-4 w-4 text-emerald-700" />
              </div>
              <div>
                <p className="text-sm font-semibold">AI Coach</p>
                <p className="text-[10px] text-slate-400">Altijd beschikbaar</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-lg p-1.5 hover:bg-slate-100">
              <X className="h-4 w-4 text-slate-500" />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="mb-3 h-8 w-8 text-slate-300" />
                <p className="text-sm font-medium text-slate-400">Hoe kan ik je helpen?</p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {[
                    "Hoe was mijn week?",
                    "Wat moet ik morgen trainen?",
                    "Analyseer mijn hartslag",
                    "Maak een training voor morgen",
                    "Toon mijn activiteitentrend",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => handleSend(s)}
                      className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, idx) => (
              <div
                key={`${message.role}-${idx}`}
                className={`flex gap-2 ${message.role === "user" ? "justify-end" : ""}`}
              >
                {message.role === "assistant" && (
                  <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                    <Bot className="h-3.5 w-3.5 text-emerald-700" />
                  </div>
                )}
                <div className={`flex max-w-[85%] flex-col gap-2 ${message.role === "user" ? "items-end" : "items-start"}`}>
                  <div
                    className={`rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                      message.role === "user"
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {message.role === "assistant" ? (
                      <div
                        className="coach-reply prose prose-sm prose-slate max-w-none [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-xs [&_strong]:text-slate-900 [&_code]:rounded [&_code]:bg-slate-200 [&_code]:px-1"
                        dangerouslySetInnerHTML={{ __html: formatCoachContent(message.content) }}
                      />
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>
                  {message.role === "assistant" && message.analysis_result && (
                    <AnalysisPreview result={message.analysis_result} />
                  )}
                </div>
                {message.role === "user" && (
                  <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200">
                    <User className="h-3.5 w-3.5 text-slate-600" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-2">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                  <Bot className="h-3.5 w-3.5 text-emerald-700" />
                </div>
                <div className="rounded-2xl bg-slate-100 px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" style={{ animationDelay: "150ms" }} />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-slate-100 p-3">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder="Stel een vraag..."
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              <button
                onClick={() => handleSend()}
                disabled={loading || !input.trim()}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function formatCoachContent(content: string): string {
  const raw = String(content || "");
  if (!raw.trim()) return "";
  if (/<\/?[a-z][\s\S]*>/i.test(raw)) {
    return sanitiseCoachHtml(raw)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  }
  return markdownToHtml(raw);
}

function sanitiseCoachHtml(raw: string): string {
  return String(raw || "")
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, "")
    .replace(/\son\w+=(["']).*?\1/gi, "")
    .replace(/\shref=(["'])javascript:.*?\1/gi, "")
    .replace(/\n{2,}/g, "<br/><br/>")
    .replace(/\n/g, "<br/>");
}

function markdownToHtml(raw: string): string {
  const lines = escapeHtml(raw.trim()).split(/\n/);
  const html: string[] = [];
  let listType: "ul" | "ol" | null = null;
  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      html.push("<br/>");
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      const nextType = bullet ? "ul" : "ol";
      if (listType !== nextType) {
        closeList();
        html.push(`<${nextType}>`);
        listType = nextType;
      }
      html.push(`<li>${inlineMarkdown((bullet ? bullet[1] : numbered?.[1]) ?? "")}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  }
  closeList();
  return html.join("");
}

function inlineMarkdown(text: string): string {
  return String(text || "")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/(^|[\s(])_([^_\n]+)_/g, "$1<em>$2</em>");
}

function escapeHtml(value: string): string {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function AnalysisPreview({ result }: { result: NonNullable<UIMessage["analysis_result"]> }) {
  return (
    <div className="w-full rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            Analysekaart
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{result.title ?? "Analyse"}</p>
          {result.summary && <p className="mt-1 text-xs leading-relaxed text-slate-500">{result.summary}</p>}
        </div>
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
          {result.confidence?.label ?? result.confidence?.level ?? "indicatief"}
        </span>
      </div>
      {Array.isArray(result.metrics) && result.metrics.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {result.metrics.slice(0, 4).map((metric) => (
            <div key={metric.label} className="rounded-xl bg-slate-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-slate-400">{metric.label}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {metric.value ?? "-"} {metric.unit ?? ""}
              </p>
            </div>
          ))}
        </div>
      )}
      <p className="mt-3 text-[11px] text-slate-400">
        {result.coverage?.sessions ?? 0} sessies gebruikt. Open Floating Coach voor de volledige grafiek.
      </p>
    </div>
  );
}
