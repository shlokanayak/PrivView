import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile } from "../api.js";
import { formatDate } from "../format.js";
import Pill from "./Pill.jsx";
import ConfirmDialog from "./ConfirmDialog.jsx";
import DatasetDetails from "./DatasetDetails.jsx";

const STATUS = {
  processing: ["wait", "Processing"],
  protected: ["ok", "Protected & encrypted"],
  failed: ["bad", "Failed"],
};

export default function DatasetsTab() {
  const [datasets, setDatasets] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState(null);

  async function load() {
    const res = await api("/admin/datasets");
    if (res.ok) setDatasets(res.data.datasets);
    else setMessage({ type: "bad", text: res.data.error || "Could not load datasets." });
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!datasets || !datasets.some((d) => d.status === "processing")) return;
    const timer = setInterval(load, 1500);
    return () => clearInterval(timer);
  }, [datasets]);

  async function confirmDelete() {
    setDeleting(true);
    const res = await api(`/admin/datasets/${toDelete.id}`, "DELETE");
    setDeleting(false);
    setMessage(res.ok ? { type: "ok", text: res.data.message }
                      : { type: "bad", text: res.data.error });
    if (res.ok && selectedId === toDelete.id) setSelectedId(null);
    setToDelete(null);
    load();
  }

  async function download(d) {
    setMessage(null);
    const res = await downloadFile(`/admin/datasets/${d.id}/download`, "protected_dataset.csv");
    setMessage(res.ok ? { type: "ok", text: `Downloaded ${res.name}` }
                      : { type: "bad", text: res.error });
  }

  if (!datasets) return <p className="muted">Loading datasets...</p>;

  return (
    <>
      {message && <div className={"notice notice-" + message.type}>{message.text}</div>}

      <div className="panel">
        <div className="panel-head">
          <h2>Uploaded datasets</h2>
          <Link className="btn btn-sm" to="/admin/upload">Upload dataset</Link>
        </div>

        {datasets.length === 0 ? (
          <p className="empty">No datasets yet. Upload a CSV or XLSX file to protect it.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Dataset</th><th>Type</th><th>Uploaded</th>
                  <th className="num">Records</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => {
                  const [tone, label] = STATUS[d.status];
                  return (
                    <tr key={d.id} className={d.id === selectedId ? "row-selected" : ""}>
                      <td>
                        <div className="cell-title">{d.name}</div>
                        <div className="muted small">{d.filename}</div>
                      </td>
                      <td>{d.file_type.toUpperCase()}</td>
                      <td>{formatDate(d.created_at)}</td>
                      <td className="num">{d.status === "protected" ? d.record_count : "-"}</td>
                      <td><Pill tone={tone}>{label}</Pill></td>
                      <td className="actions">
                        <button className="btn btn-secondary btn-sm" onClick={() => setSelectedId(d.id)}>
                          Details
                        </button>
                        {d.status === "protected" && (
                          <button className="btn btn-secondary btn-sm" onClick={() => download(d)}>
                            Download
                          </button>
                        )}
                        <button className="btn btn-danger-outline btn-sm"
                                disabled={d.status === "processing"}
                                onClick={() => setToDelete(d)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedId && <DatasetDetails id={selectedId} onClose={() => setSelectedId(null)} />}

      {toDelete && (
        <ConfirmDialog title="Delete this dataset?" confirmText="Delete permanently"
                       busy={deleting} onConfirm={confirmDelete} onCancel={() => setToDelete(null)}>
          <p><b>{toDelete.name}</b> will be permanently removed, including its encrypted copy in
            the database. Analysts will lose access to it immediately. This cannot be undone.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
