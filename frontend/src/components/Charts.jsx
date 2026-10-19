import { useId } from "react";
import { formatCurrency, formatNumber } from "../lib/format";

const PALETTE = [
  "#6366f1",
  "#22c55e",
  "#f59e0b",
  "#0ea5e9",
  "#ec4899",
  "#8b5cf6",
  "#14b8a6",
  "#f97316",
  "#64748b",
  "#ef4444",
];

export function LineChart({
  data = [],
  xKey = "order_month",
  yKey = "revenue",
  height = 230,
  color = "#6366f1",
  valueFormatter = formatCurrency,
}) {
  const gradientId = useId().replace(/:/g, "");
  const width = 660;
  const padding = { left: 54, right: 18, top: 18, bottom: 30 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  if (!data.length) {
    return (
      <div className="flex h-[180px] items-center justify-center text-xs text-slate-400">
        暂无趋势数据
      </div>
    );
  }

  const values = data.map((item) => Number(item[yKey]) || 0);
  const max = Math.max(...values, 1);
  const step = data.length > 1 ? innerWidth / (data.length - 1) : innerWidth;

  const points = data.map((item, index) => {
    const value = Number(item[yKey]) || 0;
    return {
      ...item,
      value,
      x: padding.left + index * step,
      y: padding.top + innerHeight - (value / max) * innerHeight,
    };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
    .join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${
    padding.top + innerHeight
  } L${points[0].x},${padding.top + innerHeight} Z`;

  const labelEvery = Math.max(1, Math.ceil(points.length / 7));

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label="销售趋势"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0.01" />
          </linearGradient>
        </defs>

        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + innerHeight * ratio;
          const value = max * (1 - ratio);
          return (
            <g key={ratio}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="#eef2f7"
                strokeDasharray="4 5"
              />
              <text
                x={padding.left - 9}
                y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="#94a3b8"
              >
                {value >= 10000 ? `${(value / 10000).toFixed(0)}万` : formatNumber(value)}
              </text>
            </g>
          );
        })}

        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {points.map((point, index) => (
          <g key={point[xKey] ?? index}>
            <circle cx={point.x} cy={point.y} r="4.5" fill="white" stroke={color} strokeWidth="2" />
            <circle cx={point.x} cy={point.y} r="13" fill="transparent">
              <title>
                {`${point[xKey]}：${valueFormatter(point.value)}`}
              </title>
            </circle>
            {index % labelEvery === 0 && (
              <text
                x={point.x}
                y={height - 8}
                textAnchor="middle"
                fontSize="10"
                fill="#94a3b8"
              >
                {String(point[xKey] || "").slice(-2)}月
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

export function BarList({
  items = [],
  labelKey = "category",
  valueKey = "revenue",
  maxItems = 8,
  color = "bg-indigo-500",
  valueFormatter = formatCurrency,
  suffix,
}) {
  const visible = items.slice(0, maxItems);
  if (!visible.length) {
    return (
      <div className="flex h-[120px] items-center justify-center text-xs text-slate-400">
        暂无数据
      </div>
    );
  }

  const max = Math.max(...visible.map((item) => Number(item[valueKey]) || 0), 1);

  return (
    <div className="space-y-3">
      {visible.map((item, index) => {
        const value = Number(item[valueKey]) || 0;
        return (
          <div key={`${item[labelKey]}-${index}`}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
              <span className="flex min-w-0 items-center gap-2">
                <span className="w-4 shrink-0 text-[10px] font-semibold text-slate-300">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="truncate font-medium text-slate-700">
                  {item[labelKey]}
                </span>
              </span>
              <span className="shrink-0 text-slate-500">
                {valueFormatter(value)}
                {suffix || ""}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${color} transition-all duration-500`}
                style={{ width: `${Math.max((value / max) * 100, 2)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DonutChart({
  items = [],
  labelKey = "label",
  valueKey = "value",
  size = 180,
  thickness = 22,
  centerLabel = "合计",
  centerValue,
  valueFormatter = formatCurrency,
}) {
  const total = items.reduce((sum, item) => sum + (Number(item[valueKey]) || 0), 0);

  if (!total) {
    return (
      <div className="flex h-[180px] items-center justify-center text-xs text-slate-400">
        暂无分布数据
      </div>
    );
  }

  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;

  const segments = items.reduce((accumulator, item, index) => {
    const value = Number(item[valueKey]) || 0;
    const dash = (value / total) * circumference;
    const start = accumulator.length
      ? accumulator[accumulator.length - 1].start +
        accumulator[accumulator.length - 1].dash
      : 0;
    accumulator.push({ item, index, value, dash, start });
    return accumulator;
  }, []);

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {segments.map(({ item, index, value, dash, start }) => (
              <circle
                key={`${item[labelKey]}-${index}`}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={PALETTE[index % PALETTE.length]}
                strokeWidth={thickness}
                strokeDasharray={`${Math.max(dash - 2, 0)} ${circumference - dash + 2}`}
                strokeDashoffset={-start}
                strokeLinecap="butt"
              >
                <title>{`${item[labelKey]}：${valueFormatter(value)}`}</title>
              </circle>
            ))}
          </g>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[10px] text-slate-400">{centerLabel}</span>
          <span className="mt-1 text-lg font-bold text-slate-800">
            {centerValue !== undefined ? centerValue : valueFormatter(total)}
          </span>
        </div>
      </div>

      <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-1">
        {items.slice(0, 6).map((item, index) => (
          <div key={`${item[labelKey]}-legend-${index}`} className="flex items-center gap-2 text-xs">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: PALETTE[index % PALETTE.length] }}
            />
            <span className="min-w-0 flex-1 truncate text-slate-600">{item[labelKey]}</span>
            <span className="shrink-0 font-medium text-slate-700">
              {((Number(item[valueKey]) / total) * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Sparkline({ data = [], valueKey = "revenue", color = "#6366f1", height = 40 }) {
  if (!data.length) return null;
  const width = 120;
  const values = data.map((item) => Number(item[valueKey]) || 0);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;

  const path = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-10 w-full" aria-hidden="true">
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}


