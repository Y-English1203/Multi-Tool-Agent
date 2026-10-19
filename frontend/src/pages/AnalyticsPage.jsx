import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Database,
  LoaderCircle,
  MapPin,
  Menu,
  RefreshCw,
  Search,
  Send,
  Sparkles,
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
import DataTable from "../components/DataTable";
import {
  Button,
  Card,
  EmptyState,
  SectionTitle,
  Spinner,
  StatCard,
  Tabs,
} from "../components/ui";

const TABS = [
  { key: "overview", label: "经营概览" },
  { key: "structure", label: "品类与区域" },
  { key: "products", label: "商品排行" },
  { key: "orders", label: "订单明细" },
  { key: "ask", label: "智能问数" },
];

const NL_PROMPTS = [
  "销售额最高的品类是什么？",
  "上个月订单量是多少？",
  "哪个城市的客户下单最多？",
  "客单价是多少？",
  "各事业部的销售额排名",
  "本月销量最高的商品是什么？",
];

const emptyFilters = { start: "", end: "" };

export default function AnalyticsPage({ onNavigate, onOpenMenu }) {
  const [tab, setTab] = useState("overview");
  const [filters, setFilters] = useState(emptyFilters);
  const [applied, setApplied] = useState(emptyFilters);
  const [metric, setMetric] = useState("revenue");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const params = useMemo(
    () => ({ start: applied.start || undefined, end: applied.end || undefined }),
    [applied]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [
        overview,
        trend,
        categories,
        products,
        cities,
        departments,
        orderStatus,
        channelData,
      ] = await Promise.all([
        api.overview(params),
        api.trend({ months: 12, ...params }),
        api.categories(params),
        api.topProducts({ limit: 20, metric, ...params }),
        api.cities(params),
        api.departments(params),
        api.orderStatus(),
        api.channels(),
      ]);

      setData({ overview, trend, categories, products, cities, departments, orderStatus, channels: channelData });
    } catch (requestError) {
      setError(requestError.message || "加载分析数据失败");
    } finally {
      setLoading(false);
    }
  }, [params, metric]);

  useEffect(() => {
    load();
  }, [load]);

  const overview = data?.overview || {};
  const categories = data?.categories || [];
  const cities = data?.cities || [];
  const departments = data?.departments || [];
  const products = data?.products || [];
  const trend = data?.trend || [];
  const orderStatus = data?.orderStatus || [];
  const channels = data?.channels || [];

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-[#f7f8fc]">
      <header className="flex shrink-0 flex-col gap-4 border-b border-slate-200/80 bg-white px-4 py-5 md:px-7">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
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
                BUSINESS ANALYTICS
              </p>
              <h1 className="mt-1 text-xl font-bold text-slate-900 md:text-2xl">
                数据分析
              </h1>
              <p className="mt-1 text-xs text-slate-400">
                用自然语言或可视化图表分析订单、商品、客户与事业部表现
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
              {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
              刷新
            </Button>
            <Button size="sm" onClick={() => onNavigate("chat")}>
              <Sparkles size={14} />
              去问答
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[11px] text-slate-500">
              开始日期
              <input
                type="date"
                value={filters.start}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, start: event.target.value }))
                }
                className="ml-2 rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-600 outline-none focus:border-indigo-300"
              />
            </label>
            <label className="text-[11px] text-slate-500">
              结束日期
              <input
                type="date"
                value={filters.end}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, end: event.target.value }))
                }
                className="ml-2 rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-600 outline-none focus:border-indigo-300"
              />
            </label>
            <Button size="sm" onClick={() => setApplied(filters)}>
              应用
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setFilters(emptyFilters);
                setApplied(emptyFilters);
              }}
            >
              重置
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-7">
        {error && (
          <Card className="mb-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            {error}
          </Card>
        )}

        {loading && !data ? (
          <div className="flex h-64 items-center justify-center gap-3 text-sm text-slate-400">
            <LoaderCircle size={18} className="animate-spin" />
            正在加载业务数据…
          </div>
        ) : (
          <>
            {tab === "overview" && (
              <OverviewTab
                overview={overview}
                trend={trend}
                categories={categories}
                cities={cities}
                orderStatus={orderStatus}
                channels={channels}
              />
            )}

            {tab === "structure" && (
              <StructureTab
                categories={categories}
                cities={cities}
                departments={departments}
                channels={channels}
              />
            )}

            {tab === "products" && (
              <ProductsTab
                products={products}
                metric={metric}
                onMetricChange={setMetric}
              />
            )}

            {tab === "orders" && <OrdersTab />}

            {tab === "ask" && <AskTab />}
          </>
        )}
      </div>
    </main>
  );
}

