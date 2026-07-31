import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

// ── colour palette ──────────────────────────────────────────────────────────
const CAT_COLORS = {
  code_quality: { main: "#a78bfa", light: "rgba(167,139,250,0.15)", label: "Code Quality" },
  process:      { main: "#34d399", light: "rgba(52,211,153,0.15)",  label: "Process" },
  devops:       { main: "#38bdf8", light: "rgba(56,189,248,0.15)",  label: "DevOps" },
  unknown:      { main: "#94a3b8", light: "rgba(148,163,184,0.15)", label: "Unknown" },
};
const ROLE_COLORS = [
  "#a78bfa","#38bdf8","#34d399","#fbbf24","#f472b6","#fb923c","#94a3b8",
];

// ── tiny helpers ─────────────────────────────────────────────────────────────
const pct   = (v) => `${Math.round(v)}%`;
const round1 = (v) => Math.round(v * 10) / 10;

// ── KPI card ─────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: "var(--surface)",
      border: `1px solid ${accent || "var(--border)"}`,
      borderRadius: 14,
      padding: "18px 22px",
      display: "flex",
      flexDirection: "column",
      gap: 4,
      boxShadow: accent ? `0 0 16px ${accent}28` : "none",
      flex: "1 1 160px",
      minWidth: 150,
    }}>
      <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontSize: 28, fontWeight: 800, color: accent || "var(--text-primary)", lineHeight: 1.1 }}>{value}</span>
      {sub && <span style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{sub}</span>}
    </div>
  );
}

