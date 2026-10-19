# Multi-Tool Agent 前端

React 19 + Vite 8 + Tailwind CSS 4 构建的企业智能知识中台工作台。

## 页面

- **工作台**：销售额、订单、客户、毛利 KPI，月度趋势、订单状态、品类结构、热销商品、工单概览
- **智能问答**：Supervisor 多 Agent 对话，展示工具、执行轨迹、页码来源、SQL 结果表格
- **知识库**：文档统计、语义检索、PDF 上传、删除、重建索引
- **数据分析**：经营概览、品类与区域、商品排行、订单明细、自然语言问数
- **工单中心**：工单统计、筛选、创建、状态流转、处理结果编辑
- **系统设置**：组件健康状态、用户身份、数据口径、会话清理

## 开发

```bash
npm install
npm run dev
```

开发服务器端口 `5173`，`vite.config.js` 已把 `/api`、`/ask`、`/debug`、`/health`
代理到 `http://127.0.0.1:8000`。

## 构建

```bash
npm run build
```

产物输出到 `dist/`，FastAPI 会在 `frontend/dist/index.html` 存在时自动托管前端。

## 代码结构

```text
src/
├── App.jsx                 # 页面路由（hash）、会话状态、健康轮询
├── components/
│   ├── Sidebar.jsx         # 侧栏导航与会话列表
│   ├── AgentPanel.jsx      # 右侧 Agent 运行面板
│   ├── Charts.jsx          # SVG 折线图 / 环形图 / 条形图
│   ├── DataTable.jsx       # SQL 结果与数据表格
│   ├── Markdown.jsx        # 轻量 Markdown + 页码引用渲染
│   └── ui.jsx              # Card / Button / Modal / StatCard 等
├── pages/                  # 六个页面
├── lib/
│   ├── api.js              # 统一 API 客户端
│   └── format.js           # 金额、百分比、状态样式
└── index.css               # Tailwind + 全局样式
```

## 页面路由

使用 hash 路由，可直接访问：

- `/#/dashboard`
- `/#/chat`
- `/#/knowledge`
- `/#/analytics`
- `/#/tickets`
- `/#/settings`

## 说明

- 会话保存在浏览器 `localStorage`，服务端同时按 `session_id` 保存对话记忆；
- 用户标识保存在 `localStorage` 的 `mta.user_id`，修改后聊天与工单按新身份隔离；
- 图表不依赖第三方图表库，使用原生 SVG 渲染。
