import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  Database,
  FileText,
  Layers,
  LoaderCircle,
  Menu,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Upload,
  UploadCloud,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";
import {
  Button,
  Card,
  EmptyState,
  SectionTitle,
  Spinner,
  StatCard,
} from "../components/ui";

export default function KnowledgePage({ onOpenMenu, onNavigate }) {
  const [stats, setStats] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [ready, setReady] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsData, docsData] = await Promise.all([
        api.knowledgeStats(),
        api.knowledgeDocuments(),
      ]);
      setStats(statsData);
      setDocuments(docsData.documents || []);
      setReady(Boolean(docsData.ready));
    } catch (requestError) {
      setError(requestError.message || "加载知识库失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function search(text = query) {
    const value = String(text || "").trim();
    if (!value || searching) return;
    setQuery(value);
    setSearching(true);
    setError("");
    try {
      const data = await api.knowledgeSearch(value, 5);
      setResults(data.results || []);
    } catch (requestError) {
      setError(requestError.message || "检索失败");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function upload(file) {
    if (!file || uploading) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("目前只支持上传 PDF 文档。");
      return;
    }
    setUploading(true);
    setError("");
    try {
      await api.uploadKnowledge(file);
      await load();
      setResults(null);
    } catch (requestError) {
      setError(requestError.message || "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(document) {
    if (!window.confirm(`确定删除《${document.filename}》及其索引吗？`)) return;
    setError("");
    try {
      await api.deleteKnowledge(document.id);
      await load();
      setResults(null);
    } catch (requestError) {
      setError(requestError.message || "删除失败");
    }
  }

  async function rebuild() {
    if (!window.confirm("重建索引需要重新计算全部文档向量，可能耗时数十秒，确定继续吗？")) {
      return;
    }
    setRebuilding(true);
    setError("");
    try {
      await api.rebuildKnowledge();
      await load();
    } catch (requestError) {
      setError(requestError.message || "重建索引失败");
    } finally {
      setRebuilding(false);
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) upload(file);
  }

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
              KNOWLEDGE BASE
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-900 md:text-2xl">知识库</h1>
            <p className="mt-1 text-xs text-slate-400">
              PDF 文档索引、混合检索与页码引用
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
            刷新
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={rebuild}
            disabled={rebuilding || !ready}
          >
            {rebuilding ? <Spinner size={14} /> : <RefreshCw size={14} />}
            重建索引
          </Button>
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Spinner size={14} /> : <Upload size={14} />}
            上传 PDF
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => upload(event.target.files?.[0])}
          />
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-7">
        {error && (
          <Card className="mb-4 flex items-start gap-2 border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
            <X size={15} className="mt-0.5 shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError("")} className="text-rose-400 hover:text-rose-600">
              关闭
            </button>
          </Card>
        )}

        {!ready && !loading && (
          <Card className="mb-4 border-amber-200 bg-amber-50 p-4 text-xs leading-6 text-amber-800">
            知识库当前不可用：{stats?.error || "Embedding 模型或索引尚未就绪"}。
            请确认模型缓存已下载，或在设置页查看服务状态。
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="文档数量"
            value={formatNumber(stats?.documents || 0)}
            hint="knowledge/ 目录"
            icon={FileText}
            tone="indigo"
          />
          <StatCard
            label="文档页数"
            value={formatNumber(stats?.pages || 0)}
            hint="PDF 有效文字页"
            icon={BookOpen}
            tone="blue"
          />
          <StatCard
            label="向量切片"
            value={formatNumber(stats?.chunks || 0)}
            hint={`chunk ${stats?.chunk_size || 500} / overlap ${stats?.chunk_overlap || 80}`}
            icon={Layers}
            tone="emerald"
          />
          <StatCard
            label="Embedding 模型"
            value={stats?.model ? stats.model.split("/").pop() : "—"}
            hint="BGE 中文向量模型"
            icon={Database}
            tone="violet"
            valueClassName="text-xl"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="p-5 xl:col-span-2">
            <SectionTitle
              title="知识检索"
              subtitle="向量语义检索，返回最相关的文档片段与页码"
              action={
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] text-emerald-600">
                  <CheckCircle2 size={11} />
                  {ready ? "索引就绪" : "索引异常"}
                </span>
              }
            />

            <div className="mt-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
              <Search size={16} className="ml-2 text-slate-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") search();
                }}
                placeholder="例如：员工申请病假需要什么材料？"
                className="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm text-slate-700 outline-none placeholder:text-slate-400"
              />
              <Button size="sm" onClick={() => search()} disabled={searching || !query.trim()}>
                {searching ? <Spinner size={14} /> : <Search size={14} />}
                检索
              </Button>
            </div>

            {results !== null && (
              <div className="mt-4 space-y-3">
                {results.length === 0 ? (
                  <EmptyState
                    icon={Search}
                    title="没有检索到相关片段"
                    description="尝试换一种问法，或确认知识库中已上传对应 PDF。"
                  />
                ) : (
                  results.map((item, index) => (
                    <div
                      key={`${item.source}-${item.page}-${index}`}
                      className="rounded-xl border border-slate-200 p-3.5 transition hover:border-indigo-200"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-1 text-[10px] font-medium text-indigo-700">
                          <FileText size={11} />
                          {item.source}
                        </span>
                        {item.page && (
                          <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] text-slate-600">
                            第 {item.page} 页
                          </span>
                        )}
                        <span className="ml-auto text-[10px] text-slate-400">
                          相关度 {(Number(item.score) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-4 text-xs leading-6 text-slate-600">
                        {item.content}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}

            {results === null && (
              <div className="mt-5 rounded-xl border border-dashed border-slate-200 p-6 text-center">
                <Sparkles size={22} className="mx-auto text-indigo-300" />
                <p className="mt-2 text-xs text-slate-500">
                  输入问题，检索《京东集团员工手册》中的相关条款
                </p>
                <p className="mt-1 text-[10px] text-slate-400">
                  检索结果会保留文档名与页码，可直接用于问答引用
                </p>
              </div>
            )}
          </Card>

          <Card className="flex flex-col p-5">
            <SectionTitle title="上传文档" subtitle="支持 PDF，最大 30MB" />
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              className={`mt-4 flex flex-1 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition ${
                dragging
                  ? "border-indigo-400 bg-indigo-50"
                  : "border-slate-200 bg-slate-50/60 hover:border-indigo-300"
              }`}
            >
              {uploading ? (
                <>
                  <LoaderCircle size={26} className="animate-spin text-indigo-500" />
                  <p className="mt-3 text-xs font-medium text-slate-600">
                    正在解析并建立索引…
                  </p>
                  <p className="mt-1 text-[10px] text-slate-400">
                    首次索引需要加载向量模型，请稍候
                  </p>
                </>
              ) : (
                <>
                  <UploadCloud size={28} className="text-indigo-400" />
                  <p className="mt-3 text-xs font-medium text-slate-600">
                    拖拽 PDF 到这里，或点击选择
                  </p>
                  <p className="mt-1 text-[10px] text-slate-400">
                    上传后会自动切片、向量化并加入检索
                  </p>
                </>
              )}
            </div>
            <div className="mt-4 rounded-xl bg-slate-50 p-3 text-[10px] leading-5 text-slate-500">
              知识库当前使用 BGE 中文向量模型；文档存储在 knowledge/，索引持久化在 chroma_db/。
            </div>
          </Card>
        </div>

        <Card className="mt-4 p-5">
          <SectionTitle
            title="文档列表"
            subtitle={`${documents.length} 个文档 · 索引目录 ${stats?.persist_dir || "chroma_db"}`}
            action={
              <Button variant="ghost" size="sm" onClick={() => onNavigate("chat")}>
                <Sparkles size={13} />
                用知识库提问
              </Button>
            }
          />
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="pb-2 pr-3 font-medium">文档</th>
                  <th className="pb-2 pr-3 text-right font-medium">页数</th>
                  <th className="pb-2 pr-3 text-right font-medium">切片</th>
                  <th className="pb-2 pr-3 text-right font-medium">大小</th>
                  <th className="pb-2 pr-3 font-medium">索引时间</th>
                  <th className="pb-2 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id} className="border-b border-slate-50 last:border-0">
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-50 text-rose-500">
                          <FileText size={15} />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-slate-700">
                            {document.filename}
                          </p>
                          <p className="truncate font-mono text-[9px] text-slate-400">
                            {document.id} · {document.sha256?.slice(0, 10)}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-3 text-right text-slate-600">
                      {formatNumber(document.pages)}
                    </td>
                    <td className="py-3 pr-3 text-right text-slate-600">
                      {formatNumber(document.chunks)}
                    </td>
                    <td className="py-3 pr-3 text-right text-slate-500">
                      {(Number(document.size) / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3 pr-3 text-slate-500">{document.indexed_at}</td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => remove(document)}
                        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-slate-400 transition hover:bg-rose-50 hover:text-rose-500"
                      >
                        <Trash2 size={12} />
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!documents.length && !loading && (
              <EmptyState
                icon={FileText}
                title="知识库中还没有文档"
                description="上传一份 PDF，或确认项目根目录的 test.pdf 是否存在。"
              />
            )}
          </div>
        </Card>
      </div>
    </main>
  );
}
