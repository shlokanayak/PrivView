export default function ProcessingSteps({ steps }) {
  const done = steps.filter((s) => s.status === "done").length;
  const failed = steps.some((s) => s.status === "failed");
  const percent = Math.round((done / steps.length) * 100);

  return (
    <div>
      <div className="progress" aria-label="Processing progress">
        <div className={failed ? "bar-failed" : ""} style={{ width: percent + "%" }} />
      </div>
      <ul className="steps">
        {steps.map((s) => (
          <li key={s.key} className={"step step-" + s.status}>
            <span className="step-icon">
              {s.status === "running" && <span className="spinner" />}
              {s.status === "done" && "✓"}
              {s.status === "failed" && "✕"}
            </span>
            <div>
              <div className="step-label">{s.label}</div>
              {s.detail && <div className="step-detail">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
