import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Circle,
  Database,
  LoaderCircle,
  Sparkles,
  Ticket,
  Workflow,
} from "lucide-react";
import { normalizeTool } from "../lib/format";

const AGENTS = [
  {
    key: "supervisor",
    name: "Supervisor",
    desc: "意图识别与任务调度",
    icon: Workflow,
  },
  { key: "rag", name: "RAG Agent", desc: "混合检索与文档问答", icon: BookOpen },
  { key: "sql", name: "SQL Agent", desc: "Text-to-SQL 数据分析", icon: Database },
  { key: "ticket", name: "Ticket Agent", desc: "工单创建与状态查询", icon: Ticket },
];

function StatusIcon({ status }) {
  if (status === "running") {
    return <LoaderCircle size={17} className="animate-spin text-amber-500" />;
  }
  if (status === "done") return <CheckCircle2 size={17} className="text-emerald-500" />;
  if (status === "error") return <AlertCircle size={17} className="text-rose-500" />;
  return <Circle size={17} className="text-slate-300" />;
}

export default function AgentPanel({
  sending,
  lastTool,
  requestStatus,
  session,
  health,
}) {
  const activeTool = normalizeTool(lastTool);
  const lastAssistant = [...(session?.messages || [])]
    .reverse()
    .find((message) => message.role === "assistant");
  const traceSteps = lastAssistant?.trace_steps || [];

  function getStatus(key) {
    if (sending) {
      if (key === "supervisor" || key === activeTool) return "running";
      return "waiting";
    }
    if (requestStatus === "success") {
      if (key === "supervisor" || key === activeTool) return "done";
    }
    if (requestStatus === "error" && key === "supervisor") return "error";
    return "waiting";
  }

  const knowledge = health?.components?.knowledge || {};
  const tickets = health?.components?.tickets || {};

  return (
    <aside className="hidden h-screen w-[300px] shrink-0 flex-col overflow-y-auto border-l border-slate-200 bg-white xl:flex">
      <div className="border-b border-slate-100 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">智能体架构</h2>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-[9px] tracking-wide text-slate-500">
            LIVE
          </span>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">
          展示本次请求实际使用的模块与执行步骤，不代表内部实时调用链。
        </p>
      </div>

      <div className="flex-1 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-700">Agent 模块</h3>
          <span className="text-[10px] text-slate-400">4 个组件</span>
        </div>

        <div className="space-y-2.5">
          {AGENTS.map((agent) => {
            const status = getStatus(agent.key);
            const Icon = agent.icon;
            return (
              <div
                key={agent.key}
                className={`rounded-xl border p-3.5 transition ${
                  status === "running"
                    ? "border-amber-200 bg-amber-50/60"
                    : status === "done"
                      ? "border-emerald-200 bg-emerald-50/40"
                      : status === "error"
                        ? "border-rose-200 bg-rose-50"
                        : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-500">
                    <Icon size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-slate-800">{agent.name}</p>
                    <p className="mt-0.5 text-[10px] text-slate-400">{agent.desc}</p>
                  </div>
                  <StatusIcon status={status} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-700">执行轨迹</h3>
            <span className="text-[10px] text-slate-400">{traceSteps.length} 步</span>
          </div>
          {traceSteps.length ? (
            <div className="space-y-1.5 rounded-xl border border-slate-100 bg-slate-50/60 p-3">
              {traceSteps.slice(-8).map((step, index) => (
                <div key={index} className="flex items-start gap-2 text-[10px] leading-5 text-slate-500">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-indigo-400" />
                  <span>{step}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-xl border border-dashed border-slate-200 p-3 text-[10px] leading-5 text-slate-400">
              发送一条消息后，这里会显示 Supervisor 的路由与 Agent 执行步骤。
            </p>
          )}
        </div>

        <div className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50/70 p-3.5">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-indigo-700">
            <Sparkles size={13} />
            工具与数据
          </div>
          <div className="mt-2 space-y-1.5 text-[10px] text-indigo-800/70">
            <p className="flex justify-between">
              <span>知识库文档</span>
              <b>{knowledge.documents ?? 0} 篇</b>
            </p>
            <p className="flex justify-between">
              <span>向量切片</span>
              <b>{knowledge.chunks ?? 0} 个</b>
            </p>
            <p className="flex justify-between">
              <span>工单</span>
              <b>{tickets.total ?? 0} 张</b>
            </p>
            <p className="flex justify-between">
              <span>业务订单</span>
              <b>{health?.components?.business_db?.orders ?? 0} 笔</b>
            </p>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-100 p-4">
        <div className="space-y-2 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-slate-500">后端请求</span>
            <span
              className={
                sending
                  ? "text-amber-600"
                  : requestStatus === "success"
                    ? "text-emerald-600"
                    : requestStatus === "error"
                      ? "text-rose-500"
                      : "text-slate-400"
              }
            >
              {sending
                ? "处理中"
                : requestStatus === "success"
                  ? "最近请求成功"
                  : requestStatus === "error"
                    ? "最近请求失败"
                    : "等待请求"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">知识库</span>
            <span className={knowledge.ready ? "text-emerald-600" : "text-amber-600"}>
              {knowledge.ready ? "索引就绪" : "未就绪"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500">会话记忆</span>
            <span className="text-emerald-600">SQLite 持久化</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
