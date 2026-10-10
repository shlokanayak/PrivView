// ProtectionPanel.jsx - what protects this dataset (sanitisation, masking, encryption).
// Everything comes from the backend (the stored upload summary + the protected data).
import { useState } from "react";
import Pill from "./Pill.jsx";
import { fmtNum } from "../format.js";

function Row({ label, children }) {
  return (
    <div className="kv">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{children}</span>
    </div>
  );
}

const recorded = (v) => (v === null || v === undefined
  ? <span className="muted" title="Not recorded for datasets uploaded before this update">n/a</span>
  : fmtNum(v));

export default function ProtectionPanel({ protection, recordCount }) {
  const [open, setOpen] = useState(true);
  const s = protection.sanitisation;
  const m = protection.masking;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Protection status</h2>
        <div className="toolbar">
          <Pill tone="ok">Sanitisation: {s.status}</Pill>
          <Pill tone={m.fields_affected ? "ok" : "neutral"}>Masking: {m.status}</Pill>
          <Pill tone="ok">{protection.encryption}</Pill>
          <button className="btn btn-secondary btn-sm protect-toggle" onClick={() => setOpen(!open)}>
            {open ? "Hide details" : "Show details"}
          </button>
        </div>
      </div>

      {open && (
        <>
          <div className="summary-grid">
            <section className="summary-block">
              <h4>Sanitisation</h4>
              <Row label="Status"><Pill tone="ok">{s.status}</Pill></Row>
              <Row label="Cells checked">{recorded(s.cells_checked)}</Row>
              <Row label="XSS-like content neutralised">{recorded(s.xss_cells)} cells</Row>
              <Row label="Formula injection neutralised">{recorded(s.formula_cells)} cells</Row>
              <Row label="Hidden characters removed">{recorded(s.control_char_cells)} cells</Row>
              <Row label="Records affected">
                {recorded(s.records_affected)}{s.records_affected != null && ` of ${fmtNum(recordCount)}`}
              </Row>
              <Row label="Fields affected">
                {s.fields_affected == null ? recorded(null) : s.fields_affected === 0 ? "None" : (
                  (s.affected_field_names || []).map((f) => <span key={f} className="chip">{f}</span>)
                )}
              </Row>
            </section>

            <section className="summary-block">
              <h4>Privacy masking</h4>
              <Row label="Status">
                <Pill tone={m.fields_affected ? "ok" : "neutral"}>{m.status}</Pill>
              </Row>
              <Row label="Method">{m.method}</Row>
              <Row label="Records affected">{fmtNum(m.records_affected)} of {fmtNum(recordCount)}</Row>
              <Row label="Fields affected">{m.fields_affected}</Row>
              <Row label="Masked fields">
                {m.columns.length === 0 ? "None" : m.columns.map((c) => <span key={c} className="chip chip-masked">{c}</span>)}
              </Row>
            </section>

            <section className="summary-block">
              <h4>Categories of data protected</h4>
              {protection.categories.length === 0 ? (
                <p className="muted small">No sensitive numeric fields were detected in this dataset.</p>
              ) : protection.categories.map((c) => (
                <Row key={c.category} label={c.category}>
                  {c.columns.map((col) => <span key={col} className="chip chip-masked">{col}</span>)}
                </Row>
              ))}
            </section>

            <section className="summary-block">
              <h4>Encryption and storage</h4>
              <Row label="Encryption at rest"><Pill tone="ok">{protection.encryption}</Pill></Row>
              <Row label="Original upload kept">
                {protection.raw_file_retained ? <Pill tone="bad">Yes</Pill> : <Pill tone="ok">No</Pill>}
              </Row>
              <Row label="Analysis based on">Protected copy only</Row>
            </section>
          </div>

          <p className="muted small">
            {protection.withheld.length === 0
              ? "No direct identifier fields (names, contact details, government IDs) or record IDs were found."
              : "Withheld from this workspace and from reports: "
                + protection.withheld.map((w) => `${w.kind} (${w.count} field${w.count > 1 ? "s" : ""})`).join(", ")
                + ". Only aggregated results are shown."}
          </p>
        </>
      )}
    </div>
  );
}
