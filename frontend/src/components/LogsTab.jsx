import { useEffect, useState } from "react";
import { api } from "../api.js";
import { actionLabel, formatDate } from "../format.js";
import Pill from "./Pill.jsx";

export default function LogsTab() {
  const [logs, setLogs] = useState(null);
  const [error, setError] = useState("");
  const [failuresOnly, setFailuresOnly] = useState(false);

  async function load() {
    const res = await api("/admin/logs");
    if (res.ok) { setLogs(res.data.logs); setError(""); }
    else setError(res.data.error || "Could not load the log.");
  }

  useEffect(() => { load(); }, []);

  if (error) return <p className="error">{error}</p>;
  if (!logs) return <p className="muted">Loading activity log...</p>;

  const shown = failuresOnly ? logs.filter((l) => !l.success) : logs;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Activity log</h2>
        <div className="toolbar">
          <label className="check">
            <input type="checkbox" checked={failuresOnly}
                   onChange={(e) => setFailuresOnly(e.target.checked)} />
            Failures only
          </label>
          <button className="btn btn-secondary btn-sm" onClick={load}>Refresh</button>
        </div>
      </div>
      <p className="muted small">Latest 300 events, newest first.</p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>Time</th><th>User</th><th>Role</th><th>Action</th><th>Dataset</th><th>Details</th><th>Result</th></tr>
          </thead>
          <tbody>
            {shown.length === 0 && <tr><td colSpan="7" className="empty">No events to show.</td></tr>}
            {shown.map((l) => (
              <tr key={l.id}>
                <td className="nowrap">{formatDate(l.created_at, true)}</td>
                <td>{l.username || <span className="muted">unknown</span>}</td>
                <td>{l.role ? <Pill tone={l.role === "admin" ? "info" : "neutral"}>{l.role}</Pill> : "-"}</td>
                <td className="nowrap">{actionLabel(l.action)}</td>
                <td>{l.dataset_name || "-"}</td>
                <td className="details-cell">{l.details}</td>
                <td><Pill tone={l.success ? "ok" : "bad"}>{l.success ? "Success" : "Failure"}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
