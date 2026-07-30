export default function MetricCard({ metric, history = [], onClick }) {
  const renderSparkline = () => {
    if (history.length <= 1) {
      return <div className="sparkline-container" style={{ display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "10px" }}>No history yet</div>;
    }
    const values = history.map((h) => h.value);
    const maxVal = Math.max(...values);
    const minVal = Math.min(...values);
    const valRange = maxVal - minVal || 1;

    const width = 120;
    const height = 30;
    const paddingX = 5;
    const paddingY = 5;

    const getX = (index) => {
      return paddingX + (index * (width - 2 * paddingX)) / (history.length - 1);
    };

    const getY = (val) => {
      return height - paddingY - ((val - minVal) / valRange) * (height - 2 * paddingY);
    };

    const pathD = history.reduce((acc, h, i) => {
      const x = getX(i);
      const y = getY(h.value);
      return acc + `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }, "");

    const lastIndex = history.length - 1;
    const lastX = getX(lastIndex);
    const lastY = getY(history[lastIndex].value);

    return (
      <svg className="sparkline-container" viewBox={`0 0 ${width} ${height}`}>
        <path className="sparkline-glow" d={pathD} />
        <path className="sparkline-path" d={pathD} />
        <circle className="sparkline-dot" cx={lastX} cy={lastY} r="2.5" />
      </svg>
    );
  };

  return (
    <div className="metric-card" onClick={onClick} role="button" tabIndex={0}>
      <div className="metric-name">{metric.display_name}</div>
      <div className="metric-value">
        {metric.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        <span className="metric-unit">{metric.unit}</span>
      </div>
      
      {renderSparkline()}

      <div className="metric-meta">
        Updated {new Date(metric.recorded_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })}
      </div>
    </div>
  );
}
