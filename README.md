# 企业智能知识中台 —— 多 Agent 协作系统

基于 LangGraph 构建的企业级多 Agent 协作系统，支持自然语言查询企业文档、业务数据与客服工单，解决企业内部“文档散落、数据查询门槛高、工单处理效率低”的痛点。

## 核心功能

- **Supervisor 多 Agent 协作**：Supervisor 作为调度中心，根据用户问题类型动态路由到 RAG、Text-to-SQL、Ticket Agent。
- **工业级混合检索**：BM25 关键词召回 + 向量语义召回，通过 RRF 融合后使用 Reranker（bge-reranker-base）精排，文档检索命中率达 100%。
- **Text-to-SQL**：自然语言自动生成 SQL，查询业务数据库并返回洞察。
- **工单 Agent**：支持创建工单、查询状态、敏感操作转人工。
- **多轮对话与澄清**：基于 session_id 管理会话历史，无历史时自动澄清。
- **全链路追踪**：每个请求生成 Trace ID，日志可追踪完整调用链路。
- **工程化交付**：FastAPI 封装 RESTful API，支持 SSE 流式输出，Docker 一键部署。
## 多 Agent 协作架构
- **Supervisor 调度**：统一入口，根据问题类型动态路由到 RAG、Text-to-SQL、Ticket Agent。
- **全链路追踪**：每个请求生成 Trace ID，日志可追踪完整调用链路。
- **可靠性设计**：每个工具节点带 try/except 错误捕获，失败自动回 Supervisor 重新调度，最多重试 2 次。

## 技术栈

Python、LangGraph、FastAPI、SSE、Docker、LangChain、ChromaDB、HuggingFace、DeepSeek API、SQLite

## 评估结果

基于真实《京东集团员工手册》自建 15 题评估集（10 题文档检索 + 5 题数据查询），使用 LLM-as-a-Judge 评估：
- 文档检索命中率：100%
- 数据查询命中率：60%（存在业务口径歧义与跨表 JOIN 遗漏，已记录优化方向）
- 综合命中率：86.7%

## 快速开始

### 方式一：本地运行
```bash
pip install -r requirements.txt
uvicorn server:app --port 8000
# 浏览器打开 http://127.0.0.1:8000/docs 进行接口测试
```
### 方式二：Docker 部署
```bash
docker build -t rag-api .
docker run -p 8000:8000 --env-file .env -v "%cd%/test.pdf:/app/test.pdf" -v "%cd%/business.db:/app/business.db" -v "%USERPROFILE%/.cache/huggingface:/root/.cache/huggingface" rag-api
```