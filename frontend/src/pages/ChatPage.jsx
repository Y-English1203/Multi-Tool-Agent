import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Brain,
  Check,
  Clock,
  Copy,
  Database,
  FileText,
  ListChecks,
  Menu,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Ticket,
  Trash2,
  User,
  Wrench,
} from "lucide-react";
import { api } from "../lib/api";
import {
  STATUS_STYLES,
  normalizeSources,
  normalizeTool,
  toolLabel,
  truncate,
} from "../lib/format";
import Markdown from "../components/Markdown";
import DataTable from "../components/DataTable";

const PROMPTS = [
  {
    icon: FileText,
    title: "制度与流程问答",
    description: "从《京东集团员工手册》中检索制度条款，并给出页码引用。",
    question: "员工申请病假需要提供哪些材料？",
  },
  {
    icon: Database,
    title: "业务数据分析",
    description: "用自然语言查询订单、客户、商品与销售数据。",
    question: "销售额最高的品类是什么？",
  },
  {
    icon: Ticket,
    title: "工单服务",
    description: "创建报修工单，或查询已有工单的处理进度。",
    question: "查询我的工单",
  },
];

const CHIPS = [
  "年假有多少天？",
  "上个月订单量是多少？",
  "本月各品类销售情况",
  "帮我创建一个工单：VPN 无法连接",
  "查一下本月销售额和我的工单",
];

const TOOL_STYLES = {
  rag: "border-emerald-200 bg-emerald-50 text-emerald-700",
  sql: "border-blue-200 bg-blue-50 text-blue-700",
  ticket: "border-amber-200 bg-amber-50 text-amber-700",
};

function makeId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function makeTime() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SourceList({ sources }) {
  const items = normalizeSources(sources).filter((item) => item.page);
  const unique = Array.from(
    new Map(items.map((item) => [`${item.source}-${item.page}`, item])).values()
  );

  if (!unique.length) return null;

  return (
    <details className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 px-3 py-2.5">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-indigo-700">
        <FileText size={14} />
        参考来源（{unique.length}）
        <span className="ml-auto text-[10px] font-normal text-indigo-400">展开查看原文片段</span>
      </summary>
      <div className="mt-3 space-y-2">
        {unique.map((item, index) => (
          <div
            key={`${item.source}-${item.page}-${index}`}
            className="rounded-lg border border-indigo-100 bg-white px-3 py-2"
          >
            <div className="flex items-center gap-2 text-[11px] font-medium text-indigo-700">
              <span className="rounded bg-indigo-50 px-1.5 py-0.5">
                {item.source || "员工手册"} · 第 {item.page} 页
              </span>
              {item.score > 0 && (
                <span className="text-[10px] font-normal text-slate-400">
                  相关度 {(item.score * 100).toFixed(0)}%
                </span>
              )}
            </div>
            {item.content && (
              <p className="mt-1.5 line-clamp-3 text-[11px] leading-5 text-slate-500">
                {item.content}
              </p>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function SqlResult({ data }) {
  if (!data?.columns?.length) return null;
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
          <Database size={14} className="text-blue-500" />
          查询结果
        </span>
        <span className="text-[10px] text-slate-400">返回 {data.row_count ?? data.rows?.length ?? 0} 行</span>
      </div>
      <DataTable columns={data.columns} rows={data.rows || []} maxHeight="300px" />
      {data.sql && (
        <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <summary className="cursor-pointer text-[11px] font-medium text-slate-500">
            查看生成的 SQL
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-600">
            {data.sql}
          </pre>
        </details>
      )}
    </div>
  );
}

function TicketResult({ data }) {
  const ticket = data?.ticket;
  if (!ticket) return null;

  return (
    <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Ticket size={15} className="text-amber-600" />
        <span className="text-xs font-semibold text-amber-800">工单 #{ticket.id}</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
            STATUS_STYLES[ticket.status] || STATUS_STYLES["待处理"]
          }`}
        >
          {ticket.status}
        </span>
        <span className="text-[10px] text-amber-700/70">
          优先级 {ticket.priority} · {ticket.category}
        </span>
      </div>
      <p className="mt-2 text-xs leading-6 text-slate-600">{ticket.issue}</p>
      {ticket.resolution && (
        <p className="mt-1 text-[11px] text-slate-500">处理结果：{ticket.resolution}</p>
      )}
    </div>
  );
}

function PlanPanel({ plan, steps }) {
  if (!plan?.length) return null;

  return (
    <details
      open={plan.length > 1}
      className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/60 px-3 py-2.5"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 text-[11px] font-semibold text-indigo-700">
        <ListChecks size={13} />
        智能规划 · {plan.length} 步
        <span className="ml-auto text-[10px] font-normal text-indigo-400">
          {plan.length > 1 ? "多工具协作" : "单工具"}
        </span>
      </summary>
      <div className="mt-2 space-y-1.5">
        {plan.map((step, index) => {
          const result = steps?.[index];
          const status = !result
            ? "待执行"
            : result.error
              ? "异常"
              : `完成 · ${result.elapsed_ms}ms`;
          return (
            <div key={`${step.tool}-${index}`} className="flex items-start gap-2">
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[9px] font-bold ${
                  result && !result.error
                    ? "bg-emerald-100 text-emerald-700"
                    : result?.error
                      ? "bg-rose-100 text-rose-600"
                      : "bg-white text-slate-400"
                }`}
              >
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-slate-700">
                  {toolLabel(step.tool)} · {step.purpose}
                </p>
                <p className="mt-0.5 truncate text-[10px] text-slate-400">
                  {step.question}
                </p>
              </div>
              <span className="shrink-0 text-[9px] text-slate-400">{status}</span>
            </div>
          );
        })}
      </div>
    </details>
  );
}

