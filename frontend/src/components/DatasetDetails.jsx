import { useEffect, useState } from "react";
import { api, downloadFile } from "../api.js";
import useDataset from "../useDataset.js";
import { formatDate } from "../format.js";
import Pill from "./Pill.jsx";
import ProcessingSteps from "./ProcessingSteps.jsx";
import SecuritySummary from "./SecuritySummary.jsx";
import AccessPanel from "./AccessPanel.jsx";

export default function DatasetDetails({ id, onClose }) {
  const { data, error } = useDataset(id);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    setPreview(null);
    setPreviewError("");
  }, [id]);

  async function loadPreview() {
    setPreviewError("");
    const res = await api(`/admin/datasets/${id}/preview`);
    if (res.ok) setPreview(res.data);
    else setPreviewError(res.data.error || "Could not load the preview.");
  }

  async function download() {
    setPreviewError("");
    const res = await downloadFile(`/admin/datasets/${id}/download`, "protected_dataset.csv");
    if (!res.ok) setPreviewError(res.error);
  }

  if (error) return <div className="panel"><p className="error">{error}</p></div>;
  if (!data) return <div className="panel"><p className="muted">Loading details...</p></div>;

  const tone = { processing: "wait", protected: "ok", failed: "bad" }[data.status];

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>{data.name}</h2>
          <Pill tone={tone}>
            {data.status === "protected" ? "Protected & encrypted"
              : data.status === "failed" ? "Failed" : "Processing"}
          </Pill>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={onClose}>Close</button>
      </div>

      <div className="meta-grid">
        <div><span className="meta-label">File</span><code>{data.filename}</code></div>
        <div><span className="meta-label">Type</span>{data.file_type.toUpperCase()}</div>
        <div><span className="meta-label">Uploaded by</span>{data.uploaded_by}</div>
        <div><span className="meta-label">Uploaded</span>{formatDate(data.created_at, true)}</div>
        <div><span className="meta-label">Records</span>{data.record_count}</div>
        <div><span className="meta-label">Columns</span>{data.column_count}</div>
      </div>
      {data.description && <p className="description">{data.description}</p>}

      <h3 className="section-title">Processing</h3>
      <ProcessingSteps steps={data.summary.steps} />

      <h3 className="section-title">Security summary</h3>
      <SecuritySummary summary={data.summary} />

      {data.summary.columns && (
        <>
          <h3 className="section-title">Columns</h3>
          <div className="chips">
            {data.summary.columns.map((c) => (
              <span key={c.name} className={c.masked ? "chip chip-masked" : "chip"}>
                {c.name} <small>{c.type}{c.masked ? " · masked" : ""}</small>
              </span>
            ))}
          </div>
        </>
      )}

      {data.status === "protected" && (
        <>
          <AccessPanel datasetId={id} />
          <h3 className="section-title">Protected data preview</h3>
          <p className="muted small">
            Decrypted in memory by the server. Values are the masked ones - the original
            values are not stored anywhere. Opening a preview is written to the activity log.
          </p>
          <div className="toolbar">
            {!preview && (
              <button className="btn btn-secondary" onClick={loadPreview}>
                Show first 10 rows
              </button>
            )}
            <button className="btn btn-secondary" onClick={download}>
              Download protected dataset (CSV)
            </button>
          </div>
          {previewError && <p className="error">{previewError}</p>}
          {preview && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>{preview.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i}>{row.map((cell, j) => <td key={j}>{cell === null ? "" : String(cell)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
