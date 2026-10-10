// SecuritySummary.jsx - the result of each protection layer, exactly as the
// backend reported it (summary JSON). Nothing here is hard-coded.
import Pill from "./Pill.jsx";
import { formatBytes } from "../format.js";

function Row({ label, children }) {
  return (
    <div className="kv">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{children}</span>
    </div>
  );
}

// "3 cells  [neutralised]"  or  "0 cells  [none found]"
function Found({ count }) {
  return (
    <>
      {count} {count === 1 ? "cell" : "cells"}{" "}
      {count > 0 ? <Pill tone="warn">neutralised</Pill> : <Pill tone="ok">none found</Pill>}
    </>
  );
}

export default function SecuritySummary({ summary }) {
  const v = summary.validation || {};
  const f = summary.filename;
  const s = summary.sanitisation;
  const m = summary.masking;
  const e = summary.encryption;
  const st = summary.storage;
  const pending = <Pill tone="wait">Pending</Pill>;

  return (
    <div className="summary-grid">
      <section className="summary-block">
        <h4>Validation</h4>
        <Row label="Result">
          {v.passed === true ? <Pill tone="ok">Passed</Pill>
            : v.passed === false ? <Pill tone="bad">Failed</Pill> : pending}
        </Row>
        {v.error && <p className="error small">{v.error}</p>}
        {v.size_bytes != null && <Row label="File size">{formatBytes(v.size_bytes)}</Row>}
        {summary.records != null && <Row label="Records processed">{summary.records}</Row>}
        <Row label="Filename">
          {!f ? pending : f.changed ? <Pill tone="warn">Sanitised</Pill> : <Pill tone="ok">Already safe</Pill>}
        </Row>
        {f && <Row label="Stored as"><code>{f.stored_as}</code></Row>}
      </section>

      <section className="summary-block">
        <h4>Content sanitisation</h4>
        {!s ? <Row label="Result">{pending}</Row> : (
          <>
            <Row label="Cells checked">{s.cells_checked}</Row>
            <Row label="XSS-like HTML / script"><Found count={s.xss_cells} /></Row>
            <Row label="Formula injection"><Found count={s.formula_cells} /></Row>
            <Row label="Hidden control characters">{s.control_char_cells}</Row>
            <Row label="Over-long cells cut">{s.long_cells}</Row>
            <Row label="Empty rows removed">{s.empty_rows_removed}</Row>
          </>
        )}
      </section>

      <section className="summary-block">
        <h4>Privacy masking</h4>
        {!m ? <Row label="Result">{pending}</Row> : (
          <>
            <Row label="Applied">
              {m.applied ? <Pill tone="ok">Yes</Pill> : <Pill tone="neutral">Not needed</Pill>}
            </Row>
            <Row label="Method">{m.method}</Row>
            <Row label="Masked columns">
              {m.columns.length === 0 ? "None" : m.columns.map((c) => (
                <span key={c} className="chip">{c}</span>
              ))}
            </Row>
            {m.ignored_requests.length > 0 && (
              <p className="muted small">Ignored your request: {m.ignored_requests.join("; ")}.</p>
            )}
            {m.identifier_columns.length > 0 && (
              <p className="warn-text small">
                Possible personal identifiers found ({m.identifier_columns.join(", ")}).
                Additive masking only protects numbers, so these columns are stored unmasked (but
                encrypted). They are withheld from analysts completely and appear only in the admin
                download.
              </p>
            )}
          </>
        )}
      </section>

      <section className="summary-block">
        <h4>Encryption and storage</h4>
        <Row label="Encrypted">
          {e?.encrypted ? <Pill tone="ok">Yes</Pill> : pending}
        </Row>
        {e && <Row label="Algorithm">{e.algorithm}</Row>}
        {e && <Row label="Encrypted size">{formatBytes(e.encrypted_size_bytes)}</Row>}
        <Row label="Stored in PostgreSQL">
          {st?.stored ? <Pill tone="ok">Yes</Pill> : pending}
        </Row>
        {st && (
          <Row label="Raw file kept">
            {st.raw_file_retained ? <Pill tone="bad">Yes</Pill> : <Pill tone="ok">No</Pill>}
          </Row>
        )}
      </section>
    </div>
  );
}
