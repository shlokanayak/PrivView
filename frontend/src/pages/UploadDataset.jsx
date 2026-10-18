import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDataset from "../useDataset.js";
import Header from "../components/Header.jsx";
import ProcessingSteps from "../components/ProcessingSteps.jsx";
import SecuritySummary from "../components/SecuritySummary.jsx";

const MAX_MB = 5;

export default function UploadDataset({ setUser }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [maskColumns, setMaskColumns] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [datasetId, setDatasetId] = useState(null);
  const { data, error: loadError } = useDataset(datasetId);
  const navigate = useNavigate();

  const finished = data && data.status !== "processing";

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!name.trim()) return setError("Enter a dataset name.");
    if (!file) return setError("Choose a CSV or XLSX file.");
    if (!/\.(csv|xlsx)$/i.test(file.name)) return setError("Only .csv and .xlsx files are allowed.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`The file is larger than ${MAX_MB} MB.`);

    const form = new FormData();
    form.append("name", name);
    form.append("description", description);
    form.append("mask_columns", maskColumns);
    form.append("file", file);

    setSending(true);
    const res = await api("/admin/datasets", "POST", form);
    setSending(false);
    if (res.ok) setDatasetId(res.data.id);
    else setError(res.data.error || "Upload failed.");
  }

  function reset() {
    setDatasetId(null);
    setName("");
    setDescription("");
    setMaskColumns("");
    setFile(null);
    setError("");
  }

  return (
    <div className="admin">
      <Header setUser={setUser} />
      <main className="page page-narrow">
        <div className="page-head">
          <div>
            <h1>Upload dataset</h1>
            <p className="muted">The file is checked, cleaned, masked and encrypted before it is stored.</p>
          </div>
          <Link className="btn btn-secondary" to="/admin">Back to dashboard</Link>
        </div>

        {!datasetId && (
          <form className="panel" onSubmit={handleSubmit}>
            <label>Dataset name</label>
            <input value={name} maxLength={100} onChange={(e) => setName(e.target.value)}
                   placeholder="e.g. Patient vitals Q3" />

            <label>Description <span className="muted">(optional)</span></label>
            <textarea value={description} maxLength={500} rows={2}
                      onChange={(e) => setDescription(e.target.value)} />

            <label>File (CSV or XLSX, max {MAX_MB} MB)</label>
            <input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files[0] || null)} />
            <p className="muted small">
              The first row must contain the column names. Only the first sheet of an Excel file is read.
            </p>

            <label>Extra columns to mask <span className="muted">(optional, comma separated)</span></label>
            <input value={maskColumns} onChange={(e) => setMaskColumns(e.target.value)}
                   placeholder="e.g. lab_score, deductible" />
            <p className="muted small">
              Financial and medical numeric columns (salary, balance, glucose, ...) are detected
              automatically. Use this box for any other numeric column that must be masked.
            </p>

            {error && <p className="error">{error}</p>}
            <button className="btn" disabled={sending}>{sending ? "Uploading..." : "Upload and protect"}</button>
          </form>
        )}

        {datasetId && (
          <div className="panel">
            <div className="panel-head">
              <h2>{data ? data.name : "Processing..."}</h2>
            </div>
            {loadError && <p className="error">{loadError}</p>}

            {data && finished && (
              <div className={"notice " + (data.status === "protected" ? "notice-ok" : "notice-bad")}>
                {data.status === "protected"
                  ? "Dataset protected and stored. Only the encrypted version exists in the database."
                  : `Upload failed. ${data.summary.validation.error || "See the failed step below."}`}
              </div>
            )}

            {data && <ProcessingSteps steps={data.summary.steps} />}

            {data && (
              <>
                <h3 className="section-title">Processing result</h3>
                <SecuritySummary summary={data.summary} />
              </>
            )}

            {finished && (
              <div className="form-actions">
                <button className="btn" onClick={() => navigate("/admin")}>View in dashboard</button>
                <button className="btn btn-secondary" onClick={reset}>Upload another</button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
