// StatsTable.jsx - summary statistics + group comparison tables (all from the backend).
import { fmtNum } from "../format.js";
import Pill from "./Pill.jsx";

// Level figures (mean, median, min ...) of a masked field are on the masked scale.
const LEVEL = "masked-val";

export function StatsTable({ rows }) {
  return (
    <div className="panel">
      <div className="panel-head"><h2>Summary statistics</h2></div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Field</th><th className="num">Records</th><th className="num">Mean</th>
              <th className="num">Median</th><th className="num">Std. deviation</th>
              <th className="num">Min</th><th className="num">25%</th>
              <th className="num">75%</th><th className="num">Max</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const level = r.masked ? LEVEL : "";
              return (
                <tr key={r.column}>
                  <td>
                    <span className="cell-title">{r.column}</span>{" "}
                    {r.masked && <Pill tone="info">masked scale</Pill>}
                  </td>
                  <td className="num">{fmtNum(r.n)}</td>
                  <td className={"num " + level}>{fmtNum(r.mean)}</td>
                  <td className={"num " + level}>{fmtNum(r.median)}</td>
                  <td className="num">{fmtNum(r.std)}</td>
                  <td className={"num " + level}>{fmtNum(r.min)}</td>
                  <td className={"num " + level}>{fmtNum(r.q1)}</td>
                  <td className={"num " + level}>{fmtNum(r.q3)}</td>
                  <td className={"num " + level}>{fmtNum(r.max)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Italic figures belong to masked fields: the real values were shifted by a secret constant before
        storage, so levels are on the masked scale. Standard deviation is exact.
      </p>
    </div>
  );
}

export function GroupTable({ groups, measure }) {
  return (
    <div className="panel">
      <div className="panel-head"><h2>{measure.name} by {groups.group_column}</h2></div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{groups.group_column}</th><th className="num">Records</th>
              <th className="num">Mean</th><th className="num">Median</th>
              <th className="num">Std. deviation</th><th className="num">Difference from overall</th>
            </tr>
          </thead>
          <tbody>
            {groups.groups.map((g) => (
              <tr key={g.group}>
                <td className="cell-title">{g.group}</td>
                <td className="num">{fmtNum(g.count)}</td>
                <td className={"num " + (measure.masked ? LEVEL : "")}>{fmtNum(g.mean)}</td>
                <td className={"num " + (measure.masked ? LEVEL : "")}>{fmtNum(g.median)}</td>
                <td className="num">{fmtNum(g.std)}</td>
                <td className="num">{g.diff_from_overall >= 0 ? "+" : ""}{fmtNum(g.diff_from_overall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
