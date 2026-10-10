// AccessPanel.jsx - Admin decides which analysts may analyse this dataset.
// Grant / revoke is saved in the dataset_access table by the Flask backend.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import Pill from "./Pill.jsx";

export default function AccessPanel({ datasetId }) {
  const [analysts, setAnalysts] = useState(null);
  const [message, setMessage] = useState(null);

  async function load() {
    const res = await api(`/admin/datasets/${datasetId}/access`);
    if (res.ok) setAnalysts(res.data.analysts);
    else setMessage({ type: "bad", text: res.data.error || "Could not load analyst access." });
  }

  useEffect(() => { setAnalysts(null); load(); }, [datasetId]);

  async function toggle(analyst) {
    const res = await api(`/admin/datasets/${datasetId}/access/${analyst.id}`,
                          analyst.has_access ? "DELETE" : "PUT");
    setMessage(res.ok ? { type: "ok", text: res.data.message } : { type: "bad", text: res.data.error });
    load();
  }

  return (
    <>
      <h3 className="section-title">Analyst access</h3>
      <p className="muted small">
        Analysts only see datasets you grant here. Revoking takes effect on their next request,
        and deleting the dataset removes it for everyone.
      </p>
      {message && <div className={"notice notice-" + message.type}>{message.text}</div>}
      {!analysts ? <p className="muted">Loading...</p> : analysts.length === 0 ? (
        <p className="empty">There are no analyst accounts.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Analyst</th><th>Account</th><th>Access to this dataset</th><th></th></tr></thead>
            <tbody>
              {analysts.map((a) => (
                <tr key={a.id}>
                  <td className="cell-title">{a.username}</td>
                  <td><Pill tone={a.is_active ? "ok" : "bad"}>{a.is_active ? "Active" : "Inactive"}</Pill></td>
                  <td><Pill tone={a.has_access ? "info" : "neutral"}>{a.has_access ? "Granted" : "No access"}</Pill></td>
                  <td className="actions">
                    <button className={a.has_access ? "btn btn-danger-outline btn-sm" : "btn btn-secondary btn-sm"}
                            onClick={() => toggle(a)}>
                      {a.has_access ? "Revoke" : "Grant access"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
