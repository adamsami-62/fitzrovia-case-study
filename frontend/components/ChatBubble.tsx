"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Msg = { role: "user" | "assistant" | "error"; text: string };

export function ChatBubble() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new message.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [msgs, busy]);

  async function submit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const r = await api.askChat(q);
      if (r.error) {
        setMsgs((m) => [...m, { role: "error", text: r.error as string }]);
      } else {
        setMsgs((m) => [...m, { role: "assistant", text: r.answer }]);
      }
    } catch (err) {
      setMsgs((m) => [
        ...m,
        { role: "error", text: err instanceof Error ? err.message : "Request failed" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const suggested = [
    "How many 1-bedrooms are available?",
    "Which building has the best incentive?",
    "What is the cheapest unit available?",
  ];

  return (
    <>
      {/* Floating trigger button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 bg-navy text-paper px-5 py-3 shadow-lg hover:bg-ink transition-colors font-medium tracking-wide text-sm"
          aria-label="Open chat assistant"
        >
          Ask the data
        </button>
      )}

      {/* Panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-40 w-[380px] max-w-[calc(100vw-3rem)] bg-paper border border-rule shadow-2xl flex flex-col max-h-[80vh]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-rule bg-navy text-paper">
            <div>
              <div className="font-display text-base">Ask the data</div>
              <div className="text-[0.65rem] uppercase tracking-[0.18em] text-paper/60">
                Grounded in the latest scrape
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-paper/70 hover:text-paper text-lg leading-none"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm">
            {msgs.length === 0 && (
              <div>
                <div className="text-xs text-muted mb-2">Try asking:</div>
                <div className="flex flex-col gap-1.5">
                  {suggested.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setInput(s); }}
                      className="text-left text-xs px-3 py-1.5 border border-rule hover:border-navy transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {msgs.map((m, i) => (
              <div key={i}>
                {m.role === "user" && (
                  <div className="flex justify-end">
                    <div className="bg-navy text-paper px-3 py-2 max-w-[85%] text-sm">
                      {m.text}
                    </div>
                  </div>
                )}
                {m.role === "assistant" && (
                  <div className="flex justify-start">
                    <div className="bg-[#f2eee6] text-ink px-3 py-2 max-w-[85%] text-sm whitespace-pre-wrap">
                      {m.text}
                    </div>
                  </div>
                )}
                {m.role === "error" && (
                  <div className="flex justify-start">
                    <div className="border-l-2 border-rust bg-rust/10 text-ink px-3 py-2 max-w-[85%] text-xs">
                      {m.text}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {busy && (
              <div className="flex justify-start">
                <div className="bg-[#f2eee6] text-muted px-3 py-2 text-sm">Thinking...</div>
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={submit} className="px-3 py-3 border-t border-rule flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about rents, units, incentives..."
              className="flex-1 px-3 py-2 bg-transparent border border-rule focus:border-navy outline-none text-sm"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="px-4 py-2 bg-navy text-paper hover:bg-ink transition-colors text-sm font-medium"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
