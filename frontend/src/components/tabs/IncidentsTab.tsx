import { useCallback, useEffect, useState } from "react";
import { useAgentApi } from "../../hooks/useAgentApi";
import type { AgentIncident } from "../../types";

const SEVERITY_CLASS: Record<string, string> = {
  LOW: "sev-low",
  WARNING: "sev-warn",
  HIGH: "sev-high",
  CRITICAL: "sev-crit",
};

export default function IncidentsTab() {
  const { listIncidents, incidentReport } = useAgentApi();
  const [incidents, setIncidents] = useState<AgentIncident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setIncidents(await listIncidents());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents.");
    }
  }, [listIncidents]);

  useEffect(() => {
    load();
  }, [load]);

  const openReport = async (id: string) => {
    setReport(null);
    setLoadingReport(true);
    try {
      const r = await incidentReport(id);
      setReport(r.summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report.");
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <section className="tab-page">
      <div className="tab-head">
        <h2>AGENT INCIDENTS</h2>
        <button className="btn ghost" onClick={load}>REFRESH</button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {!incidents && !error && <div className="muted">Loading incidents…</div>}
      <ul className="incident-list">
        {incidents?.map((inc) => (
          <li key={inc.id} className="incident-card">
            <div className="incident-top">
              <span className={`severity ${SEVERITY_CLASS[inc.severity] ?? ""}`}>{inc.severity}</span>
              <span className="incident-action">{inc.action}</span>
              <span className="incident-time">{inc.created_at}</span>
              {inc.resolved && <span className="resolved-tag">RESOLVED</span>}
            </div>
            <p className="incident-reason">{inc.reasoning}</p>
            <div className="incident-meta">
              <code className="mono">{inc.event_id.slice(0, 8)}</code>
              {inc.reference_incident_id && (
                <span className="muted">↳ ref {inc.reference_incident_id.slice(0, 8)}</span>
              )}
              <button className="btn ghost small" onClick={() => openReport(inc.id)}>
                {loadingReport ? "…" : "REPORT"}
              </button>
            </div>
          </li>
        ))}
      </ul>
      {report && (
        <pre className="report-panel">
          <button className="btn ghost small" style={{ float: "right" }} onClick={() => setReport(null)}>✕</button>
          {report}
        </pre>
      )}
    </section>
  );
}
