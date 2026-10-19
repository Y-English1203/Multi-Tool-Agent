function inlineNodes(text, keyPrefix) {
  const parts = String(text).split(
    /(\*\*[^*]+\*\*|`[^`]+`|\[第\s*\d+\s*页\])/g
  );

  return parts.filter(Boolean).map((part, index) => {
    const key = `${keyPrefix}-${index}`;

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    if (/^\[第\s*\d+\s*页\]$/.test(part)) {
      return (
        <span key={key} className="citation">
          {part.replace(/[\[\]]/g, "")}
        </span>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

/**
 * 轻量 Markdown 渲染：支持标题、无序/有序列表、加粗、行内代码和页码引用。
 * 不解析 HTML，避免模型输出注入。
 */
export default function Markdown({ text = "", className = "" }) {
  const lines = String(text || "").split("\n");
  const blocks = [];
  let list = null;

  const flushList = () => {
    if (list) {
      const Tag = list.type === "ol" ? "ol" : "ul";
      blocks.push(
        <Tag key={`list-${blocks.length}`}>
          {list.items.map((item, index) => (
            <li key={`li-${index}`}>{inlineNodes(item, `li-${index}`)}</li>
          ))}
        </Tag>
      );
      list = null;
    }
  };

  lines.forEach((rawLine, index) => {
    const line = rawLine.replace(/\s+$/, "");
    const unordered = line.match(/^\s*[-*•]\s+(.*)$/);
    const ordered = line.match(/^\s*(\d+)[.、)]\s+(.*)$/);
    const heading = line.match(/^\s*#{2,4}\s+(.*)$/);

    if (unordered) {
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(unordered[1]);
      return;
    }

    if (ordered) {
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(ordered[2]);
      return;
    }

    flushList();

    if (!line.trim()) {
      return;
    }

    if (heading) {
      blocks.push(
        <p key={`h-${index}`} className="mt-2 font-semibold text-slate-900">
          {inlineNodes(heading[1], `h-${index}`)}
        </p>
      );
      return;
    }

    blocks.push(
      <p key={`p-${index}`}>{inlineNodes(line, `p-${index}`)}</p>
    );
  });

  flushList();

  return <div className={`prose-chat text-sm leading-7 text-slate-700 ${className}`}>{blocks}</div>;
}
