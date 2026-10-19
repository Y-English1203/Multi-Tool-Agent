export function formatNumber(value, digits = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCurrency(value, compact = false) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (compact && Math.abs(number) >= 10000) {
    return `¥${(number / 10000).toFixed(1)}万`;
  }
  return `¥${number.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPercent(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toFixed(digits)}%`;
}

export function formatDate(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 16);
}

export function timeAgo(value) {
  if (!value) return "";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return String(value);
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`;
  return date.toLocaleDateString("zh-CN");
}

export function truncate(text, length = 80) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

export function normalizeTool(tool) {
  const value = String(tool || "").toLowerCase();
  if (value.includes("rag") || value.includes("retriev")) return "rag";
  if (value.includes("sql") || value.includes("data")) return "sql";
  if (value.includes("ticket")) return "ticket";
  if (value.includes("supervisor")) return "supervisor";
  return "";
}

export function normalizeSources(sources) {
  if (!Array.isArray(sources)) return [];
  return sources
    .map((source) => {
      if (typeof source === "number" || typeof source === "string") {
        return { page: Number(source) || null, source: "", content: "", score: 0 };
      }
      return {
        page: Number(source?.page) || null,
        source: source?.source || "",
        content: source?.content || "",
        score: Number(source?.score) || 0,
      };
    })
    .filter((source) => source.page || source.content);
}

export function toolLabel(tool) {
  return (
    {
      rag: "RAG 文档问答",
      sql: "Text-to-SQL",
      ticket: "工单服务",
      supervisor: "Supervisor",
    }[normalizeTool(tool)] || "智能助手"
  );
}

export const STATUS_STYLES = {
  待处理: "border-amber-200 bg-amber-50 text-amber-700",
  处理中: "border-blue-200 bg-blue-50 text-blue-700",
  已解决: "border-emerald-200 bg-emerald-50 text-emerald-700",
  已关闭: "border-slate-200 bg-slate-100 text-slate-600",
  已完成: "border-emerald-200 bg-emerald-50 text-emerald-700",
  已发货: "border-blue-200 bg-blue-50 text-blue-700",
  待付款: "border-amber-200 bg-amber-50 text-amber-700",
  已取消: "border-slate-200 bg-slate-100 text-slate-500",
  退款中: "border-rose-200 bg-rose-50 text-rose-700",
};

export const PRIORITY_STYLES = {
  高: "border-rose-200 bg-rose-50 text-rose-700",
  中: "border-amber-200 bg-amber-50 text-amber-700",
  低: "border-slate-200 bg-slate-100 text-slate-600",
};
