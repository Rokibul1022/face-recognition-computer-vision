import { useEffect, useRef, useState } from "react";
import { useAgentApi } from "../../hooks/useAgentApi";
import type { ChatMessage, ChatReference } from "../../types";

export default function ChatTab() {
  const { askChat } = useAgentApi();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refsRef = useRef<Record<string, ChatReference[]>>({});
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    try {
      const res = await askChat(text);
      const msgId = `${next.length}`;
      refsRef.current[msgId] = res.references;
      setMessages([...next, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat request failed.");
      setMessages([...next, { role: "assistant", content: "⚠ Unable to reach the agent backend." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="tab-page chat-tab">
      <div className="tab-head">
        <h2>AGENT CHAT</h2>
        <span className="muted">Answers grounded in past events + long-term memory</span>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="chat-log" ref={listRef}>
        {messages.length === 0 && <div className="muted">Ask about activity, cameras, or incidents.</div>}
        {messages.map((m, i) => {
          const refs = refsRef.current[`${i}`];
          return (
            <div key={i} className={`chat-msg ${m.role}`}>
              <div className="chat-bubble">{m.content}</div>
              {refs && refs.length > 0 && (
                <ul className="chat-refs">
                  {refs.map((r) => (
                    <li key={r.event_id}>
                      <span className="muted">{r.human || r.description}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
        {busy && <div className="muted typing">Agent is thinking…</div>}
      </div>
      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="e.g. what happened at gate-1 today?"
        />
        <button className="btn primary" onClick={send} disabled={busy || !input.trim()}>
          SEND
        </button>
      </div>
    </section>
  );
}
