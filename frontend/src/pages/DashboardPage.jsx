import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Brain,
  CalendarDays,
  CircleDollarSign,
  Clock3,
  Database,
  Lightbulb,
  Menu,
  Package,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Ticket,
  TrendingDown,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import { api } from "../lib/api";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  STATUS_STYLES,
} from "../lib/format";
import { BarList, DonutChart, LineChart } from "../components/Charts";
import { Button, Card, EmptyState, SectionTitle, Spinner, StatCard } from "../components/ui";

const STATUS_ICON = {
  待处理: Clock3,
  处理中: RefreshCw,
  已解决: TrendingUp,
  已关闭: TrendingDown,
};

const INSIGHT_SEVERITY = {
  high: {
    label: "高优先级",
    box: "border-rose-200 bg-rose-50/70",
    badge: "bg-rose-100 text-rose-700",
  },
  medium: {
    label: "需关注",
    box: "border-amber-200 bg-amber-50/70",
    badge: "bg-amber-100 text-amber-700",
  },
  low: {
    label: "健康",
    box: "border-emerald-200 bg-emerald-50/70",
    badge: "bg-emerald-100 text-emerald-700",
  },
};

export default function DashboardPage({ onNavigate, onOpenMenu, health, userId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [insightsError, setInsightsError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.dashboard();
      setData(result);
    } catch (requestError) {
      setError(requestError.message || "加载仪表盘失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadInsights = useCallback(async (force = false) => {
    setInsightsLoading(true);
    setInsightsError("");
    try {
      const result = await api.insights(force);
      setInsights(result);
    } catch (requestError) {
      setInsightsError(requestError.message || "生成 AI 洞察失败");
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadInsights();
  }, [load, loadInsights]);

  const kpis = data?.kpis || {};
  const trend = data?.sales_trend || [];
  const mom = data?.month_over_month?.growth ?? null;
  const categories = data?.categories || [];
  const products = data?.top_products || [];
  const orders = data?.recent_orders || [];
  const tickets = data?.tickets || {};
  const company = data?.company_profile?.[0];
  const statusItems = (data?.order_status || []).map((item) => ({
    label: item.status,
    value: item.orders,
    amount: item.amount,
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
              WORKSPACE OVERVIEW
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-900 md:text-2xl">
              企业运营工作台
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              京东商城业务演示库 · 2026 年 1—10 月 · 当前用户 {userId}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
            刷新数据
          </Button>
          <Button size="sm" onClick={() => onNavigate("chat")}>
            <Sparkles size={14} />
            开始问答
          </Button>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-7">
        {error && (
          <Card className="mb-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            {error}
            <button onClick={load} className="ml-2 underline">
              重试
            </button>
          </Card>
        )}

        {loading && !data ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((item) => (
              <Card key={item} className="h-[132px] animate-pulse p-5">
                <div className="h-3 w-20 rounded bg-slate-100" />
                <div className="mt-4 h-7 w-32 rounded bg-slate-100" />
                <div className="mt-3 h-3 w-24 rounded bg-slate-100" />
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="有效销售额"
              value={formatCurrency(kpis.revenue, true)}
              hint={`${formatCurrency(kpis.revenue)} · 已完成/已发货`}
              icon={CircleDollarSign}
              tone="indigo"
              trend={mom}
            />
            <StatCard
              label="有效订单"
              value={formatNumber(kpis.orders)}
              hint={`总订单 ${formatNumber(kpis.total_orders)} · 有效率 ${formatPercent(kpis.valid_order_ratio)}`}
              icon={ShoppingBag}
              tone="blue"
            />
            <StatCard
              label="成交客户"
              value={formatNumber(kpis.customers)}
              hint={`商品 ${formatNumber(kpis.units)} 件 · 客单价 ${formatCurrency(kpis.aov)}`}
              icon={Users}
              tone="emerald"
            />
            <StatCard
              label="毛利 / 毛利率"
              value={formatCurrency(kpis.gross_profit, true)}
              hint={`毛利率 ${formatPercent(kpis.gross_margin)} · 数据口径见设置页`}
              icon={Wallet}
              tone="amber"
            />
          </div>
        )}

        <Card className="mt-4 overflow-hidden border-indigo-100 bg-indigo-50/50 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
                <Brain size={20} />
              </div>
              <div>
                <p className="text-[10px] font-semibold tracking-[0.18em] text-indigo-600">
                  AGENTIC INSIGHT
                </p>
                <h3 className="text-sm font-bold text-slate-900">AI 经营洞察</h3>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  模型分析真实经营统计，给出发现、证据与建议
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {insights?.cached && (
                <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500">
                  缓存结果
                </span>
              )}
              {insights?.fallback && (
                <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-700">
                  规则兜底
                </span>
              )}
              {insights?.confidence !== undefined && (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] text-emerald-700">
                  <ShieldCheck size={11} />
                  置信度 {(Number(insights.confidence) * 100).toFixed(0)}%
                </span>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => loadInsights(true)}
                disabled={insightsLoading}
              >
                {insightsLoading ? <Spinner size={13} /> : <RefreshCw size={13} />}
                重新分析
              </Button>
            </div>
          </div>

          {insightsLoading && !insights ? (
            <div className="mt-5 space-y-3">
              <div className="h-6 w-3/4 animate-pulse rounded bg-indigo-100/70" />
              <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="h-28 animate-pulse rounded-xl bg-white/70" />
                ))}
              </div>
            </div>
          ) : insightsError && !insights ? (
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              <Lightbulb size={15} />
              {insightsError}
              <button onClick={() => loadInsights(true)} className="ml-auto underline">
                重试
              </button>
            </div>
          ) : insights ? (
            <>
              <h4 className="mt-4 break-words text-lg font-bold leading-7 text-slate-900">
                {insights.headline}
              </h4>
              <p className="mt-1.5 max-w-4xl break-words text-xs leading-6 text-slate-600">
                {insights.summary}
              </p>

              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                {(insights.insights || []).slice(0, 3).map((item, index) => {
                  const style = INSIGHT_SEVERITY[item.severity] || INSIGHT_SEVERITY.medium;
                  return (
                    <div
                      key={`${item.title}-${index}`}
                      className={`min-w-0 rounded-xl border p-3.5 ${style.box}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="shrink-0 text-[10px] font-bold text-slate-400">
                          0{index + 1}
                        </span>
                        <p className="min-w-0 flex-1 truncate text-xs font-semibold text-slate-800">
                          {item.title}
                        </p>
                        <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${style.badge}`}>
                          {style.label}
                        </span>
                      </div>
                      <p className="mt-2 break-words text-[11px] font-medium leading-5 text-slate-700">
                        {item.finding}
                      </p>
                      <p className="mt-1.5 break-words text-[10px] leading-5 text-slate-500">
                        证据：{item.evidence}
                      </p>
                      <p className="mt-2 break-words border-t border-white/70 pt-2 text-[10px] leading-5 text-indigo-700">
                        建议：{item.action}
                      </p>
                    </div>
                  );
                })}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 break-words text-[10px] text-slate-400">
                <span>生成时间：{insights.generated_at}</span>
                <span>数据区间：{insights.data_period}</span>
                <span>模型：{insights.model}</span>
                {insights.risks?.length > 0 && (
                  <span className="w-full text-rose-500">
                    风险：{insights.risks.join("；")}
                  </span>
                )}
              </div>
            </>
          ) : null}
        </Card>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="p-5 xl:col-span-2">
            <SectionTitle
              title="月度销售趋势"
              subtitle="有效订单销售额（元），2026 年 1—10 月"
              action={
                mom !== null && (
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                      Number(mom) >= 0
                        ? "bg-emerald-50 text-emerald-600"
                        : "bg-rose-50 text-rose-600"
                    }`}
                  >
                    {Number(mom) >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                    {Number(mom) >= 0 ? "+" : ""}
                    {Number(mom).toFixed(1)}% 环比
                  </span>
                )
              }
            />
            <div className="mt-4">
              <LineChart data={trend} />
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="订单状态分布" subtitle="全部订单（含待付款与取消）" />
            <div className="mt-5">
              <DonutChart
                items={statusItems}
                labelKey="label"
                valueKey="value"
                centerLabel="订单总数"
                centerValue={formatNumber(kpis.total_orders)}
                valueFormatter={(value) => `${formatNumber(value)} 单`}
              />
            </div>
          </Card>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="p-5">
            <SectionTitle
              title="品类销售结构"
              subtitle="按有效销售额排序"
              action={
                <button
                  onClick={() => onNavigate("analytics")}
                  className="text-[11px] font-medium text-indigo-600 hover:underline"
                >
                  查看全部
                </button>
              }
            />
            <div className="mt-5">
              <BarList
                items={categories}
                labelKey="category"
                valueKey="revenue"
                maxItems={6}
                valueFormatter={(value) => formatCurrency(value, true)}
              />
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle
              title="热销商品"
              subtitle="按有效销售额排序 Top 6"
              action={
                <button
                  onClick={() => onNavigate("analytics")}
                  className="text-[11px] font-medium text-indigo-600 hover:underline"
                >
                  商品排行
                </button>
              }
            />
            <div className="mt-4 space-y-3">
              {products.slice(0, 6).map((product, index) => (
                <div key={product.product_name} className="flex items-center gap-3">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ${
                      index < 3
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-700">
                      {product.product_name}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-400">
                      {product.category} · 销量 {formatNumber(product.units)}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs font-semibold text-slate-700">
                    {formatCurrency(product.revenue, true)}
                  </span>
                </div>
              ))}
              {!products.length && <EmptyState title="暂无商品数据" />}
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle
              title="工单服务概览"
              subtitle={`待处理 ${tickets.by_status?.待处理 ?? 0} · 处理中 ${tickets.by_status?.处理中 ?? 0}`}
              action={
                <button
                  onClick={() => onNavigate("tickets")}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:underline"
                >
                  进入工单中心 <ArrowRight size={12} />
                </button>
              }
            />
            <div className="mt-4 grid grid-cols-2 gap-3">
              {["待处理", "处理中", "已解决", "已关闭"].map((status) => {
                const Icon = STATUS_ICON[status] || Ticket;
                return (
                  <div
                    key={status}
                    className={`rounded-xl border p-3 ${STATUS_STYLES[status] || "border-slate-200 bg-slate-50 text-slate-600"}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-medium">{status}</span>
                      <Icon size={13} />
                    </div>
                    <p className="mt-2 text-xl font-bold">
                      {formatNumber(tickets.by_status?.[status] ?? 0)}
                    </p>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2.5 text-[11px] text-slate-500">
              <span>解决率</span>
              <span className="font-semibold text-emerald-600">
                {formatPercent(tickets.resolve_rate ?? 0)}
              </span>
            </div>
          </Card>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card className="p-5">
            <SectionTitle
              title="最近订单"
              subtitle="按下单日期倒序"
              action={
                <button
                  onClick={() => onNavigate("analytics")}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:underline"
                >
                  订单明细 <ArrowRight size={12} />
                </button>
              }
            />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                    <th className="pb-2 pr-3 font-medium">订单号</th>
                    <th className="pb-2 pr-3 font-medium">客户</th>
                    <th className="pb-2 pr-3 font-medium">金额</th>
                    <th className="pb-2 font-medium">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.order_id} className="border-b border-slate-50 last:border-0">
                      <td className="py-2.5 pr-3 font-mono text-[10px] text-slate-500">
                        {order.order_no}
                      </td>
                      <td className="py-2.5 pr-3">
                        <p className="text-slate-700">{order.customer_name}</p>
                        <p className="text-[10px] text-slate-400">
                          {order.customer_city} · {order.sales_rep || "—"}
                        </p>
                      </td>
                      <td className="py-2.5 pr-3 font-semibold text-slate-700">
                        {formatCurrency(order.total_amount, true)}
                      </td>
                      <td className="py-2.5">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] ${
                            STATUS_STYLES[order.status] ||
                            "border-slate-200 bg-slate-50 text-slate-500"
                          }`}
                        >
                          {order.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!orders.length && <EmptyState title="暂无订单" />}
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="数据资产概览" subtitle="当前工作区的数据与索引状态" />
            <div className="mt-4 grid grid-cols-2 gap-3">
              {[
                {
                  icon: Database,
                  label: "业务表",
                  value: "7 张",
                  hint: "订单 / 客户 / 商品 / 集团业绩",
                },
                {
                  icon: Package,
                  label: "商品",
                  value: formatNumber(health?.components?.business_db?.products),
                  hint: "10 个品类",
                },
                {
                  icon: Users,
                  label: "客户",
                  value: formatNumber(health?.components?.business_db?.customers),
                  hint: "10 个城市",
                },
                {
                  icon: CalendarDays,
                  label: "数据区间",
                  value: "2026.01—10",
                  hint: "覆盖 618 与 11.11 预热",
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="rounded-xl border border-slate-100 p-3">
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <Icon size={14} className="text-indigo-500" />
                      {item.label}
                    </div>
                    <p className="mt-2 text-base font-bold text-slate-800">{item.value}</p>
                    <p className="mt-0.5 text-[10px] text-slate-400">{item.hint}</p>
                  </div>
                );
              })}
            </div>
            {company && (
              <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold text-slate-600">
                    集团公开业绩 · {company.fiscal_year}
                  </p>
                  <span className="text-[9px] text-slate-400">来源：公开财报报道</span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-[10px] text-slate-400">全年营收</p>
                    <p className="text-sm font-bold text-slate-700">
                      {formatNumber(company.revenue)}
                      <span className="ml-1 text-[10px] font-normal text-slate-400">亿元</span>
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-400">归母净利润</p>
                    <p className="text-sm font-bold text-slate-700">
                      {formatNumber(company.net_profit)}
                      <span className="ml-1 text-[10px] font-normal text-slate-400">亿元</span>
                    </p>
                  </div>
                </div>
              </div>
            )}
            <div className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold text-indigo-700">
                <BarChart3 size={13} />
                数据说明
              </div>
              <p className="mt-1.5 text-[10px] leading-5 text-indigo-700/70">
                客户、员工与订单为固定种子的演示数据；商品品类与部分参考价来自京东公开商品信息。
                统计口径为“已完成 / 已发货”订单。
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="mt-4 w-full"
              onClick={() => onNavigate("settings")}
            >
              查看系统与数据口径
              <ArrowRight size={13} />
            </Button>
          </Card>
        </div>
      </div>
    </main>
  );
}


