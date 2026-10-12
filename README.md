# 企业智能知识中台 —— Multi-Tool-Agent

基于 LangGraph 构建的企业级多 Agent 协作系统，面向企业内部知识问答、业务数据查询与工单管理场景，旨在降低文档检索与数据查询门槛，提升企业内部信息获取和业务处理效率。

## 核心功能

- **Supervisor 多 Agent 协作**：作为统一调度中心，根据用户请求的意图将任务路由至 RAG、Text-to-SQL 或 Ticket Agent。
- **混合检索与文档溯源**：结合 BM25 关键词检索与向量语义检索，通过 RRF 融合候选结果，并使用 Reranker 进行精排；支持 PDF 页码引用及检索来源返回。
- **Text-to-SQL Agent**：读取数据库真实 Schema，根据自然语言问题生成 SQL，执行业务数据查询与统计分析。
- **工单 Agent**：支持工单创建、状态查询，并通过 `user_id` 实现用户间的工单数据隔离。
- **多轮对话记忆**：基于 `session_id` 管理会话历史，支持结合上下文补全追问。
- **异常处理与调用追踪**：使用 Trace ID 关联请求日志，通过异常捕获和 RAG 重试机制提升运行稳定性。
- **REST API 服务**：基于 FastAPI 提供统一的 Agent 调用入口。

## 多 Agent 协作架构

```text
用户请求
   |
   v
Supervisor Agent
   |
   +-------------------+-------------------+
   |                   |                   |
   v                   v                   v
RAG Agent           SQL Agent          Ticket Agent
   |                   |                   |
   v                   v                   v
混合检索             Schema读取           工单创建
向量检索             SQL生成              工单查询
Reranker             SQL执行              权限隔离
   |                   |                   |
   +-------------------+-------------------+
                       |
                       v
                   统一返回结果
```

## 核心处理流程

### 1. RAG 文档问答

```text
PDF 文档
   |
   v
文本提取与分块
   |
   +--> BM25 关键词检索
   |
   +--> 向量语义检索
              |
              v
          RRF 融合
              |
              v
          Reranker 精排
              |
              v
       上下文构建与生成
              |
              v
       引用校验与来源返回
```

### 2. Text-to-SQL

```text
自然语言问题
     |
     v
读取数据库 Schema
     |
     v
生成 SQL
     |
     v
SQL 执行与结果处理
     |
     v
返回查询结果
```

### 3. 多轮对话记忆

用户请求
   |
   v
读取 session 历史
   |
   v
问题补全
   |
   v
Supervisor 意图判断
   |
   v
Agent 执行业务处理
   |
   v
保存对话消息

## 技术栈

- **语言**：Python
- **Agent 编排**：LangGraph
- **API 服务**：FastAPI
- **检索与 RAG**：LangChain、ChromaDB、BM25、RRF、Reranker
- **模型服务**：DeepSeek API
- **模型服务**：DeepSeek API、HuggingFace Embedding/Reranker 模型
- **数据存储**：SQLite


## 评估结果

基于《京东集团员工手册》及业务数据库构建 15 题自建评估集，其中包括 10 道文档问答题和 5 道业务数据查询题，并结合人工测试进行结果评估。

| 评估项目 | 测试题数 | 命中率 |
|---|---:|---:|
| 文档问答 | 10 | 100% |
| 数据查询 | 5 | 60% |
| 综合结果 | 15 | 约 86.7% |

数据查询中的错误主要涉及业务统计口径歧义、复杂查询条件理解以及跨表 JOIN 场景，后续可从 SQL 校验、Schema 约束和测试集扩充等方向继续优化。

**说明：** 以上结果仅反映当前自建测试集上的评估表现，不代表生产环境中的实际准确率。提交前请确认评估记录与表中数据一致。

## 快速开始

### 1. 环境准备

建议使用 Python 虚拟环境：

```bash
python -m venv .venv
```
Windows：
```bash
.venv\Scripts\activate
```
安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env`，填写实际使用的模型 API Key，例如：

```dotenv
DEEPSEEK_API_KEY=your_api_key
```

请勿将 `.env` 或真实 API Key 提交到 GitHub。

### 3. 启动服务

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```
浏览器访问：

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

即可进入 FastAPI 接口文档进行测试。

### 4. 数据文件与模型

首次运行前，请根据项目实际配置准备所需的 PDF 文档、业务数据库和模型文件。若使用本地缓存模型，请确认模型已下载，且运行环境能够正确访问对应缓存目录。

## 后续优化方向

- 提高复杂业务查询的 SQL 生成准确率。
- 优化跨表 JOIN 与业务统计口径识别。
- 扩充文档问答和数据库查询评估集。
- 持续验证多轮对话、来源引用和用户数据隔离的可靠性。