function OverviewTab({ overview, trend, categories, cities, orderStatus, channels }) {
  const statusItems = orderStatus.map((item) => ({
    label: item.status,
    value: item.orders,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="有效销售额"
          value={formatCurrency(overview.revenue, true)}
          hint={formatCurrency(overview.revenue)}
          icon={Wallet}
          tone="indigo"
        />
        <StatCard
          label="有效订单数"
          value={formatNumber(overview.orders)}
          hint={`总订单 ${formatNumber(overview.total_orders)}`}
          icon={BarChart3}
          tone="blue"
        />
        <StatCard
          label="客单价"
          value={formatCurrency(overview.aov)}
          hint={`成交客户 ${formatNumber(overview.customers)}`}
          icon={Users}
          tone="emerald"
        />
        <StatCard
          label="毛利率"
          value={formatPercent(overview.gross_margin)}
          hint={`毛利 ${formatCurrency(overview.gross_profit, true)}`}
          icon={TrendingUp}
          tone="amber"
        />
      </div>

      <Card className="p-5">
        <SectionTitle
          title="销售趋势"
          subtitle="有效订单销售额与订单量，按月份聚合"
          action={<span className="text-[11px] text-slate-400">金额单位：元</span>}
        />
        <div className="mt-4">
          <LineChart data={trend} height={260} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="p-5">
          <SectionTitle title="品类结构" subtitle="按销售额占比" />
          <div className="mt-5">
            <DonutChart
              items={categories}
              labelKey="category"
              valueKey="revenue"
              centerLabel="销售额"
              centerValue={formatCurrency(overview.revenue, true)}
            />
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="城市销售 Top 8" subtitle="按有效订单销售额" />
          <div className="mt-5">
            <BarList
              items={cities}
              labelKey="city"
              valueKey="revenue"
              maxItems={8}
              valueFormatter={(value) => formatCurrency(value, true)}
            />
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="渠道与状态" subtitle="订单来源与履约状态" />
          <div className="mt-5 space-y-4">
            <div>
              <p className="mb-2 text-[11px] font-semibold text-slate-500">下单渠道</p>
              <div className="space-y-2">
                {channels.slice(0, 5).map((channel) => (
                  <div key={channel.channel} className="flex items-center justify-between text-xs">
                    <span className="text-slate-600">{channel.channel}</span>
                    <span className="font-medium text-slate-700">
                      {formatCurrency(channel.revenue, true)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <div className="flex flex-wrap gap-2">
                {statusItems.map((item) => (
                  <span
                    key={item.label}
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${
                      STATUS_STYLES[item.label] ||
                      "border-slate-200 bg-slate-50 text-slate-500"
                    }`}
                  >
                    {item.label}
                    <b>{formatNumber(item.value)}</b>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function StructureTab({ categories, cities, departments, channels }) {
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <SectionTitle title="品类表现" subtitle="销售额、销量与订单数" />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                <th className="pb-2 pr-3 font-medium">品类</th>
                <th className="pb-2 pr-3 text-right font-medium">销售额</th>
                <th className="pb-2 pr-3 text-right font-medium">占比</th>
                <th className="pb-2 pr-3 text-right font-medium">销量</th>
                <th className="pb-2 text-right font-medium">订单数</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((item) => (
                <tr key={item.category} className="border-b border-slate-50 last:border-0">
                  <td className="py-2.5 pr-3 font-medium text-slate-700">{item.category}</td>
                  <td className="py-2.5 pr-3 text-right text-slate-600">
                    {formatCurrency(item.revenue)}
                  </td>
                  <td className="py-2.5 pr-3 text-right text-slate-500">
                    {formatPercent(item.share)}
                  </td>
                  <td className="py-2.5 pr-3 text-right text-slate-600">
                    {formatNumber(item.units)}
                  </td>
                  <td className="py-2.5 text-right text-slate-600">
                    {formatNumber(item.orders)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="p-5">
          <SectionTitle title="城市分布" subtitle="客户所在城市" />
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="pb-2 pr-3 font-medium">城市</th>
                  <th className="pb-2 pr-3 text-right font-medium">销售额</th>
                  <th className="pb-2 pr-3 text-right font-medium">订单</th>
                  <th className="pb-2 text-right font-medium">客户</th>
                </tr>
              </thead>
              <tbody>
                {cities.map((item) => (
                  <tr key={item.city} className="border-b border-slate-50 last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-slate-700">
                      <span className="inline-flex items-center gap-1.5">
                        <MapPin size={12} className="text-indigo-400" />
                        {item.city}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-right text-slate-600">
                      {formatCurrency(item.revenue, true)}
                    </td>
                    <td className="py-2.5 pr-3 text-right text-slate-600">
                      {formatNumber(item.orders)}
                    </td>
                    <td className="py-2.5 text-right text-slate-600">
                      {formatNumber(item.customers)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <SectionTitle title="事业部业绩" subtitle="按销售额排序" />
            <div className="mt-4 space-y-3">
              {departments.map((item, index) => (
                <div key={item.department}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-slate-600">
                      {index + 1}. {item.department}
                    </span>
                    <span className="font-medium text-slate-700">
                      {formatCurrency(item.revenue, true)}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{ width: `${Math.max(item.share, 2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle title="渠道销售" subtitle="各下单渠道有效销售额" />
            <div className="mt-4">
              <BarList
                items={channels}
                labelKey="channel"
                valueKey="revenue"
                maxItems={6}
                color="bg-blue-500"
                valueFormatter={(value) => formatCurrency(value, true)}
              />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function ProductsTab({ products, metric, onMetricChange }) {
  return (
    <Card className="p-5">
      <SectionTitle
        title="商品排行"
        subtitle="按有效订单统计，支持销售额与销量两种口径"
        action={
          <div className="flex rounded-lg bg-slate-100 p-1">
            {[
              { key: "revenue", label: "按销售额" },
              { key: "units", label: "按销量" },
            ].map((option) => (
              <button
                key={option.key}
                onClick={() => onMetricChange(option.key)}
                className={`rounded-md px-3 py-1.5 text-[11px] font-medium transition ${
                  metric === option.key
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-500"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
              <th className="pb-2 pr-3 font-medium">#</th>
              <th className="pb-2 pr-3 font-medium">商品</th>
              <th className="pb-2 pr-3 font-medium">品类</th>
              <th className="pb-2 pr-3 text-right font-medium">销售额</th>
              <th className="pb-2 pr-3 text-right font-medium">销量</th>
              <th className="pb-2 text-right font-medium">订单数</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product, index) => (
              <tr key={product.product_name} className="border-b border-slate-50 last:border-0">
                <td className="py-2.5 pr-3">
                  <span
                    className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${
                      index < 3 ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {index + 1}
                  </span>
                </td>
                <td className="py-2.5 pr-3">
                  <p className="font-medium text-slate-700">{product.product_name}</p>
                  <p className="text-[10px] text-slate-400">{product.brand}</p>
                </td>
                <td className="py-2.5 pr-3 text-slate-500">{product.category}</td>
                <td className="py-2.5 pr-3 text-right font-semibold text-slate-700">
                  {formatCurrency(product.revenue)}
                </td>
                <td className="py-2.5 pr-3 text-right text-slate-600">
                  {formatNumber(product.units)}
                </td>
                <td className="py-2.5 text-right text-slate-600">
                  {formatNumber(product.orders)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!products.length && <EmptyState title="暂无商品排行数据" />}
      </div>
    </Card>
  );
}

function OrdersTab() {
  const [filters, setFilters] = useState({ status: "", keyword: "", city: "" });
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [options, setOptions] = useState({ cities: [], statuses: [] });

  useEffect(() => {
    api.filters().then(setOptions).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.orders({
        page,
        size: 15,
        status: filters.status || undefined,
        keyword: filters.keyword || undefined,
        city: filters.city || undefined,
      });
      setResult(data);
    } catch (requestError) {
      setError(requestError.message || "加载订单失败");
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  const items = result?.items || [];

  return (
    <Card className="p-5">
      <SectionTitle
        title="订单明细"
        subtitle={`共 ${formatNumber(result?.total)} 笔订单，按日期倒序`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
              <input
                value={filters.keyword}
                onChange={(event) => {
                  setPage(1);
                  setFilters((current) => ({ ...current, keyword: event.target.value }));
                }}
                placeholder="订单号 / 客户 / 销售"
                className="w-44 rounded-lg border border-slate-200 py-1.5 pl-8 pr-2 text-xs outline-none focus:border-indigo-300"
              />
            </div>
            <select
              value={filters.status}
              onChange={(event) => {
                setPage(1);
                setFilters((current) => ({ ...current, status: event.target.value }));
              }}
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-600 outline-none"
            >
              <option value="">全部状态</option>
              {(options.statuses || []).map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
            <select
              value={filters.city}
              onChange={(event) => {
                setPage(1);
                setFilters((current) => ({ ...current, city: event.target.value }));
              }}
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-600 outline-none"
            >
              <option value="">全部城市</option>
              {(options.cities || []).map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {error && <p className="mt-3 text-xs text-rose-600">{error}</p>}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
              <th className="pb-2 pr-3 font-medium">订单号</th>
              <th className="pb-2 pr-3 font-medium">日期</th>
              <th className="pb-2 pr-3 font-medium">客户 / 城市</th>
              <th className="pb-2 pr-3 font-medium">销售 / 事业部</th>
              <th className="pb-2 pr-3 text-right font-medium">金额</th>
              <th className="pb-2 font-medium">状态</th>
            </tr>
          </thead>
          <tbody>
            {items.map((order) => (
              <tr key={order.order_id} className="border-b border-slate-50 last:border-0">
                <td className="py-2.5 pr-3 font-mono text-[10px] text-slate-500">
                  {order.order_no}
                </td>
                <td className="py-2.5 pr-3 text-slate-500">{order.order_date}</td>
                <td className="py-2.5 pr-3">
                  <p className="text-slate-700">{order.customer_name}</p>
                  <p className="text-[10px] text-slate-400">{order.customer_city}</p>
                </td>
                <td className="py-2.5 pr-3">
                  <p className="text-slate-600">{order.sales_rep || "—"}</p>
                  <p className="text-[10px] text-slate-400">{order.department || "—"}</p>
                </td>
                <td className="py-2.5 pr-3 text-right font-semibold text-slate-700">
                  {formatCurrency(order.total_amount)}
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
        {!items.length && !loading && <EmptyState title="没有符合条件的订单" />}
        {loading && (
          <div className="flex h-20 items-center justify-center gap-2 text-xs text-slate-400">
            <LoaderCircle size={15} className="animate-spin" /> 加载中…
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-500">
        <span>
          第 {result?.page || 1} / {result?.pages || 1} 页
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={(result?.page || 1) <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            <ArrowLeft size={13} /> 上一页
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={(result?.page || 1) >= (result?.pages || 1)}
            onClick={() => setPage((current) => current + 1)}
          >
            下一页 <ArrowRight size={13} />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AskTab() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(text = question) {
    const value = String(text || "").trim();
    if (!value || loading) return;
    setQuestion(value);
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.sqlQuery(value);
      setResult(data);
      if (data.error && data.error !== "cannot_answer") {
        setError(data.error);
      }
    } catch (requestError) {
      setError(requestError.message || "查询失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Card className="p-5 xl:col-span-2">
        <SectionTitle
          title="自然语言问数"
          subtitle="问题会被转换为只读 SQL，并在真实业务库执行"
          action={
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] text-emerald-600">
              <Database size={11} /> 只读查询
            </span>
          }
        />

        <div className="mt-4 flex items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                run();
              }
            }}
            rows={2}
            placeholder="例如：上个月销售额最高的品类是什么？"
            className="min-h-12 flex-1 resize-y bg-transparent px-3 py-2 text-sm leading-6 outline-none"
          />
          <Button onClick={() => run()} disabled={loading || !question.trim()}>
            {loading ? <Spinner size={15} /> : <Send size={15} />}
            查询
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {NL_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => run(prompt)}
              disabled={loading}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-500 transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-5 space-y-4">
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4">
              <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-indigo-700">
                <Sparkles size={14} />
                分析结论
              </div>
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {result.answer}
              </p>
            </div>

            {result.columns?.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-600">查询结果</span>
                  <span className="text-[10px] text-slate-400">
                    {result.row_count} 行
                    {result.truncated ? "（已截断）" : ""}
                  </span>
                </div>
                <DataTable columns={result.columns} rows={result.rows} maxHeight="340px" />
              </div>
            )}

            {result.sql && (
              <details className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <summary className="cursor-pointer text-xs font-medium text-slate-600">
                  查看执行 SQL
                </summary>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-6 text-slate-600">
                  {result.sql}
                </pre>
              </details>
            )}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <SectionTitle title="可分析的数据" subtitle="业务库中的表与视图" />
        <div className="mt-4 space-y-3 text-xs">
          {[
            ["orders", "订单主表", "订单号、状态、渠道、金额"],
            ["order_items", "订单明细", "商品、数量、成交价"],
            ["products", "商品", "品类、品牌、参考价"],
            ["customers", "客户", "城市、会员等级"],
            ["employees", "销售员工", "岗位、入职日期"],
            ["departments", "事业部", "负责人、城市"],
            ["v_sales_line", "销售明细视图", "一行一个商品明细"],
            ["v_order_summary", "订单汇总视图", "一行一个订单"],
          ].map(([name, label, desc]) => (
            <div key={name} className="rounded-lg border border-slate-100 p-2.5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] text-indigo-600">{name}</span>
                <span className="text-[10px] text-slate-400">{label}</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">{desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-xl bg-amber-50 p-3 text-[10px] leading-5 text-amber-700">
          统计口径：销售额默认只统计“已完成 / 已发货”订单；客单价 = 有效销售额 / 有效订单数。
        </div>
      </Card>
    </div>
  );
}
