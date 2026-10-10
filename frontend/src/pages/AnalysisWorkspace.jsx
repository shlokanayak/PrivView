import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile } from "../api.js";
import { fmtNum, formatDate } from "../format.js";
import Header from "../components/Header.jsx";
import Pill from "../components/Pill.jsx";
import ProtectionPanel from "../components/ProtectionPanel.jsx";
import AnalysisCharts from "../components/AnalysisCharts.jsx";
import { StatsTable, GroupTable } from "../components/StatsTable.jsx";
import "../analyst.css";

// Protected Analysis Workspace for ONE dataset.
// 1) GET /analyst/datasets/:id          -> metadata, protection status, filter options
// 2) GET /analyst/datasets/:id/analysis -> every number and chart, recalculated by the backend
//    each time a filter changes (from the decrypted protected copy, in memory).
export default function AnalysisWorkspace({ setUser }) {
  const { id } = useParams();
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState("");

  const [measure, setMeasure] = useState("");
  const [groupBy, setGroupBy] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState(null);

  useEffect(() => {
    setMeta(null);
    setMetaError("");
    setResult(null);
    api(`/analyst/datasets/${id}`).then((r) => {
      if (!r.ok) return setMetaError(r.data.error || "Could not open this dataset.");
      setMeta(r.data);
      setMeasure(r.data.options.default_measure || "");
      setGroupBy(r.data.options.default_group || "");
    });
  }, [id]);

  // the same query string drives the analysis AND the PDF report
  const query = useMemo(() => {
    const q = new URLSearchParams();
    if (measure) q.set("measure", measure);
    q.set("group_by", groupBy);
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    return q.toString();
  }, [measure, groupBy, dateFrom, dateTo]);

  useEffect(() => {
    if (!meta) return;
    let stale = false;
    setLoading(true);
    api(`/analyst/datasets/${id}/analysis?${query}`).then((r) => {
      if (stale) return;
      setLoading(false);
      if (r.ok) { setResult(r.data); setError(""); }
      else setError(r.data.error || "The analysis could not be calculated.");
    });
    return () => { stale = true; };
  }, [meta, query, id]);

  async function downloadReport() {
    setNote(null);
    setBusy("pdf");
    const res = await downloadFile(`/analyst/datasets/${id}/report.pdf?${query}`, "report.pdf");
    setBusy("");
    setNote(res.ok ? { type: "ok", text: `Downloaded ${res.name}` } : { type: "bad", text: res.error });
  }

  function resetFilters() {
    setDateFrom(""); setDateTo("");
    if (meta) { setMeasure(meta.options.default_measure || ""); setGroupBy(meta.options.default_group || ""); }
  }

  if (metaError) {
    return (
      <div className="admin">
        <Header setUser={setUser} role="analyst" />
        <main className="page">
          <div className="notice notice-bad">{metaError}</div>
          <Link className="btn btn-secondary" to="/analyst">Back to my datasets</Link>
        </main>
      </div>
    );
  }
  if (!meta) {
    return <div className="admin"><Header setUser={setUser} role="analyst" /><main className="page"><p className="muted">Opening dataset...</p></main></div>;
  }

  const opts = meta.options;
  const filtersActive = dateFrom || dateTo;
  const stats = result && result.stats;
  const tr = result && result.trend;

  return (
    <div className="admin">
      <Header setUser={setUser} role="analyst" />
      <main className="page page-wide">
        <div className="crumbs">
          <Link className="btn btn-secondary btn-sm" to="/analyst">{"←"} Back to my datasets</Link>
        </div>

        <div className="page-head">
          <div>
            <div className="title-row">
              <h1>{meta.name}</h1>
              <Pill tone="ok">Protected</Pill>
            </div>
            <p className="muted">
              {meta.description ? meta.description + " · " : ""}
              {fmtNum(meta.record_count)} records · {meta.column_count} fields · last updated{" "}
              {formatDate(meta.updated_at)} by {meta.updated_by}
            </p>
          </div>
          <div className="ws-actions">
            <button className="btn" disabled={busy === "pdf" || !result || result.suppressed || result.no_measures}
                    onClick={downloadReport}>
              {busy === "pdf" ? "Building report..." : "Download report (PDF)"}
            </button>
          </div>
        </div>
        {note && <div className={"notice notice-" + note.type}>{note.text}</div>}

        <ProtectionPanel protection={meta.protection} recordCount={meta.record_count} />

        <div className="panel">
          <div className="panel-head">
            <h2>Filters</h2>
            <button className="btn btn-secondary btn-sm" onClick={resetFilters} disabled={!filtersActive && measure === opts.default_measure && groupBy === (opts.default_group || "")}>
              Reset
            </button>
          </div>
          <div className="filters">
            <div className="filter">
              <label>Measure</label>
              <select value={measure} onChange={(e) => setMeasure(e.target.value)} disabled={opts.measures.length === 0}>
                {opts.measures.map((m) => (
                  <option key={m.name} value={m.name}>{m.name}{m.masked ? " (masked)" : ""}</option>
                ))}
              </select>
            </div>
            <div className="filter">
              <label>Compare by</label>
              <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                <option value="">None</option>
                {opts.group_columns.map((g) => <option key={g.name} value={g.name}>{g.name}</option>)}
              </select>
            </div>
            {opts.time && (
              <div className="filter">
                <label>Date range ({opts.time.column})</label>
                <div className="filter-pair">
                  <input type="date" value={dateFrom} min={opts.time.min} max={opts.time.max}
                         onChange={(e) => setDateFrom(e.target.value)} />
                  <span>to</span>
                  <input type="date" value={dateTo} min={opts.time.min} max={opts.time.max}
                         onChange={(e) => setDateTo(e.target.value)} />
                </div>
              </div>
            )}
          </div>
          {loading && <div className="loading-bar"><div /></div>}
        </div>

        {error && <div className="notice notice-bad">{error}</div>}
        {result && (result.suppressed || result.no_measures) && (
          <div className="notice notice-bad">{result.message}</div>
        )}

        {result && !result.suppressed && !result.no_measures && (
          <>
            <div className="kpis">
              <div className="kpi">
                <div className="kpi-label">Records analysed</div>
                <div className="kpi-value">{fmtNum(result.records_selected)}</div>
                <div className="kpi-note">of {fmtNum(result.records_total)} in the dataset</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Average {result.measure.name}</div>
                <div className="kpi-value">{fmtNum(stats.mean)}</div>
                <div className="kpi-note">{result.measure.masked ? "masked scale" : "actual values"}</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Standard deviation</div>
                <div className="kpi-value">{fmtNum(stats.std)}</div>
                <div className="kpi-note">exact spread of the values</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Trend</div>
                <div className="kpi-value">
                  {tr.available ? ({ rising: "↑ Rising", falling: "↓ Falling", flat: "→ Flat" })[tr.direction] : "-"}
                </div>
                <div className="kpi-note">
                  {tr.available ? `${tr.change >= 0 ? "+" : ""}${fmtNum(tr.change)} first to last` : "not enough data"}
                </div>
              </div>
              {result.coverage && (
                <div className="kpi">
                  <div className="kpi-label">Period covered</div>
                  <div className="kpi-value kpi-small">{result.coverage.from}</div>
                  <div className="kpi-note">to {result.coverage.to}</div>
                </div>
              )}
            </div>

            <AnalysisCharts result={result} />

            {result.groups && result.groups.available && (
              <GroupTable groups={result.groups} measure={result.measure} />
            )}
            <StatsTable rows={result.summary_stats} />
          </>
        )}

        <p className="muted small">
          You are looking at calculated results from the protected copy of this dataset. Original values were
          never stored, and results based on fewer than 3 records are hidden.
        </p>
      </main>
    </div>
  );
}
