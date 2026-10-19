import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  CheckCircle2,
  Database,
  ExternalLink,
  HardDrive,
  Menu,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  UserRound,
  XCircle,
} from "lucide-react";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";
import {
  Button,
  Card,
  Field,
  SectionTitle,
  Spinner,
  StatCard,
  inputClass,
} from "../components/ui";

const COMPONENT_LABELS = {
  api: "FastAPI 服务",
  llm: "大模型服务",
  business_db: "业务数据库",
  knowledge: "知识库向量索引",
  tickets: "工单数据库",
  memory: "会话记忆库",
  frontend: "前端静态资源",
};

export default function SettingsPage({
  user,
  onUserChange,
  onOpenMenu,
  onClearLocalChat,
  health: healthProp,
  onHealthChange,
}) {
  const [health, setHealth] = useState(healthProp || null);
  const [loading, setLoading] = useState(!healthProp);
  const [error, setError] = useState("");
  const [userInput, setUserInput] = useState(user);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.health();
      setHealth(data);
      onHealthChange?.(data);
    } catch (requestError) {
      setError(requestError.message || "无法获取服务状态");
    } finally {
      setLoading(false);
    }
  }, [onHealthChange]);

  useEffect(() => {
    if (!healthProp) load();
  }, [healthProp, load]);

  function saveUser() {
    const value = userInput.trim();
    if (!value) return;
    onUserChange(value);
    setMessage("用户标识已更新，聊天与工单将使用新的身份。");
    setTimeout(() => setMessage(""), 2500);
  }

  async function clearBackendConversations() {
    if (!window.confirm(`确定清空用户 ${user} 在服务端的全部对话记忆吗？`)) return;
    try {
      const result = await api.clearConversations(user);
      setMessage(`已清空 ${result.deleted} 条服务端对话消息。`);
      setTimeout(() => setMessage(""), 3000);
    } catch (requestError) {
      setError(requestError.message || "清空失败");
    }
  }

  const components = health?.components || {};
  const business = components.business_db || {};
  const knowledge = components.knowledge || {};
  const memory = components.memory || {};

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-[#f7f8fc]">
      <header className="flex shrink-0 flex-col gap-3 border-b border-slate-200/80 bg-white px-4 py-5 md:flex-row md:items-center md:justify-between md:px-7">
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenMenu}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="打开菜单"
          >
            <Menu size={19} />
          </button>
          <div>
            <p className="text-[11px] font-semibold tracking-[0.16em] text-indigo-600">
              SYSTEM SETTINGS
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-900 md:text-2xl">系统设置</h1>
            <p className="mt-1 text-xs text-slate-400">
              服务健康状态、用户身份与数据口径
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
          {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
          刷新状态
        </Button>
      </header>

      <div className="mx-auto w-full max-w-[1100px] px-4 py-6 md:px-7">
        {error && (
          <Card className="mb-4 border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
            {error}
          </Card>
        )}
        {message && (
          <Card className="mb-4 border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-700">
            {message}
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="服务版本"
            value={health?.version || "2.0.0"}
            hint={`运行 ${Math.round((health?.uptime_seconds || 0) / 60)} 分钟`}
            icon={Server}
            tone="indigo"
          />
          <StatCard
            label="业务订单"
            value={formatNumber(business.orders || 0)}
            hint={`客户 ${formatNumber(business.customers || 0)} · 商品 ${formatNumber(business.products || 0)}`}
            icon={Database}
            tone="blue"
          />
          <StatCard
            label="知识库文档"
            value={formatNumber(knowledge.documents || 0)}
            hint={`${formatNumber(knowledge.pages || 0)} 页 · ${formatNumber(knowledge.chunks || 0)} 切片`}
            icon={BookOpen}
            tone="emerald"
          />
          <StatCard
            label="会话消息"
            value={formatNumber(memory.messages || 0)}
            hint={`${formatNumber(memory.sessions || 0)} 个会话`}
            icon={HardDrive}
            tone="amber"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-2">
            <SectionTitle
              title="组件状态"
              subtitle="API、模型、数据库、知识库与前端资源"
              action={
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-medium ${
                    health?.status === "ok"
                      ? "bg-emerald-50 text-emerald-600"
                      : "bg-amber-50 text-amber-600"
                  }`}
                >
                  <Activity size={11} />
                  {health?.status === "ok" ? "全部正常" : "部分降级"}
                </span>
              }
            />
            <div className="mt-4 divide-y divide-slate-100">
              {Object.entries(COMPONENT_LABELS).map(([key, label]) => {
                const component = components[key] || { status: "unknown" };
                const ok = ["ok", "healthy"].includes(component.status);
                return (
                  <div key={key} className="flex items-center gap-3 py-3">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                        ok ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"
                      }`}
                    >
                      {ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-700">{label}</p>
                      <p className="mt-0.5 truncate text-[10px] text-slate-400">
                        {component.status === "ok"
                          ? "运行正常"
                          : component.error || component.status || "未知"}
                        {key === "llm" && component.model ? ` · ${component.model}` : ""}
                        {key === "knowledge" && component.ready
                          ? ` · ${component.model}`
                          : ""}
                      </p>
                    </div>
                    <span
                      className={`text-[10px] font-medium ${
                        ok ? "text-emerald-600" : "text-amber-600"
                      }`}
                    >
                      {component.status}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="用户身份" subtitle="用于会话与工单数据隔离" />
            <div className="mt-4">
              <Field label="user_id" hint="修改后请刷新页面">
                <input
                  value={userInput}
                  onChange={(event) => setUserInput(event.target.value)}
                  className={inputClass}
                  placeholder="default_user"
                />
              </Field>
              <Button className="mt-3 w-full" size="sm" onClick={saveUser}>
                <UserRound size={14} />
                保存用户标识
              </Button>
              <p className="mt-3 rounded-lg bg-slate-50 p-2.5 text-[10px] leading-5 text-slate-500">
                当前身份：<span className="font-mono text-slate-700">{user}</span>
                <br />
                切换身份后，工单中心只显示该用户的工单，对话记忆也相互独立。
              </p>
            </div>
          </Card>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <SectionTitle title="数据与接口" subtitle="当前运行配置" />
            <dl className="mt-4 space-y-3 text-xs">
              {[
                ["前端地址", window.location.origin],
                ["后端接口", window.location.origin + "/api"],
                ["API 文档", window.location.origin + "/docs"],
                ["用户标识", user],
                ["会话存储", "浏览器 localStorage + 服务端 SQLite"],
                ["知识库模型", knowledge.model || "BAAI/bge-small-zh-v1.5"],
              ].map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="max-w-[65%] truncate text-right font-mono text-[10px] text-slate-700">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] text-slate-600 hover:border-indigo-300 hover:text-indigo-600"
              >
                <ExternalLink size={12} />
                打开 API 文档
              </a>
              <a
                href="/api/health"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] text-slate-600 hover:border-indigo-300 hover:text-indigo-600"
              >
                <Activity size={12} />
                健康检查 JSON
              </a>
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="数据维护" subtitle="清理会话与查看数据口径" />
            <div className="mt-4 space-y-3">
              <div className="flex items-start gap-3 rounded-xl border border-slate-100 p-3">
                <Trash2 size={15} className="mt-0.5 text-rose-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-700">清空本地对话</p>
                  <p className="mt-0.5 text-[10px] text-slate-400">
                    删除浏览器中保存的会话记录，不影响服务端数据。
                  </p>
                </div>
                <Button variant="danger" size="sm" onClick={onClearLocalChat}>
                  清空
                </Button>
              </div>
              <div className="flex items-start gap-3 rounded-xl border border-slate-100 p-3">
                <HardDrive size={15} className="mt-0.5 text-amber-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-700">清空服务端记忆</p>
                  <p className="mt-0.5 text-[10px] text-slate-400">
                    删除当前用户的 SQLite 对话历史，用于重置多轮上下文。
                  </p>
                </div>
                <Button variant="danger" size="sm" onClick={clearBackendConversations}>
                  清空
                </Button>
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold text-indigo-700">
                <ShieldCheck size={13} />
                数据口径说明
              </div>
              <p className="mt-1.5 text-[10px] leading-5 text-indigo-800/70">
                业务库为京东商城场景的演示数据：商品品类与部分参考价来自公开商品信息，
                客户、员工与订单为固定随机种子生成，不对应真实个人或真实交易。
                销售额默认为“已完成 / 已发货”订单金额。
              </p>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}