function CriticPanel({ critic, confidence, clarification }) {
  if (clarification) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
        <Brain size={14} />
        当前信息不足，Agent 先向你确认，而不是猜测答案。
      </div>
    );
  }

  if (!critic || critic.supported === undefined || confidence === null) return null;

  const passed = critic.supported && Number(confidence) >= 0.7;
  return (
    <div
      className={`mt-3 rounded-xl border px-3 py-2 text-[11px] ${
        passed
          ? "border-emerald-100 bg-emerald-50/60 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <ShieldCheck size={13} />
        <span className="font-semibold">
          {passed ? "证据校验通过" : "证据校验发现风险"}
        </span>
        <span className="text-[10px] opacity-70">
          置信度 {(Number(confidence) * 100).toFixed(0)}%
        </span>
        {critic.revised && <span className="text-[10px] opacity-70">已自动修正</span>}
      </div>
      {critic.issues?.length > 0 && (
        <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-[10px] leading-5">
          {critic.issues.slice(0, 3).map((issue, index) => (
            <li key={index}>{issue}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StepResults({ steps }) {
  if (!steps || steps.length < 2) return null;

  return (
    <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2.5">
      <summary className="cursor-pointer text-[11px] font-semibold text-slate-600">
        分步结果（{steps.length} 步）
      </summary>
      <div className="mt-3 space-y-3">
        {steps.map((step, index) => (
          <div key={`${step.tool}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-bold text-slate-400">0{index + 1}</span>
              <span className="text-[11px] font-semibold text-slate-700">
                {toolLabel(step.tool)}
              </span>
              <span className="text-[10px] text-slate-400">{step.question}</span>
              <span className="ml-auto text-[9px] text-slate-400">
                {step.error ? "异常" : `${step.elapsed_ms}ms`}
              </span>
            </div>
            {step.error ? (
              <p className="mt-2 text-[10px] text-rose-600">{step.error}</p>
            ) : (
              <>
                <p className="mt-2 whitespace-pre-wrap text-[11px] leading-5 text-slate-600">
                  {step.answer}
                </p>
                {step.data?.columns?.length > 0 && (
                  <div className="mt-2">
                    <DataTable
                      columns={step.data.columns}
                      rows={step.data.rows || []}
                      maxHeight="220px"
                      footer={false}
                    />
                  </div>
                )}
                {step.data?.ticket && (
                  <TicketResult data={{ ticket: step.data.ticket }} />
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function FollowUps({ items, onFollowUp }) {
  if (!items?.length || !onFollowUp) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-[10px] text-slate-400">继续追问：</span>
      {items.slice(0, 3).map((item) => (
        <button
          key={item}
          onClick={() => onFollowUp(item)}
          className="inline-flex items-center gap-1 rounded-full border border-indigo-100 bg-indigo-50/60 px-2.5 py-1 text-[10px] text-indigo-600 transition hover:border-indigo-300 hover:bg-indigo-50"
        >
          {item}
          <ArrowRight size={10} />
        </button>
      ))}
    </div>
  );
}

function MessageBubble({ message, onRetry, onFollowUp }) {
  const isUser = message.role === "user";
  const tool = normalizeTool(message.tool_used);
  const tools = Array.isArray(message.tools) && message.tools.length
    ? Array.from(new Set(message.tools))
    : tool
      ? [tool]
      : [];
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.text || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  if (isUser) {
    return (
      <div className="flex flex-row-reverse gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-200 text-slate-500">
          <User size={17} />
        </div>
        <article className="max-w-[88%] rounded-2xl rounded-tr-sm border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-700 shadow-sm md:max-w-[78%]">
          <p className="whitespace-pre-wrap break-words">{message.text}</p>
          <p className="mt-2 text-right text-[10px] text-slate-400">{message.time}</p>
        </article>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
        <Bot size={18} />
      </div>

      <article className="min-w-0 max-w-[92%] flex-1 rounded-2xl rounded-tl-sm border border-indigo-100/80 bg-white px-4 py-4 shadow-sm md:max-w-[84%]">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-semibold text-slate-700">Multi-Tool Agent</p>
          {tools.map((item) => (
            <span
              key={item}
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                TOOL_STYLES[item] || "border-slate-200 bg-slate-50 text-slate-500"
              }`}
            >
              <Wrench size={10} />
              {toolLabel(item)}
            </span>
          ))}
          {tools.length > 1 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
              <Brain size={10} />
              多工具协作
            </span>
          )}
          {message.confidence !== null && message.confidence !== undefined && (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                Number(message.confidence) >= 0.7
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-amber-50 text-amber-700"
              }`}
            >
              <ShieldCheck size={10} />
              {(Number(message.confidence) * 100).toFixed(0)}%
            </span>
          )}
          {message.time && (
            <span className="flex items-center gap-1 text-[10px] text-slate-400">
              <Clock size={10} />
              {message.time}
            </span>
          )}
          <button
            onClick={copyAnswer}
            className="ml-auto rounded-lg p-1.5 text-slate-300 transition hover:bg-slate-100 hover:text-slate-500"
            title="复制回答"
          >
            {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
          </button>
        </div>

        <PlanPanel plan={message.plan} steps={message.steps} />

        <div className="mt-3">
          <Markdown text={message.text || ""} />
        </div>

        <CriticPanel
          critic={message.critic}
          confidence={message.confidence}
          clarification={message.clarification}
        />

        {message.intent_reason && (
          <p className="mt-3 text-[10px] text-slate-400">规划依据：{message.intent_reason}</p>
        )}

        <SourceList sources={message.sources} />
        <SqlResult data={message.data} />
        <TicketResult data={message.data} />
        <StepResults steps={message.steps} />
        <FollowUps items={message.follow_ups} onFollowUp={onFollowUp} />

        {message.trace_steps?.length > 0 && (
          <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-[11px] font-semibold text-slate-600">
              <Sparkles size={13} className="text-indigo-500" />
              Agent 执行过程（{message.trace_steps.length} 步）
            </summary>
            <div className="mt-2 space-y-1.5">
              {message.trace_steps.map((step, index) => (
                <div key={index} className="flex items-start gap-2 text-[11px] text-slate-500">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-indigo-400" />
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </details>
        )}

        {message.error && (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 p-3 text-[11px] leading-5 text-rose-700">
            <AlertCircle size={15} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              <p>{message.error}</p>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-rose-600 underline"
                >
                  <RotateCcw size={11} /> 重试
                </button>
              )}
            </div>
          </div>
        )}
      </article>
    </div>
  );
}

export default function ChatPage({
  session,
  userId,
  onUpdateSession,
  initialQuestion,
  onConsumeInitialQuestion,
  onOpenMenu,
  onClearSession,
  health,
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  const messages = session?.messages || [];
  const sessionId = session?.id;

  useEffect(() => {
    if (initialQuestion) {
      setInput(initialQuestion);
      onConsumeInitialQuestion?.();
      textareaRef.current?.focus();
    }
  }, [initialQuestion, onConsumeInitialQuestion]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  function update(updater) {
    if (!sessionId) return;
    onUpdateSession(sessionId, updater);
  }

  async function send(text = input) {
    const question = String(text || "").trim();
    if (!question || sending || !session) return;

    setError("");
    setLastQuestion(question);
    setSending(true);
    setInput("");

    const userMessage = {
      id: makeId(),
      role: "user",
      text: question,
      time: makeTime(),
    };

    update((current) => ({
      ...current,
      title: current.messages.length === 0 ? truncate(question, 24) : current.title,
      updatedAt: new Date().toISOString(),
      requestStatus: "running",
      lastTool: "",
      messages: [...current.messages, userMessage],
    }));

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await api.ask(
        { question, user_id: userId, session_id: session.session_id },
        controller.signal
      );

      const assistantMessage = {
        id: makeId(),
        role: "assistant",
        text: data.answer || "后端已完成请求，但没有返回回答内容。",
        time: makeTime(),
        sources: data.sources || [],
        pages: data.pages || [],
        trace_steps: data.trace_steps || [],
        tool_used: data.tool_used || "",
        tools: data.tools || [],
        data: data.data || {},
        plan: data.plan || [],
        steps: data.steps || [],
        plan_reason: data.plan_reason || "",
        confidence: data.confidence ?? null,
        critic: data.critic || {},
        follow_ups: data.follow_ups || [],
        clarification: Boolean(data.clarification),
        intent_reason: data.intent_reason || data.plan_reason || "",
        error: data.success === false ? data.error || "本次请求未能成功完成。" : null,
      };

      update((current) => ({
        ...current,
        updatedAt: new Date().toISOString(),
        requestStatus: data.success === false ? "error" : "success",
        lastTool: normalizeTool(data.tool_used),
        messages: [...current.messages, assistantMessage],
      }));
    } catch (requestError) {
      if (requestError.name === "AbortError") {
        update((current) => ({
          ...current,
          requestStatus: "idle",
          messages: [
            ...current.messages,
            {
              id: makeId(),
              role: "assistant",
              text: "本次请求已停止。",
              time: makeTime(),
              tool_used: "",
            },
          ],
        }));
        return;
      }

      setError(requestError.message || "请求失败，请稍后重试。");
      update((current) => ({
        ...current,
        updatedAt: new Date().toISOString(),
        requestStatus: "error",
        lastTool: "",
        messages: [
          ...current.messages,
          {
            id: makeId(),
            role: "assistant",
            text: "请求未能完成。",
            time: makeTime(),
            error: requestError.message || "请求失败，请稍后重试。",
          },
        ],
      }));
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  }

  function retry() {
    if (lastQuestion) send(lastQuestion);
  }

  const hasMessages = messages.length > 0;

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#f7f8fc]">
      <header className="flex h-[74px] shrink-0 items-center justify-between gap-3 border-b border-slate-200/80 bg-white px-4 md:px-7">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={onOpenMenu}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="打开菜单"
          >
            <Menu size={19} />
          </button>
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold text-slate-800 md:text-lg">
              {session?.title && session.title !== "新对话"
                ? session.title
                : "智能问答"}
            </h2>
            <p className="mt-0.5 truncate text-[11px] text-slate-400">
              Agentic Supervisor · 任务规划 · 多工具协作 · 证据校验
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] text-emerald-700 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Agentic 多步规划在线
            {health?.components?.knowledge?.documents ? (
              <span className="text-emerald-500">
                · {health.components.knowledge.documents} 篇文档
              </span>
            ) : null}
          </div>
          {hasMessages && (
            <button
              onClick={() => onClearSession?.(sessionId)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] text-slate-500 transition hover:border-rose-200 hover:text-rose-500"
              title="清空当前对话"
            >
              <Trash2 size={13} />
              <span className="hidden sm:inline">清空</span>
            </button>
          )}
        </div>
      </header>

      <section className="flex-1 overflow-y-auto px-4 py-6 md:px-7" aria-label="聊天消息">
        {!hasMessages ? (
          <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-center py-6">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-200">
              <Sparkles size={27} />
            </div>
            <p className="mb-2 text-xs font-semibold tracking-[0.18em] text-indigo-600">
              AGENTIC MULTI-TOOL ASSISTANT
            </p>
            <h3 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
              你好，今天想了解什么？
            </h3>
            <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">
              我会先规划任务，再按需要组合文档检索、业务数据查询和工单服务。
              回答会经过证据校验，并给出置信度、来源和下一步建议。
            </p>

            <div className="mt-8 grid grid-cols-1 gap-3 md:grid-cols-3">
              {PROMPTS.map((prompt) => {
                const Icon = prompt.icon;
                return (
                  <button
                    key={prompt.title}
                    onClick={() => send(prompt.question)}
                    disabled={sending}
                    className="group rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md disabled:opacity-50"
                  >
                    <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white">
                      <Icon size={18} />
                    </div>
                    <p className="text-sm font-semibold text-slate-800">{prompt.title}</p>
                    <p className="mt-1.5 text-[11px] leading-5 text-slate-500">
                      {prompt.description}
                    </p>
                    <div className="mt-3 flex items-center gap-1 text-[11px] font-medium text-indigo-600">
                      开始提问 <ArrowUpRight size={13} />
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="mt-7 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-slate-400">试试：</span>
              {CHIPS.map((chip) => (
                <button
                  key={chip}
                  onClick={() => setInput(chip)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] text-slate-500 transition hover:border-indigo-300 hover:text-indigo-600"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onRetry={retry}
                onFollowUp={send}
              />
            ))}

            {sending && (
              <div className="flex gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
                  <Bot size={18} />
                </div>
                <div className="flex items-center gap-3 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
                  <div className="flex items-center gap-1">
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-indigo-500" />
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-indigo-500" />
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-indigo-500" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-700">Supervisor 正在调度</p>
                    <p className="mt-0.5 text-[10px] text-slate-400">
                      正在判断意图并调用合适的 Agent…
                    </p>
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </section>

      <footer className="shrink-0 border-t border-slate-200/80 bg-white px-4 py-3.5 md:px-7">
        <div className="mx-auto max-w-3xl">
          {error && (
            <div className="mb-2 flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
              <AlertCircle size={13} />
              {error}
            </div>
          )}
          <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 transition focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
              rows={1}
              placeholder="向 Multi-Tool Agent 发送消息…"
              className="max-h-36 min-h-10 flex-1 resize-y bg-transparent px-3 py-2.5 text-sm leading-6 text-slate-700 outline-none placeholder:text-slate-400 disabled:opacity-60"
            />

            {sending ? (
              <button
                onClick={stop}
                className="flex h-10 shrink-0 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 text-xs font-medium text-slate-600 transition hover:border-rose-300 hover:text-rose-500"
              >
                <Square size={13} className="fill-current" />
                停止
              </button>
            ) : (
              <button
                onClick={() => send()}
                disabled={!input.trim()}
                className="flex h-10 shrink-0 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:bg-indigo-300"
              >
                <Send size={15} />
                发送
              </button>
            )}
          </div>
          <p className="mt-2 text-center text-[10px] text-slate-400">
            Enter 发送 · Shift + Enter 换行 · 回答中的制度条款请以员工手册原文为准
          </p>
        </div>
      </footer>
    </main>
  );
}
