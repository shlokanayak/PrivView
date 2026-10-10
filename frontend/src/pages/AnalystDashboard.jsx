import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { formatDate } from "../format.js";
import Header from "../components/Header.jsx";
import Pill from "../components/Pill.jsx";
import "../analyst.css";

// Analyst dashboard: ONLY the datasets the admin granted to this analyst.
// The list comes from GET /api/analyst/datasets (backend checks role + dataset_access).
export default function AnalystDashboard({ setUser }) {
  const [datasets, setDatasets] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/analyst/datasets").then((r) =>
      r.ok ? setDatasets(r.data.datasets) : setError(r.data.error || "Could not load your datasets."));
  }, []);

  return (
    <div className="admin">
      <Header setUser={setUser} role="analyst" />
      <main className="page">
        <div className="page-head">
          <div>
            <h1>Analyst dashboard</h1>
            <p className="muted">
              Datasets shared with you. Analysis runs on the protected copy only - you never see original values.
            </p>
          </div>
        </div>

        {error && <div className="notice notice-bad">{error}</div>}
        {!datasets && !error && <p className="muted">Loading your datasets...</p>}

        {datasets && datasets.length === 0 && (
          <div className="panel">
            <p className="empty">
              No datasets have been shared with you yet. Ask a system administrator to grant you access.
            </p>
          </div>
        )}

        {datasets && datasets.length > 0 && (
          <div className="ds-grid">
            {datasets.map((d) => (
              <article className="ds-card" key={d.id}>
                <div className="ds-card-head">
                  <h3>{d.name}</h3>
                  <Pill tone="ok">Protected</Pill>
                </div>
                <p className="ds-desc">{d.description || d.filename}</p>

                <div className="ds-stats">
                  <div className="ds-stat"><b>{d.record_count.toLocaleString()}</b><span>Records</span></div>
                  <div className="ds-stat"><b>{d.column_count}</b><span>Fields</span></div>
                  <div className="ds-stat"><b>{d.masked_fields}</b><span>Masked fields</span></div>
                </div>

                <div className="ds-meta">
                  Last updated {formatDate(d.updated_at)} by {d.updated_by}<br />
                  Sanitised and masked{d.encryption ? ` · ${d.encryption} at rest` : ""}
                </div>
                <Link className="btn" to={`/analyst/dataset/${d.id}`}>Open analysis workspace</Link>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
