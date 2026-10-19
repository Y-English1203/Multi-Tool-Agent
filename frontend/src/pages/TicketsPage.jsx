import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  Clock3,
  LoaderCircle,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Ticket,
  UserRound,
} from "lucide-react";
import { api } from "../lib/api";
import {
  formatNumber,
  formatPercent,
  PRIORITY_STYLES,
  STATUS_STYLES,
  truncate,
} from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Modal,
  SectionTitle,
  Spinner,
  StatCard,
  inputClass,
  selectClass,
} from "../components/ui";

const NEXT_STATUS = {
  待处理: "处理中",
  处理中: "已解决",
  已解决: "已关闭",
};

const STATUS_FILTERS = [
  { key: "", label: "全部" },
  { key: "待处理", label: "待处理" },
  { key: "处理中", label: "处理中" },
  { key: "已解决", label: "已解决" },
  { key: "已关闭", label: "已关闭" },
];

const EMPTY_FORM = { issue: "", category: "其他", priority: "中" };

export default function TicketsPage({ userId, onOpenMenu }) {
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [meta, setMeta] = useState({ categories: [], priorities: [], statuses: [] });
  const [status, setStatus] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState(null);
  const [detailForm, setDetailForm] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [listData, statsData, metaData] = await Promise.all([
        api.tickets({
          user_id: userId,
          status: status || undefined,
          keyword: keyword || undefined,
          limit: 200,
        }),
        api.ticketStats(userId),
        api.ticketMeta(),
      ]);
      setTickets(listData.items || []);
      setStats(statsData);
      setMeta(metaData);
    } catch (requestError) {
      setError(requestError.message || "加载工单失败");
    } finally {
      setLoading(false);
    }
  }, [userId, status, keyword]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  function openDetail(ticket) {
    setSelected(ticket);
    setDetailForm({
      status: ticket.status,
      priority: ticket.priority,
      resolution: ticket.resolution || "",
      assignee: ticket.assignee || "",
    });
  }

  async function createTicket() {
    if (!form.issue.trim()) {
      setError("请填写工单问题描述。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.createTicket({
        user_id: userId,
        issue: form.issue.trim(),
        category: form.category,
        priority: form.priority,
      });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (requestError) {
      setError(requestError.message || "创建工单失败");
    } finally {
      setSaving(false);
    }
  }

  async function saveDetail() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateTicket(selected.id, {
        user_id: userId,
        status: detailForm.status,
        priority: detailForm.priority,
        resolution: detailForm.resolution,
        assignee: detailForm.assignee,
      });
      setSelected(updated);
      setDetailForm({
        status: updated.status,
        priority: updated.priority,
        resolution: updated.resolution || "",
        assignee: updated.assignee || "",
      });
      await load();
    } catch (requestError) {
      setError(requestError.message || "更新工单失败");
    } finally {
      setSaving(false);
    }
  }

  async function advance(ticket) {
    const next = NEXT_STATUS[ticket.status];
    if (!next) return;
    setError("");
    try {
      await api.updateTicket(ticket.id, {
        user_id: userId,
        status: next,
        resolution:
          next === "已解决"
            ? ticket.resolution || "问题已处理并确认。"
            : undefined,
      });
      await load();
      if (selected?.id === ticket.id) {
        const refreshed = await api.ticket(ticket.id, userId);
        openDetail(refreshed);
      }
    } catch (requestError) {
      setError(requestError.message || "更新工单失败");
    }
  }

  const statusCounts = stats?.by_status || {};
  const openCount = (statusCounts["待处理"] || 0) + (statusCounts["处理中"] || 0);

  const statusTiles = ["待处理", "处理中", "已解决", "已关闭"].map((item) => ({
    status: item,
    count: statusCounts[item] || 0,
  }));

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
              SERVICE DESK
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-900 md:text-2xl">工单中心</h1>
            <p className="mt-1 text-xs text-slate-400">
              当前用户：{userId} · 工单数据按用户隔离
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
            刷新
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus size={14} />
            新建工单
          </Button>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-7">
        {error && (
          <Card className="mb-4 flex items-start gap-2 border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
            <AlertCircle size={15} className="mt-0.5 shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError("")} className="text-rose-400 hover:text-rose-600">
              关闭
            </button>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="工单总数"
            value={formatNumber(stats?.total || 0)}
            hint="当前用户"
            icon={Ticket}
            tone="indigo"
          />
          <StatCard
            label="待处理 / 处理中"
            value={formatNumber(openCount)}
            hint="需要进行处理"
            icon={Clock3}
            tone="amber"
          />
          <StatCard
            label="已解决 / 已关闭"
            value={formatNumber(stats?.resolved || 0)}
            hint="历史已完成工单"
            icon={CheckCircle2}
            tone="emerald"
          />
          <StatCard
            label="解决率"
            value={formatPercent(stats?.resolve_rate || 0)}
            hint={`高优先级 ${stats?.by_priority?.高 || 0} 张`}
            icon={CircleDot}
            tone="blue"
          />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {statusTiles.map((tile) => (
            <button
              key={tile.status}
              onClick={() => setStatus(status === tile.status ? "" : tile.status)}
              className={`rounded-xl border p-3 text-left transition ${
                status === tile.status
                  ? "border-indigo-300 bg-indigo-50"
                  : "border-slate-200 bg-white hover:border-indigo-200"
              }`}
            >
              <p className="text-[11px] text-slate-500">{tile.status}</p>
              <p className="mt-1 text-xl font-bold text-slate-800">{formatNumber(tile.count)}</p>
            </button>
          ))}
        </div>

        <Card className="mt-4 p-5">
          <SectionTitle
            title="工单列表"
            subtitle={`${tickets.length} 张工单${status ? ` · ${status}` : ""}`}
            action={
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
                  <input
                    value={keyword}
                    onChange={(event) => setKeyword(event.target.value)}
                    placeholder="搜索问题 / 分类"
                    className="w-44 rounded-lg border border-slate-200 py-1.5 pl-8 pr-2 text-xs outline-none focus:border-indigo-300"
                  />
                </div>
                <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
                  {STATUS_FILTERS.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => setStatus(item.key)}
                      className={`rounded-md px-2 py-1 text-[10px] font-medium transition ${
                        status === item.key
                          ? "bg-white text-indigo-700 shadow-sm"
                          : "text-slate-500"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            }
          />

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="pb-2 pr-3 font-medium">编号</th>
                  <th className="pb-2 pr-3 font-medium">问题</th>
                  <th className="pb-2 pr-3 font-medium">分类</th>
                  <th className="pb-2 pr-3 font-medium">优先级</th>
                  <th className="pb-2 pr-3 font-medium">状态</th>
                  <th className="pb-2 pr-3 font-medium">更新时间</th>
                  <th className="pb-2 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <tr key={ticket.id} className="border-b border-slate-50 last:border-0">
                    <td className="py-3 pr-3 font-mono text-[10px] text-slate-400">
                      #{ticket.id}
                    </td>
                    <td className="max-w-[320px] py-3 pr-3">
                      <button
                        onClick={() => openDetail(ticket)}
                        className="block truncate text-left font-medium text-slate-700 hover:text-indigo-600"
                      >
                        {truncate(ticket.issue, 46)}
                      </button>
                      {ticket.assignee && (
                        <p className="mt-0.5 text-[10px] text-slate-400">
                          <UserRound size={9} className="mr-1 inline" />
                          {ticket.assignee}
                        </p>
                      )}
                    </td>
                    <td className="py-3 pr-3 text-slate-500">{ticket.category}</td>
                    <td className="py-3 pr-3">
                      <Badge className={PRIORITY_STYLES[ticket.priority] || PRIORITY_STYLES.中}>
                        {ticket.priority}
                      </Badge>
                    </td>
                    <td className="py-3 pr-3">
                      <Badge className={STATUS_STYLES[ticket.status] || STATUS_STYLES["待处理"]}>
                        {ticket.status}
                      </Badge>
                    </td>
                    <td className="py-3 pr-3 text-[10px] text-slate-400">
                      {ticket.updated_at}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => openDetail(ticket)}
                          className="rounded-lg px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-100"
                        >
                          详情
                        </button>
                        {NEXT_STATUS[ticket.status] && (
                          <button
                            onClick={() => advance(ticket)}
                            className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2 py-1 text-[11px] font-medium text-indigo-600 hover:bg-indigo-100"
                          >
                            {NEXT_STATUS[ticket.status]}
                            <ArrowRight size={11} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!tickets.length && !loading && (
              <EmptyState
                icon={Ticket}
                title={status ? `没有“${status}”状态的工单` : "暂无工单"}
                description="点击右上角“新建工单”，描述你遇到的问题。"
                action={
                  <Button size="sm" onClick={() => setCreateOpen(true)}>
                    <Plus size={14} />
                    新建工单
                  </Button>
                }
              />
            )}
            {loading && (
              <div className="flex h-24 items-center justify-center gap-2 text-xs text-slate-400">
                <LoaderCircle size={15} className="animate-spin" /> 正在加载工单…
              </div>
            )}
          </div>
        </Card>
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建工单"
        subtitle="描述故障或服务请求，提交后会进入待处理队列"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button size="sm" onClick={createTicket} disabled={saving}>
              {saving ? <Spinner size={14} /> : <Plus size={14} />}
              提交工单
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="问题描述" hint="必填">
            <textarea
              value={form.issue}
              onChange={(event) => setForm((current) => ({ ...current, issue: event.target.value }))}
              rows={4}
              placeholder="例如：办公电脑开机蓝屏，无法进入系统"
              className={inputClass}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="分类">
              <select
                value={form.category}
                onChange={(event) =>
                  setForm((current) => ({ ...current, category: event.target.value }))
                }
                className={selectClass}
              >
                {(meta.categories || []).map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="优先级">
              <select
                value={form.priority}
                onChange={(event) =>
                  setForm((current) => ({ ...current, priority: event.target.value }))
                }
                className={selectClass}
              >
                {(meta.priorities || ["高", "中", "低"]).map((priority) => (
                  <option key={priority} value={priority}>
                    {priority}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `工单 #${selected.id}` : ""}
        subtitle={selected?.created_at}
        wide
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setSelected(null)}>
              关闭
            </Button>
            <Button size="sm" onClick={saveDetail} disabled={saving}>
              {saving ? <Spinner size={14} /> : <CheckCircle2 size={14} />}
              保存变更
            </Button>
          </>
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={STATUS_STYLES[selected.status] || STATUS_STYLES["待处理"]}>
                  {selected.status}
                </Badge>
                <Badge className={PRIORITY_STYLES[selected.priority] || PRIORITY_STYLES.中}>
                  优先级 {selected.priority}
                </Badge>
                <span className="text-[11px] text-slate-500">{selected.category}</span>
                {selected.assignee && (
                  <span className="text-[11px] text-slate-500">
                    · 处理人 {selected.assignee}
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm leading-7 text-slate-700">{selected.issue}</p>
              {selected.resolution && (
                <p className="mt-2 rounded-lg bg-white p-2.5 text-xs leading-6 text-slate-500">
                  处理结果：{selected.resolution}
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="状态">
                <select
                  value={detailForm.status}
                  onChange={(event) =>
                    setDetailForm((current) => ({ ...current, status: event.target.value }))
                  }
                  className={selectClass}
                >
                  {(meta.statuses || ["待处理", "处理中", "已解决", "已关闭"]).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="优先级">
                <select
                  value={detailForm.priority}
                  onChange={(event) =>
                    setDetailForm((current) => ({ ...current, priority: event.target.value }))
                  }
                  className={selectClass}
                >
                  {(meta.priorities || ["高", "中", "低"]).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="处理人">
              <input
                value={detailForm.assignee}
                onChange={(event) =>
                  setDetailForm((current) => ({ ...current, assignee: event.target.value }))
                }
                placeholder="例如：IT服务台-王工"
                className={inputClass}
              />
            </Field>

            <Field label="处理结果 / 备注">
              <textarea
                value={detailForm.resolution}
                onChange={(event) =>
                  setDetailForm((current) => ({ ...current, resolution: event.target.value }))
                }
                rows={3}
                placeholder="记录处理过程或结论"
                className={inputClass}
              />
            </Field>

            <p className="text-[10px] text-slate-400">
              创建时间：{selected.created_at} · 更新时间：{selected.updated_at}
            </p>
          </div>
        )}
      </Modal>
    </main>
  );
}
