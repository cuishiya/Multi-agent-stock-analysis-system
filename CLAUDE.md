# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目级规则

- **语言偏好**：所有回复、注释、说明统一使用中文，代码中的变量名/函数名保持英文
- **虚拟环境**：运行任何 Python 文件之前，必须使用虚拟环境中的 Python 解释器：
  ```
  /home/ubuntu/miniconda3/envs/cui_sft/bin/python <文件名>.py
  ```
  安装第三方库时也必须安装到此环境中：
  ```
  /home/ubuntu/miniconda3/envs/cui_sft/bin/pip install <包名>
  ```

## 项目概述

面向A股市场的多 Agent 协同股票分析系统。整合了 MCP 数据服务器、LangGraph 多智能体编排层，以及基于 Qwen 微调的情感/风险评分模型。

## 系统架构

系统由三个主要子系统组成：

### 1. MCP 数据服务器 (`a-share-mcp-is-just-i-need/`)
基于 FastMCP 的 A 股行情数据服务器，通过 stdio 传输协议提供数据工具。使用 **baostock** 作为数据后端，采用可插拔接口模式：
- `src/data_source_interface.py` — 抽象基类 `FinancialDataSource`
- `src/baostock_data_source.py` — baostock 具体实现
- `src/tools/` — 模块化工具注册：`stock_market`、`financial_reports`、`indices`、`market_overview`、`macroeconomic`、`date_utils`、`analysis`、`news_crawler`
- `mcp_server.py` — 入口文件，实例化数据源并注册所有工具模块

运行方式：`cd a-share-mcp-is-just-i-need && /home/ubuntu/miniconda3/envs/cui_sft/bin/python mcp_server.py`

### 2. 多智能体编排层 (`Financial-MCP-Agent/`)
基于 LangGraph 的工作流，包含 4 个并行分析智能体和 1 个汇总智能体：
```
start_node → [fundamental_analyst, technical_analyst, value_analyst, news_analyst] → summarizer → END
```
- **AgentState**（`src/utils/state_definition.py`）：TypedDict，包含 `messages`、`data`、`metadata`，均使用 merge/reduce 注解以支持并行扇入
- 4 个分析智能体均使用 LangGraph 的 `create_react_agent` 搭配 MCP 工具，通过 `langchain-mcp-adapters` 访问
- **汇总智能体** 支持两种后端：OpenAI 兼容 API 或本地 FinR1 模型（通过 `USE_LOCAL_MODEL` 环境变量控制）
- `src/tools/mcp_config.py` — 配置 MCP 服务器子进程（需修改路径指向实际的 `a-share-mcp-is-just-i-need` 目录）
- 分析报告保存至 `Financial-MCP-Agent/reports/`
- 执行日志保存至 `Financial-MCP-Agent/logs/`

运行方式：`cd Financial-MCP-Agent && /home/ubuntu/miniconda3/envs/cui_sft/bin/python -m src.main` 或 `... -m src.main --command "分析嘉友国际"`

### 3. 微调与数据流水线（根目录）
- `train_qwen_sentiment.py` / `train_qwen_risk.py` — 基于 Qwen LoRA 微调，用于新闻情感评分（1-5）和风险评分（1-5），训练数据为 NASDAQ 新闻
- `data_process.py` — `NewsDeduplicator`，使用 MinHash/SimHash/TF-IDF 对 CSV 新闻数据去重
- `download.py` — 从 HuggingFace 下载 Qwen3-8B 模型
- `nasdaq_news_sentiment/`、`risk_nasdaq/` — 训练数据（CSV + Jupyter Notebook）

## 环境变量

需在 `.env` 文件中配置（通常位于 `Financial-MCP-Agent/` 目录下）：
- `OPENAI_COMPATIBLE_API_KEY` — LLM API 密钥
- `OPENAI_COMPATIBLE_BASE_URL` — LLM API 基础地址
- `OPENAI_COMPATIBLE_MODEL` — 模型名称
- `USE_LOCAL_MODEL` — 设为 `"local"` 使用本地 FinR1 模型（默认 `"api"`）
- `GEMINI_API_KEY`、`GEMINI_MODEL` — 可选，用于 `openrouter_config.py` 中的 Gemini 客户端

## 核心依赖

- **langgraph** — 工作流编排（StateGraph、create_react_agent）
- **langchain-mcp-adapters** — 连接智能体与 MCP 服务器工具
- **langchain-openai** — ChatOpenAI，用于 LLM 调用
- **baostock** — A 股行情数据源
- **peft + transformers** — Qwen LoRA 微调
- **uv** — MCP 服务器的 Python 包运行器

## 重要约定

- `Financial-MCP-Agent/src/tools/mcp_config.py` 中的 MCP 服务器路径必须指向实际的 `a-share-mcp-is-just-i-need` 目录
- 股票代码使用交易所前缀：`sh.` 对应上海交易所（代码以 6 开头），`sz.` 对应深圳交易所（代码以 0 或 3 开头）
- 所有智能体均为异步函数，接收和返回 `AgentState` 字典
- 工具注册模式：每个工具模块导出一个 `register_*_tools(app, data_source)` 函数，在 `mcp_server.py` 中统一调用