// ── SVG line chart for daily trends ──────────────────────────────────────────
function TrendLineChart({ data }) {
  if (!data || data.length === 0) return (
    <div style={{ color: "var(--text-muted)", textAlign: "center", padding: "40px 0" }}>No trend data available</div>
  );

  const W = 560, H = 180, PAD = { t: 20, r: 16, b: 40, l: 44 };
  const maxTotal = Math.max(...data.map(d => d.total), 1);
  const maxRate  = 100;

  const xScale = (i) => PAD.l + (i / (data.length - 1 || 1)) * (W - PAD.l - PAD.r);
  const yScaleTotal = (v) => H - PAD.b - (v / maxTotal) * (H - PAD.t - PAD.b);
  const yScaleRate  = (v) => H - PAD.b - (v / maxRate)  * (H - PAD.t - PAD.b);

  const totalPath = data.map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScaleTotal(d.total)}`).join(" ");
  const ratePath  = data.map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScaleRate(d.helpfulness_rate)}`).join(" ");

  // fill under rate line
  const rateArea = `${ratePath} L ${xScale(data.length - 1)} ${H - PAD.b} L ${xScale(0)} ${H - PAD.b} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", maxWidth: W, display: "block" }}>
      {/* grid lines */}
      {[0, 25, 50, 75, 100].map(v => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={yScaleRate(v)} y2={yScaleRate(v)}
                stroke="#ffffff10" strokeWidth={1} strokeDasharray="4 4" />
          <text x={PAD.l - 6} y={yScaleRate(v) + 4} fill="#94a3b8" fontSize={9} textAnchor="end">{v}%</text>
        </g>
      ))}

      {/* rate area fill */}
      <path d={rateArea} fill="rgba(52,211,153,0.08)" />

      {/* total count bars (mini) */}
      {data.map((d, i) => (
        <rect key={i}
          x={xScale(i) - 3} y={yScaleTotal(d.total)}
          width={6} height={H - PAD.b - yScaleTotal(d.total)}
          fill="rgba(167,139,250,0.25)" rx={2}
        />
      ))}

      {/* rate line */}
      <path d={ratePath} fill="none" stroke="#34d399" strokeWidth={2.5} strokeLinejoin="round" />

      {/* total line */}
      <path d={totalPath} fill="none" stroke="#a78bfa" strokeWidth={1.5} strokeLinejoin="round" strokeDasharray="5 3" />

      {/* dots + labels on rate */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={xScale(i)} cy={yScaleRate(d.helpfulness_rate)} r={3.5} fill="#34d399" />
          <text x={xScale(i)} y={H - PAD.b + 14} fill="#94a3b8" fontSize={9} textAnchor="middle">
            {d.date.slice(5)} {/* MM-DD */}
          </text>
        </g>
      ))}

      {/* legend */}
      <g transform={`translate(${PAD.l}, ${PAD.t - 10})`}>
        <circle cx={0} cy={0} r={4} fill="#34d399" />
        <text x={8} y={4} fill="#94a3b8" fontSize={9}>Helpfulness %</text>
        <rect x={110} y={-4} width={12} height={4} fill="rgba(167,139,250,0.4)" rx={1} />
        <text x={126} y={4} fill="#94a3b8" fontSize={9}>Daily count</text>
      </g>
    </svg>
  );
}

// ── Horizontal bar chart ──────────────────────────────────────────────────────
function HBarChart({ data, colorFn, labelKey, valueKey = "helpfulness_rate", maxVal = 100 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {data.map((d, i) => {
        const pctVal = Math.min(d[valueKey], maxVal);
        const color  = colorFn ? colorFn(d, i) : "#a78bfa";
        return (
          <div key={i}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600 }}>{d[labelKey]}</span>
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                {round1(d[valueKey])}{valueKey === "helpfulness_rate" ? "%" : ""}
                <span style={{ marginLeft: 8, color: "var(--text-muted)", fontWeight: 400 }}>({d.total} reviews)</span>
              </span>
            </div>
            <div style={{ background: "var(--surface-raised)", borderRadius: 6, height: 10, overflow: "hidden" }}>
              <div style={{
                width: `${(pctVal / maxVal) * 100}%`,
                height: "100%",
                background: `linear-gradient(90deg, ${color}, ${color}cc)`,
                borderRadius: 6,
                transition: "width 0.6s ease",
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Metric table ──────────────────────────────────────────────────────────────
function MetricTable({ data }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["Metric", "Category", "Reviews", "Helpful %", "Avg Score", "Avg Deviation"].map(h => (
              <th key={h} style={{
                textAlign: "left", padding: "8px 12px",
                borderBottom: "1px solid var(--border)",
                color: "var(--text-muted)", fontWeight: 600,
                textTransform: "uppercase", letterSpacing: 0.5, fontSize: 10,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((m, i) => {
            const catColor = (CAT_COLORS[m.category] || CAT_COLORS.unknown).main;
            return (
              <tr key={i} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                <td style={{ padding: "9px 12px", color: "var(--text-primary)", fontWeight: 600 }}>{m.metric_name}</td>
                <td style={{ padding: "9px 12px" }}>
                  <span style={{
                    background: (CAT_COLORS[m.category] || CAT_COLORS.unknown).light,
                    color: catColor, borderRadius: 20,
                    padding: "2px 10px", fontSize: 11, fontWeight: 600,
                  }}>{(CAT_COLORS[m.category] || CAT_COLORS.unknown).label}</span>
                </td>
                <td style={{ padding: "9px 12px", color: "var(--text-secondary)" }}>{m.total}</td>
                <td style={{ padding: "9px 12px" }}>
                  <span style={{
                    color: m.helpfulness_rate >= 60 ? "#34d399" : m.helpfulness_rate >= 40 ? "#fbbf24" : "#f87171",
                    fontWeight: 700,
                  }}>{m.helpfulness_rate}%</span>
                </td>
                <td style={{ padding: "9px 12px", color: "var(--text-secondary)" }}>{m.avg_priority_score}</td>
                <td style={{ padding: "9px 12px", color: "var(--text-secondary)" }}>{round1(m.avg_deviation * 100)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Project comparison bars ───────────────────────────────────────────────────
function ProjectBars({ data, projects }) {
  const nameOf = (pid) => {
    const p = projects.find(p => p.id === pid);
    return p ? p.name : `Project ${pid}`;
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {data.map((d, i) => (
        <div key={i}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600 }}>{nameOf(d.project_id)}</span>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{d.helpfulness_rate}% helpful <span style={{ opacity: 0.6 }}>({d.total})</span></span>
          </div>
          <div style={{ display: "flex", gap: 2, height: 12 }}>
            <div style={{
              width: `${d.helpfulness_rate}%`,
              background: "linear-gradient(90deg, #34d399, #059669)",
              borderRadius: "4px 0 0 4px",
            }} />
            <div style={{
              width: `${100 - d.helpfulness_rate}%`,
              background: "rgba(248,113,113,0.25)",
              borderRadius: "0 4px 4px 0",
            }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────
function FilterBar({ filters, value, onChange }) {
  const sel = {
    background: "var(--surface-raised)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text-primary)",
    padding: "6px 10px",
    fontSize: 12,
    cursor: "pointer",
  };
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
      <span style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>Filter:</span>
      <select style={sel} value={value.project_id ?? ""} onChange={e => onChange({ ...value, project_id: e.target.value ? parseInt(e.target.value) : null })}>
        <option value="">All Projects</option>
        {(filters.projects || []).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select style={sel} value={value.category ?? ""} onChange={e => onChange({ ...value, category: e.target.value || null })}>
        <option value="">All Categories</option>
        {(filters.categories || []).map(c => <option key={c} value={c}>{(CAT_COLORS[c] || {}).label || c}</option>)}
      </select>
      <select style={sel} value={value.userRole ?? ""} onChange={e => onChange({ ...value, userRole: e.target.value || null })}>
        <option value="">All Roles</option>
        {(filters.roles || []).map(r => <option key={r} value={r}>{r}</option>)}
      </select>
    </div>
  );
}

// ── Section card wrapper ──────────────────────────────────────────────────────
function Section({ title, children, accent }) {
  return (
    <div style={{
      background: "var(--surface)",
      border: `1px solid ${accent || "var(--border)"}`,
      borderRadius: 16,
      padding: "20px 24px",
      display: "flex",
      flexDirection: "column",
      gap: 16,
    }}>
      <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--text-primary)", letterSpacing: 0.3 }}>{title}</h3>
      {children}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function FeedbackAnalytics() {
  const [summary, setSummary]   = useState(null);
  const [filters, setFilters]   = useState({ projects: [], categories: [], roles: [] });
  const [active, setActive]     = useState({ project_id: null, category: null, userRole: null });
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  // Load filter options once
  useEffect(() => {
    api.getFeedbackFilters()
       .then(setFilters)
       .catch(err => console.error("Filter load error:", err));
  }, []);

  // Reload summary whenever active filters change
  const loadSummary = useCallback(() => {
    setLoading(true);
    setError(null);
    api.getFeedbackSummary({
      projectId: active.project_id,
      category:  active.category,
      userRole:  active.userRole,
    })
    .then(data => { setSummary(data); setLoading(false); })
    .catch(err => { setError(err.message); setLoading(false); });
  }, [active]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", flexDirection: "column", gap: 16 }}>
      <div style={{ width: 40, height: 40, border: "3px solid var(--border)", borderTopColor: "#a78bfa", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
      <span style={{ color: "var(--text-muted)" }}>Loading analytics…</span>
    </div>
  );

  if (error) return (
    <div style={{ padding: 32, color: "#f87171" }}>
      <strong>Error loading analytics:</strong> {error}
    </div>
  );

  if (!summary || summary.total_feedback === 0) return (
    <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)" }}>
      <div style={{ fontSize: 40, marginBottom: 16 }}>📊</div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No feedback data yet</div>
      <div style={{ fontSize: 13 }}>Run the <code>seed_feedback_csv.py</code> script to import the demo dataset.</div>
    </div>
  );

  const helpPct = summary.overall_helpfulness_rate;
  const helpColor = helpPct >= 65 ? "#34d399" : helpPct >= 45 ? "#fbbf24" : "#f87171";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, padding: "0 4px" }}>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "var(--text-primary)" }}>
            Feedback Analytics
          </h2>
          {summary.date_range_start && (
            <span style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3, display: "block" }}>
              {summary.date_range_start} → {summary.date_range_end}
            </span>
          )}
        </div>
        <FilterBar filters={filters} value={active} onChange={setActive} />
      </div>

      {/* KPI Strip */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <KpiCard label="Total Feedback" value={summary.total_feedback.toLocaleString()} sub="reviews submitted" accent="#a78bfa" />
        <KpiCard label="Helpfulness Rate" value={`${helpPct}%`} sub={`${summary.helpful_count} helpful / ${summary.not_helpful_count} not`} accent={helpColor} />
        <KpiCard label="Avg Priority Score" value={round1(summary.avg_priority_score)} sub="across all reviews" />
        <KpiCard label="Critical Reviews" value={summary.critical_feedback_count} sub="score ≥ 60" accent="#f87171" />
        <KpiCard label="Most Active Role" value={summary.most_active_role || "—"} sub="by review count" accent="#38bdf8" />
      </div>

      {/* Daily Trend + By Category (side by side) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Section title="📈 Helpfulness Trend (Daily)">
          <TrendLineChart data={summary.daily_trends} />
        </Section>
        <Section title="🏷️ By Category">
          <HBarChart
            data={summary.by_category}
            labelKey="category"
            valueKey="helpfulness_rate"
            colorFn={(d) => (CAT_COLORS[d.category] || CAT_COLORS.unknown).main}
          />
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 4 }}>
            {summary.by_category.map(c => (
              <div key={c.category} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-muted)" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: (CAT_COLORS[c.category] || CAT_COLORS.unknown).main, display: "inline-block" }} />
                {(CAT_COLORS[c.category] || CAT_COLORS.unknown).label}: {c.total} reviews, avg score {c.avg_priority_score}
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* By Role + Project Comparison (side by side) */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Section title="👥 By User Role">
          <HBarChart
            data={summary.by_role}
            labelKey="user_role"
            valueKey="helpfulness_rate"
            colorFn={(_, i) => ROLE_COLORS[i % ROLE_COLORS.length]}
          />
        </Section>
        <Section title="🏗️ Project Comparison">
          <ProjectBars data={summary.by_project} projects={filters.projects} />
          <div style={{ display: "flex", gap: 16, marginTop: 4, fontSize: 11, color: "var(--text-muted)" }}>
            <span><span style={{ color: "#34d399" }}>■</span> Helpful</span>
            <span><span style={{ color: "#f87171" }}>■</span> Not helpful</span>
          </div>
        </Section>
      </div>

      {/* Metric breakdown table */}
      <Section title="📋 Metrics Breakdown (ranked by avg priority score)">
        <MetricTable data={summary.by_metric} />
      </Section>

    </div>
  );
}
