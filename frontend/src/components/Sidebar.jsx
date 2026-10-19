import {
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronRight,
  History,
  LayoutDashboard,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  Ticket,
  Trash2,
  X,
} from "lucide-react";
import { truncate } from "../lib/format";

const NAV_ITEMS = [
  { id: "dashboard", label: "工作台", icon: LayoutDashboard },
  { id: "chat", label: "智能问答", icon: MessageSquare },
  { id: "knowledge", label: "知识库", icon: BookOpen },
  { id: "analytics", label: "数据分析", icon: BarChart3 },
  { id: "tickets", label: "工单中心", icon: Ticket },
  { id: "settings", label: "系统设置", icon: Settings },
];

function SessionRow({ session, active, onSelect, onDelete }) {
  const title =
    session.title ||
    session.messages?.find((message) => message.role === "user")?.text ||
    "新对话";
  const count = session.messages?.length
    ? `${Math.ceil(session.messages.length / 2)} 轮对话`
    : "尚未开始";

  return (
    <div
      className={`group flex items-center gap-1 rounded-xl transition ${
        active ? "bg-indigo-50" : "hover:bg-slate-50"
      }`}
    >
      <button
        onClick={() => onSelect(session.id)}
        className="min-w-0 flex-1 px-3 py-2.5 text-left"
      >
        <div
          className={`truncate text-xs font-medium ${
            active ? "text-indigo-700" : "text-slate-600"
          }`}
        >
          {truncate(title, 26)}
        </div>
        <div className="mt-1 text-[10px] text-slate-400">{count}</div>
      </button>
      <button
        onClick={() => onDelete(session.id)}
        title="删除对话"
        className="mr-1 rounded-lg p-1.5 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100"
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}

export default function Sidebar({
  page,
  onNavigate,
  sessions = [],
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  health,
}) {
  const healthOk = health?.status === "ok";

  return (
    <>
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] shrink-0 flex-col border-r border-slate-200 bg-white transition-all duration-200 lg:static lg:translate-x-0 ${
          mobileOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        } ${collapsed ? "lg:w-[78px]" : "lg:w-[268px]"}`}
      >
        <div className="flex h-[74px] shrink-0 items-center gap-3 border-b border-slate-100 px-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-200">
            <Bot size={23} />
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-sm font-bold text-slate-900">
                Multi-Tool Agent
              </h1>
              <p className="mt-0.5 text-[11px] text-slate-400">企业智能知识中台</p>
            </div>
          )}
          <button
            onClick={onToggleCollapse}
            title={collapsed ? "展开侧栏" : "收起侧栏"}
            className="hidden rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 lg:inline-flex"
          >
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
          <button
            onClick={onCloseMobile}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 lg:hidden"
            aria-label="关闭菜单"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4">
          {!collapsed && (
            <p className="mb-2 px-3 text-[10px] font-semibold tracking-[0.18em] text-slate-400">
              WORKSPACE
            </p>
          )}
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = page === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onNavigate(item.id);
                    onCloseMobile?.();
                  }}
                  title={collapsed ? item.label : undefined}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                    active
                      ? "bg-indigo-50 font-semibold text-indigo-700"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <Icon size={18} className="shrink-0" />
                  {!collapsed && <span className="flex-1">{item.label}</span>}
                  {!collapsed && active && <ChevronRight size={14} />}
                </button>
              );
            })}
          </nav>

          {page === "chat" && (
            <div className="mt-5">
              {!collapsed ? (
                <>
                  <button
                    onClick={onNewChat}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
                  >
                    <Plus size={17} />
                    新建对话
                  </button>

                  <div className="mb-2 mt-5 flex items-center gap-2 px-2 text-[11px] font-semibold text-slate-400">
                    <History size={13} />
                    最近对话
                  </div>

                  {sessions.length === 0 ? (
                    <p className="px-3 py-4 text-[11px] leading-5 text-slate-400">
                      暂无历史对话，开始你的第一个问题吧。
                    </p>
                  ) : (
                    <div className="space-y-0.5">
                      {sessions.slice(0, 30).map((session) => (
                        <SessionRow
                          key={session.id}
                          session={session}
                          active={session.id === activeSessionId}
                          onSelect={onSelectSession}
                          onDelete={onDeleteSession}
                        />
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <button
                  onClick={onNewChat}
                  title="新建对话"
                  className="flex w-full justify-center rounded-xl bg-indigo-600 p-2.5 text-white transition hover:bg-indigo-700"
                >
                  <Plus size={18} />
                </button>
              )}
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-slate-100 p-3">
          <div
            className={`flex items-center gap-3 rounded-xl bg-slate-50 p-3 ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                healthOk ? "bg-emerald-100 text-emerald-600" : "bg-amber-100 text-amber-600"
              }`}
            >
              <CheckCircle2 size={16} />
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold text-slate-700">
                  {healthOk ? "服务运行正常" : "服务状态待检查"}
                </p>
                <p className="mt-0.5 truncate text-[10px] text-slate-400">
                  v{health?.version || "2.0.0"} · Multi-Agent
                </p>
              </div>
            )}
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/30 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}
    </>
  );
}
