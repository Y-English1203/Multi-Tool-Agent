import { formatNumber } from "../lib/format";

function renderCell(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? formatNumber(value) : formatNumber(value, 2);
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

export default function DataTable({
  columns = [],
  rows = [],
  maxHeight = "360px",
  emptyText = "暂无数据",
  footer = true,
}) {
  if (!rows.length) {
    return (
      <div className="flex h-24 items-center justify-center text-xs text-slate-400">
        {emptyText}
      </div>
    );
  }

  const normalized = columns.map((column, index) =>
    typeof column === "string"
      ? { key: column, label: column, index }
      : { ...column, index: column.index ?? index }
  );

  function valueFor(row, column) {
    if (Array.isArray(row)) return row[column.index];
    return row[column.key];
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200">
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full min-w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-slate-50">
            <tr>
              {normalized.map((column) => (
                <th
                  key={column.key}
                  className="whitespace-nowrap border-b border-slate-200 px-3 py-2.5 font-semibold text-slate-600"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-slate-100 last:border-0 hover:bg-indigo-50/30"
              >
                {normalized.map((column) => (
                  <td
                    key={`${rowIndex}-${column.key}`}
                    className="whitespace-nowrap px-3 py-2.5 text-slate-600"
                  >
                    {renderCell(valueFor(row, column))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer && (
        <div className="border-t border-slate-100 bg-slate-50/60 px-3 py-1.5 text-[10px] text-slate-400">
          共 {rows.length} 行
        </div>
      )}
    </div>
  );
}
