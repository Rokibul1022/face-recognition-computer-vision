import { useState } from "react";
import { useAgentApi } from "../../hooks/useAgentApi";

export default function SettingsTab() {
  const { sendAlert, getSummary } = useAgentApi();
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState("WARNING");
  const [result, setResult] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!message.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await sendAlert(message, severity);
      const channels = Object.entries(r.channels)
        .filter(([, ok]) => ok)
        .map(([name]) => name);
      setResult(channels.length > 0 ? `Delivered via ${channels.join(", ")}` : "No channels configured (no-op).");
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Alert failed.");
    } finally {
      setBusy(false);
    }
  };

  const runSummary = async () => {
    setBusy(true);
    setSummary(null);
    try {
      const s = await getSummary();
      const counts = Object.entries(s.by_severity ?? {})
        .map(([k, v]) => `${k}:${v}`)
        .join("  ");
      setSummary(
        `Window: ${s.window_seconds}s | Events: ${s.total_events}\nBy severity: ${counts}\nIncidents: ${s.incidents.length}`
      );
    } catch (e) {
      setSummary(e instanceof Error ? e.message : "Summary failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="tab-page">
      <div className="tab-head">
        <h2>OPERATOR SETTINGS</h2>
      </div>

      <div className="settings-group">
        <h3>MANUAL ALERT</h3>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Message for the security desk / channels…"
          rows={3}
        />
        <div className="row">
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option>LOW</option>
            <option>WARNING</option>
            <option>HIGH</option>
            <option>CRITICAL</option>
          </select>
          <button className="btn primary" onClick={send} disabled={busy || !message.trim()}>
            SEND ALERT
          </button>
        </div>
        {result && <div className="muted">{result}</div>}
      </div>

      <div className="settings-group">
        <h3>DAILY SUMMARY</h3>
        <button className="btn ghost" onClick={runSummary} disabled={busy}>
          GENERATE SUMMARY
        </button>
        {summary && <pre className="report-panel">{summary}</pre>}
      </div>
    </section>
  );
}
