import { useState, useEffect, useRef } from "react";

const API = "";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #0a0e1a;
    color: #e2e8f0;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    min-height: 100vh;
    overflow-x: hidden;
  }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #1e2d4a; border-radius: 2px; }

  .mono { font-family: 'JetBrains Mono', monospace; }

  .glow-blue { box-shadow: 0 0 0 1px #1d6fdb22, inset 0 1px 0 #ffffff08; }
  .glow-active { box-shadow: 0 0 20px #3b82f620, 0 0 0 1px #3b82f640; }

  .card {
    background: #0f1729;
    border: 1px solid #1a2744;
    border-radius: 12px;
    overflow: hidden;
  }

  .card-header {
    padding: 12px 16px;
    border-bottom: 1px solid #1a2744;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #0c1422;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4a6fa5;
  }

  .btn {
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid #1a2744;
    background: #0f1729;
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn:hover { background: #1a2744; color: #e2e8f0; }
  .btn.primary {
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    border-color: #3b82f6;
    color: #fff;
    box-shadow: 0 0 16px #2563eb30;
  }
  .btn.primary:hover { background: linear-gradient(135deg, #2563eb, #3b82f6); box-shadow: 0 0 24px #2563eb50; }
  .btn.primary:disabled { background: #1a2744; border-color: #1a2744; color: #4a6fa5; box-shadow: none; cursor: not-allowed; }
  .btn.danger { border-color: #991b1b; color: #f87171; }
  .btn.danger:hover { background: #1c0a0a; }
  .btn.success { border-color: #166534; color: #4ade80; }
  .btn.success:hover { background: #0a1c0f; }
  .btn.tab { border: none; background: transparent; border-radius: 6px; padding: 6px 14px; }
  .btn.tab.active { background: #1a2744; color: #60a5fa; }

  .badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    padding: 2px 7px;
    border-radius: 4px;
    letter-spacing: 0.04em;
  }
  .badge.p1 { background: #1c0a0a; color: #f87171; border: 1px solid #7f1d1d; }
  .badge.p2 { background: #1c1000; color: #fbbf24; border: 1px solid #78350f; }
  .badge.p3 { background: #0a1c10; color: #4ade80; border: 1px solid #166534; }

  .status-dot {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: #64748b;
  }
  .status-dot::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    display: inline-block;
    flex-shrink: 0;
  }
  .status-dot.resolved { color: #4ade80; }
  .status-dot.running { color: #60a5fa; animation: pulse 1.5s infinite; }
  .status-dot.pending_hitl { color: #fbbf24; }
  .status-dot.approved { color: #4ade80; }
  .status-dot.rejected { color: #f87171; }
  .status-dot.error { color: #f87171; }

  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
  @keyframes fadeIn { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
  @keyframes slideIn { from { opacity:0; transform:translateX(-6px); } to { opacity:1; transform:translateX(0); } }

  .alert-item {
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid #1a2744;
    background: #0c1422;
    cursor: pointer;
    transition: all 0.15s;
  }
  .alert-item:hover { border-color: #2a3f6a; background: #111d33; }
  .alert-item.selected { border-color: #3b82f6; background: #0e1e3a; box-shadow: 0 0 12px #3b82f618; }

  .incident-row {
    padding: 10px 14px;
    border-bottom: 1px solid #0f1729;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: background 0.12s;
    animation: fadeIn 0.25s ease;
  }
  .incident-row:hover { background: #111d33; }
  .incident-row.selected { background: #0e1e3a; }

  .agent-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    transition: opacity 0.3s;
  }
  .agent-step.dim { opacity: 0.3; }

  .agent-icon {
    width: 30px; height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    border: 1px solid #1a2744;
    background: #0c1422;
    color: #4a6fa5;
    flex-shrink: 0;
    transition: all 0.3s;
  }
  .agent-icon.active { background: #0e1e3a; border-color: #3b82f6; color: #60a5fa; box-shadow: 0 0 10px #3b82f630; }
  .agent-icon.done { background: #0a1c10; border-color: #166534; color: #4ade80; }

  .log-line { animation: slideIn 0.2s ease; line-height: 1.7; }

  .metric-bar-wrap { display: flex; flex-direction: column; gap: 10px; }
  .metric-bar { height: 4px; background: #1a2744; border-radius: 2px; overflow: hidden; }
  .metric-bar-fill { height: 100%; border-radius: 2px; transition: width 0.8s cubic-bezier(0.16,1,0.3,1); }

  .stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .stat-card {
    background: #0c1422;
    border: 1px solid #1a2744;
    border-radius: 10px;
    padding: 14px;
  }

  input, select {
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    background: #0c1422;
    border: 1px solid #1a2744;
    border-radius: 8px;
    color: #e2e8f0;
    padding: 8px 12px;
    width: 100%;
    outline: none;
    transition: border-color 0.15s;
  }
  input:focus, select:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px #3b82f615; }
  input::placeholder { color: #2a3f6a; }

  .connector { width: 1px; height: 16px; background: #1a2744; margin-left: 14px; }

  .hitl-card {
    background: #1c1000;
    border: 1px solid #78350f;
    border-radius: 10px;
    padding: 14px;
    animation: fadeIn 0.3s ease;
  }

  .topbar {
    height: 52px;
    background: #0c1422;
    border-bottom: 1px solid #1a2744;
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .logo-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #3b82f6;
    box-shadow: 0 0 8px #3b82f6;
    flex-shrink: 0;
  }

  .grid-3 {
    display: grid;
    grid-template-columns: 260px 1fr 220px;
    gap: 14px;
    align-items: start;
  }

  .tabs {
    display: flex;
    gap: 4px;
    margin-left: auto;
  }
`;

const AGENTS = [
  { id: "monitor_triage", label: "Monitor & Triage", icon: "⬡" },
  { id: "data_collector", label: "Data Collector", icon: "◈" },
  { id: "diagnostic_reasoner", label: "Diagnostic Reasoner", icon: "◎" },
  { id: "remediation_planner", label: "Remediation Planner", icon: "◇" },
  { id: "postmortem_writer", label: "Postmortem Writer", icon: "◻" },
];

const DEMO_ALERTS = [
  { service: "payment-service", metric: "http_request_duration_seconds_p99", value: 2.34, threshold: 0.5, description: "P99 latency spike — DB connection pool exhaustion" },
  { service: "auth-service", metric: "container_memory_usage_bytes", value: 0.95, threshold: 0.85, description: "Memory at 95% — OOMKilled pods detected" },
  { service: "order-service", metric: "http_requests_total", value: 0.0, threshold: 50.0, description: "Service completely down — zero requests" },
  { service: "inventory-service", metric: "http_request_duration_seconds_p99", value: 8.5, threshold: 1.0, description: "Extreme latency — N+1 query after deploy" },
  { service: "search-service", metric: "elasticsearch_cluster_health", value: 2.0, threshold: 1.0, description: "Elasticsearch RED — shards unassigned" },
];

const SEV_CLASS = { P1: "p1", P2: "p2", P3: "p3" };

function Badge({ sev }) {
  return <span className={`badge ${SEV_CLASS[sev] || "p3"}`}>{sev}</span>;
}

function StatusDot({ status }) {
  const label = status?.replace("_", " ") || "";
  return <span className={`status-dot ${status || ""}`}>{label}</span>;
}

function AgentPipeline({ active, done }) {
  return (
    <div style={{ padding: "4px 0" }}>
      {AGENTS.map((a, i) => {
        const isDone = done.includes(a.id);
        const isActive = active.includes(a.id);
        return (
          <div key={a.id}>
            <div className={`agent-step${!isDone && !isActive ? " dim" : ""}`}>
              <div className={`agent-icon${isDone ? " done" : isActive ? " active" : ""}`}>
                {isDone ? "✓" : a.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: isDone ? "#4ade80" : isActive ? "#60a5fa" : "#64748b" }}>{a.label}</div>
                {isActive && <div style={{ fontSize: 10, color: "#3b82f6", marginTop: 1, fontFamily: "JetBrains Mono, monospace" }}>processing…</div>}
                {isDone && <div style={{ fontSize: 10, color: "#166534", marginTop: 1, fontFamily: "JetBrains Mono, monospace" }}>done</div>}
              </div>
            </div>
            {i < AGENTS.length - 1 && <div className="connector" />}
          </div>
        );
      })}
    </div>
  );
}

function TriggerPanel({ onCreated }) {
  const [mode, setMode] = useState("demo");
  const [sel, setSel] = useState(0);
  const [custom, setCustom] = useState({ service: "", metric: "", value: "", threshold: "", description: "" });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const fire = async () => {
    setLoading(true); setErr(null);
    const a = mode === "demo" ? DEMO_ALERTS[sel] : { ...custom, value: parseFloat(custom.value), threshold: parseFloat(custom.threshold) };
    const id = `inc-${Date.now()}`;
    try {
      const r = await fetch(`${API}/incident`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ alert_id: id, ...a }) });
      if (!r.ok) throw new Error((await r.json()).detail || "Error");
      const data = await r.json();
      onCreated({ ...data, alert_id: id, service: a.service, started_at: new Date().toISOString() });
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="section-label">Trigger incident</span>
        <div style={{ display: "flex", gap: 4 }}>
          {["demo", "custom"].map(m => (
            <button key={m} className={`btn tab${mode === m ? " active" : ""}`} onClick={() => setMode(m)} style={{ fontSize: 11, padding: "4px 10px" }}>{m}</button>
          ))}
        </div>
      </div>
      <div style={{ padding: 12 }}>
        {mode === "demo" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
            {DEMO_ALERTS.map((a, i) => (
              <div key={i} className={`alert-item${sel === i ? " selected" : ""}`} onClick={() => setSel(i)}>
                <div style={{ fontSize: 12, fontWeight: 500, color: sel === i ? "#60a5fa" : "#94a3b8", marginBottom: 2 }}>{a.service}</div>
                <div style={{ fontSize: 11, color: "#4a6fa5", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.description}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {[["service", "Service"], ["metric", "Metric"], ["value", "Value"], ["threshold", "Threshold"], ["description", "Description"]].map(([k, l]) => (
              <div key={k}>
                <div style={{ fontSize: 10, color: "#4a6fa5", marginBottom: 4, fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase", letterSpacing: "0.08em" }}>{l}</div>
                <input value={custom[k]} onChange={e => setCustom(p => ({ ...p, [k]: e.target.value }))} placeholder={l} />
              </div>
            ))}
          </div>
        )}
        {err && <div style={{ fontSize: 11, color: "#f87171", marginBottom: 8, fontFamily: "JetBrains Mono, monospace" }}>✗ {err}</div>}
        <button className="btn primary" style={{ width: "100%", fontSize: 13 }} onClick={fire} disabled={loading}>
          {loading ? "Running pipeline…" : "↗ Trigger incident"}
        </button>
      </div>
    </div>
  );
}

function IncidentList({ incidents, selected, onSelect }) {
  if (incidents.length === 0) return (
    <div style={{ textAlign: "center", padding: "24px 0", color: "#2a3f6a", fontSize: 12, fontFamily: "JetBrains Mono, monospace" }}>
      — no incidents yet —
    </div>
  );
  return (
    <div>
      {incidents.slice(0, 10).map(inc => (
        <div key={inc.alert_id} className={`incident-row${selected?.alert_id === inc.alert_id ? " selected" : ""}`} onClick={() => onSelect(inc)}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
              {inc.severity && <Badge sev={inc.severity.replace("Severity.", "")} />}
              <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{inc.service || inc.alert_id}</span>
            </div>
            {inc.root_cause && <div style={{ fontSize: 11, color: "#4a6fa5", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{inc.root_cause}</div>}
          </div>
          <StatusDot status={inc.status} />
        </div>
      ))}
    </div>
  );
}

function LiveLog({ lines }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [lines]);
  const color = { info: "#4a6fa5", success: "#4ade80", warning: "#fbbf24", danger: "#f87171" };
  return (
    <div ref={ref} style={{ height: 200, overflowY: "auto", fontFamily: "JetBrains Mono, monospace", fontSize: 11, lineHeight: 1.8, padding: "10px 14px", background: "#07101c", borderRadius: 8, border: "1px solid #1a2744" }}>
      {lines.length === 0
        ? <span style={{ color: "#1e2d4a" }}>awaiting pipeline execution…</span>
        : lines.map((l, i) => (
          <div key={i} className="log-line">
            <span style={{ color: "#1e3a5f", marginRight: 10 }}>{l.time}</span>
            <span style={{ color: color[l.type] || "#4a6fa5" }}>{l.type === "success" ? "✓" : l.type === "danger" ? "✗" : "›"} {l.msg}</span>
          </div>
        ))
      }
    </div>
  );
}

function IncidentDetail({ inc }) {
  if (!inc) return null;
  const sev = inc.severity?.replace("Severity.", "");
  return (
    <div className="card" style={{ marginTop: 14 }}>
      <div className="card-header">
        <span className="section-label">Incident detail</span>
        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#2a3f6a" }}>{inc.alert_id}</span>
      </div>
      <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {[["Service", inc.service], ["Severity", sev ? <Badge sev={sev} /> : "—"], ["Status", <StatusDot status={inc.status} />], ["Started", inc.started_at ? new Date(inc.started_at).toLocaleTimeString() : "—"]].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 10, color: "#2a3f6a", marginBottom: 4, fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontSize: 13, color: "#94a3b8" }}>{v}</div>
            </div>
          ))}
        </div>
        {inc.root_cause && (
          <div style={{ borderTop: "1px solid #1a2744", paddingTop: 10 }}>
            <div style={{ fontSize: 10, color: "#2a3f6a", marginBottom: 6, fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase" }}>Root cause</div>
            <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>{inc.root_cause}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function HITLTab({ incidents, onDecision }) {
  const pending = incidents.filter(i => i.status === "pending_hitl");
  return (
    <div style={{ maxWidth: 500 }}>
      <div style={{ fontSize: 12, color: "#4a6fa5", marginBottom: 16, lineHeight: 1.7, fontFamily: "JetBrains Mono, monospace" }}>
        Actions classified as HIGH risk by the Remediation Planner.<br />
        Approval routes through Slack bot — this panel mirrors state.
      </div>
      {pending.length === 0
        ? <div style={{ textAlign: "center", padding: "48px 0", color: "#1e2d4a", fontSize: 12, fontFamily: "JetBrains Mono, monospace" }}>— no pending approvals —</div>
        : pending.map(inc => (
          <div key={inc.alert_id} className="hitl-card" style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#fbbf24" }}>{inc.alert_id}</span>
              <Badge sev={inc.severity?.replace("Severity.", "") || "P2"} />
            </div>
            <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>{inc.service}</div>
            {inc.root_cause && <div style={{ fontSize: 11, color: "#78350f", marginBottom: 12, fontFamily: "JetBrains Mono, monospace" }}>{inc.root_cause}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn success" style={{ flex: 1, fontSize: 12 }} onClick={() => onDecision(inc.alert_id, "approve")}>✓ Approve</button>
              <button className="btn danger" style={{ flex: 1, fontSize: 12 }} onClick={() => onDecision(inc.alert_id, "reject")}>✗ Reject</button>
            </div>
          </div>
        ))
      }
    </div>
  );
}

function EvalsTab() {
  const bars = [
    { label: "Severity accuracy", value: 62, color: "#60a5fa" },
    { label: "Top-1 diagnostic accuracy", value: 38, color: "#fbbf24" },
    { label: "Top-3 diagnostic accuracy", value: 62, color: "#4ade80" },
    { label: "Avg keyword score", value: 23, color: "#4a6fa5" },
  ];
  const stats = [
    { label: "HITL rate", value: "100%", color: "#fbbf24" },
    { label: "Postmortem rate", value: "100%", color: "#4ade80" },
    { label: "Avg confidence", value: "84%", color: "#60a5fa" },
    { label: "Avg attempts", value: "1.0", color: "#94a3b8" },
    { label: "Incidents evaluated", value: "8", color: "#94a3b8" },
    { label: "Time to diagnose", value: "~7s", color: "#4ade80" },
  ];
  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#4a6fa5", marginBottom: 20, lineHeight: 1.8, background: "#07101c", padding: "10px 14px", borderRadius: 8, border: "1px solid #1a2744" }}>
        model: groq/llama-3.3-70b-versatile (dev)<br />
        dataset: 8 historical incidents w/ ground truth<br />
        prod target: claude-sonnet → top-1 &gt; 70%
      </div>
      <div className="stat-grid" style={{ marginBottom: 20 }}>
        {stats.map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ fontSize: 10, color: "#2a3f6a", marginBottom: 6, fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase", letterSpacing: "0.08em" }}>{s.label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-header"><span className="section-label">Diagnostic accuracy</span></div>
        <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
          {bars.map(b => (
            <div key={b.label}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: "#64748b" }}>{b.label}</span>
                <span style={{ fontSize: 12, fontWeight: 500, color: b.color, fontFamily: "JetBrains Mono, monospace" }}>{b.value}%</span>
              </div>
              <div className="metric-bar">
                <div className="metric-bar-fill" style={{ width: `${b.value}%`, background: b.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 14, fontSize: 11, color: "#2a3f6a", lineHeight: 1.7, fontFamily: "JetBrains Mono, monospace" }}>
        Top-1 bias toward postgres driver in ambiguous incidents.<br />
        Claude Sonnet (prod) expected significant improvement on edge cases.
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [log, setLog] = useState([]);
  const [activeAgents, setActiveAgents] = useState([]);
  const [doneAgents, setDoneAgents] = useState([]);
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    fetch(`${API}/health`).then(r => r.json()).then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    const interval = setInterval(() => {
      fetch(`${API}/health`).then(r => r.json()).then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const addLog = (msg, type = "info") => setLog(l => [...l.slice(-80), { msg, type, time: new Date().toLocaleTimeString() }]);

  const simulatePipeline = () => {
    setDoneAgents([]); setActiveAgents([]);
    const agents = AGENTS.map(a => a.id);
    agents.forEach((id, i) => {
      setTimeout(() => { setActiveAgents([id]); addLog(`${id.replace(/_/g, " ")} — started`, "info"); }, i * 1400);
      setTimeout(() => { setActiveAgents(p => p.filter(a => a !== id)); setDoneAgents(p => [...p, id]); addLog(`${id.replace(/_/g, " ")} — completed`, "success"); }, i * 1400 + 1200);
    });
    setTimeout(() => addLog("pipeline complete", "success"), agents.length * 1400 + 200);
  };

  const handleCreated = (inc) => {
    setIncidents(p => [inc, ...p]);
    setSelected(inc);
    setLog([]);
    addLog(`incident created — ${inc.alert_id}`, "info");
    addLog(`service: ${inc.service}`, "info");
    simulatePipeline();
    setTimeout(() => setIncidents(p => p.map(i => i.alert_id === inc.alert_id ? { ...i, ...inc } : i)), AGENTS.length * 1400 + 600);
  };

  const handleDecision = (alertId, dec) => {
    addLog(`HITL ${dec} — ${alertId}`, dec === "approve" ? "success" : "danger");
    setIncidents(p => p.map(i => i.alert_id === alertId ? { ...i, status: dec === "approve" ? "approved" : "rejected" } : i));
  };

  const pendingCount = incidents.filter(i => i.status === "pending_hitl").length;

  return (
    <>
      <style>{css}</style>
      <div className="topbar">
        <div className="logo-dot" />
        <span style={{ fontWeight: 600, fontSize: 14, letterSpacing: "0.01em" }}>Incident Response</span>
        <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#2a3f6a", marginLeft: 4 }}>/ AI-powered SRE</span>
        <div className="tabs">
          {[["dashboard", "Dashboard"], ["hitl", `HITL${pendingCount > 0 ? ` (${pendingCount})` : ""}`], ["evals", "Evaluations"]].map(([id, label]) => (
            <button key={id} className={`btn tab${tab === id ? " active" : ""}`} onClick={() => setTab(id)} style={{ fontSize: 12 }}>{label}</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginLeft: 16 }}>
          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: apiOnline ? "#4ade80" : "#f87171", display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block", boxShadow: apiOnline ? "0 0 6px currentColor" : "none" }} />
            {apiOnline ? "API online" : "API offline"}
          </span>
          <a href="https://eu.smith.langchain.com" target="_blank" rel="noreferrer" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#3b82f6", textDecoration: "none" }}>LangSmith ↗</a>
        </div>
      </div>

      <div style={{ padding: "16px 20px" }}>
        {tab === "dashboard" && (
          <div className="grid-3">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <TriggerPanel onCreated={handleCreated} />
              <div className="card">
                <div className="card-header"><span className="section-label">Recent incidents</span></div>
                <IncidentList incidents={incidents} selected={selected} onSelect={setSelected} />
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="card">
                <div className="card-header">
                  <span className="section-label">Live pipeline log</span>
                  {log.length > 0 && <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#2a3f6a" }}>{log.length} events</span>}
                </div>
                <div style={{ padding: "10px 12px" }}>
                  <LiveLog lines={log} />
                </div>
              </div>
              <IncidentDetail inc={selected} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="card">
                <div className="card-header"><span className="section-label">Agent pipeline</span></div>
                <div style={{ padding: "12px 14px" }}>
                  <AgentPipeline active={activeAgents} done={doneAgents} />
                </div>
              </div>
              <div className="card">
                <div className="card-header"><span className="section-label">Stack</span></div>
                <div style={{ padding: "4px 0" }}>
                  {[["LangGraph", "orchestration"], ["Groq Llama 3.3", "LLM · dev"], ["Claude Sonnet", "LLM · prod"], ["ChromaDB", "vector store"], ["Pydantic v2", "schemas"], ["LangSmith", "observability"], ["Slack bot", "HITL"], ["FastAPI", "backend"]].map(([tech, role]) => (
                    <div key={tech} style={{ display: "flex", justifyContent: "space-between", padding: "7px 14px", borderBottom: "1px solid #0f1729", fontSize: 12 }}>
                      <span style={{ color: "#94a3b8", fontWeight: 500 }}>{tech}</span>
                      <span style={{ color: "#2a3f6a", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>{role}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "hitl" && <HITLTab incidents={incidents} onDecision={handleDecision} />}
        {tab === "evals" && <EvalsTab />}
      </div>
    </>
  );
}
