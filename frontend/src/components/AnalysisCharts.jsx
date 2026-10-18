import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmtNum } from "../format.js";

const BLUE = "#2a78d6";    
const ORANGE = "#eb6834";  
const GRID = "#e6eaf0";
const axis = { tick: { fontSize: 12, fill: "#5f6f7e" }, stroke: "#c3ccd6" };
const short = (text) => (text.length > 16 ? text.slice(0, 15) + "…" : text);

function Card({ title, subtitle, children, foot }) {
  return (
    <section className="chart-card">
      <h3>{title}</h3>
      {subtitle && <p className="chart-sub">{subtitle}</p>}
      {children}
      {foot && <p className="chart-foot">{foot}</p>}
    </section>
  );
}

function Tip({ active, payload, build }) {
  if (!active || !payload || !payload.length) return null;
  const lines = build(payload[0].payload);
  return (
    <div className="tip">
      <b>{lines[0]}</b>
      {lines.slice(1).map((line, i) => <div key={i}>{line}</div>)}
    </div>
  );
}

const Empty = ({ children }) => <p className="chart-empty">{children}</p>;

export default function AnalysisCharts({ result }) {
  const name = result.measure.name;
  const scale = result.measure.masked ? " (masked scale)" : "";
  const tr = result.trend;
  const gr = result.groups;
  const cor = result.correlations;

  const grain = tr.available ? (tr.grain === "sequence" ? "record group" : tr.grain) : "";
  const changeText = tr.available
    ? `${tr.direction[0].toUpperCase() + tr.direction.slice(1)}: ${tr.change >= 0 ? "+" : ""}${fmtNum(tr.change)} `
      + `from first to last point${tr.change_pct != null ? ` (${tr.change_pct >= 0 ? "+" : ""}${tr.change_pct}%)` : ""}`
    : "";

  return (
    <div className="chart-grid">
      <Card title={`Trend: average ${name} per ${grain || "period"}`}
            subtitle={tr.available ? changeText : undefined}
            foot={tr.available
              ? (tr.grain === "sequence"
                ? "No date field found, so the records are grouped in file order."
                : `Dates from "${tr.source_column}".`)
                + (tr.hidden_periods ? ` ${tr.hidden_periods} period(s) with fewer than ${result.min_group_size} records are hidden.` : "")
                + (result.measure.masked ? " Values are on the masked scale; the shape and the changes are exact." : "")
              : undefined}>
        {!tr.available ? <Empty>{tr.reason}</Empty> : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={tr.points} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="label" {...axis} minTickGap={24} />
              <YAxis {...axis} domain={["auto", "auto"]} tickFormatter={fmtNum} width={70} />
              <Tooltip content={<Tip build={(p) => [p.label, `Average: ${fmtNum(p.mean)}`, `Records: ${p.count}`]} />} />
              <Line type="monotone" dataKey="mean" stroke={BLUE} strokeWidth={2}
                    dot={{ r: 3, stroke: "#fff", strokeWidth: 2, fill: BLUE }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card title={gr ? `${name} by ${gr.group_column}` : `${name} by group`}
            subtitle="Difference from the overall average (exact, even for masked fields)"
            foot={gr && gr.available && gr.hidden_groups
              ? `${gr.hidden_groups} group(s) with fewer than ${result.min_group_size} records are hidden.` : undefined}>
        {!gr ? <Empty>Choose a field under "Compare by" to compare groups.</Empty>
          : !gr.available ? <Empty>{gr.reason}</Empty> : (
            <>
              <ResponsiveContainer width="100%" height={Math.max(220, 70 + gr.groups.length * 36)}>
                <BarChart data={gr.groups} layout="vertical" margin={{ top: 4, right: 20, bottom: 4, left: 4 }}>
                  <CartesianGrid stroke={GRID} horizontal={false} />
                  <XAxis type="number" {...axis} tickFormatter={fmtNum} />
                  <YAxis type="category" dataKey="group" {...axis} width={110} tickFormatter={short} />
                  <ReferenceLine x={0} stroke="#8a97a5" />
                  <Tooltip content={<Tip build={(p) => [p.group, `Difference: ${p.diff_from_overall >= 0 ? "+" : ""}${fmtNum(p.diff_from_overall)}`,
                    `Average: ${fmtNum(p.mean)}${scale}`, `Records: ${p.count}`]} />} />
                  <Bar dataKey="diff_from_overall" radius={4} barSize={20}>
                    {gr.groups.map((g) => <Cell key={g.group} fill={g.diff_from_overall >= 0 ? BLUE : ORANGE} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="legend-line">
                <span><i className="swatch" style={{ background: BLUE }} />Above overall average</span>
                <span><i className="swatch" style={{ background: ORANGE }} />Below overall average</span>
              </div>
            </>
          )}
      </Card>

      <Card title={`Distribution of ${name}`}
            subtitle={`Number of records in each value range${scale}`}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={result.distribution} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="label" {...axis} angle={-30} textAnchor="end" height={78} interval="preserveStartEnd"
                   tick={{ fontSize: 11, fill: "#5f6f7e" }} />
            <YAxis {...axis} allowDecimals={false} width={44} />
            <Tooltip content={<Tip build={(p) => [`${p.label}`, `Records: ${p.count}`]} />} />
            <Bar dataKey="count" fill={BLUE} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title={`Correlation of ${name} with other fields`}
            subtitle="-1 = move in opposite directions, +1 = move together (exact, unaffected by masking)">
        {cor.length === 0 ? <Empty>No other numeric field has enough data to correlate.</Empty> : (
          <>
            <ResponsiveContainer width="100%" height={Math.max(220, 70 + cor.length * 36)}>
              <BarChart data={cor} layout="vertical" margin={{ top: 4, right: 20, bottom: 4, left: 4 }}>
                <CartesianGrid stroke={GRID} horizontal={false} />
                <XAxis type="number" {...axis} domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} />
                <YAxis type="category" dataKey="column" {...axis} width={110} tickFormatter={short} />
                <ReferenceLine x={0} stroke="#8a97a5" />
                <Tooltip content={<Tip build={(p) => [p.column, `Correlation: ${p.r}`, `Records compared: ${p.n}`]} />} />
                <Bar dataKey="r" radius={4} barSize={20}>
                  {cor.map((c) => <Cell key={c.column} fill={c.r >= 0 ? BLUE : ORANGE} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="legend-line">
              <span><i className="swatch" style={{ background: BLUE }} />Positive</span>
              <span><i className="swatch" style={{ background: ORANGE }} />Negative</span>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
