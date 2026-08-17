# 股票分析 Agent 系统

一个面向 A 股研究的多智能体 Web 应用。用户输入股票名称、六位代码或自然语言要求后，系统并行执行基本面、技术面、估值和新闻分析，再生成结构化综合报告。

> 本项目仅用于学习、研究和辅助分析，不构成投资建议。

## 核心能力

- 四个研究 Agent 实时展示执行状态与日志
- 汇总 Agent 生成报告时逐段呈现 Markdown 正文
- LangGraph 编排分析流程，FastAPI + SSE 推送事件
- React + TypeScript 文本型研究工作台
- 自动生成、复制和下载 Markdown 报告
- 通过 MCP 获取 A 股行情、财报、新闻和市场数据

## 项目结构

```text
.
├── Financial-MCP-Agent/
│   ├── src/agents/       # 基本面、技术面、估值、新闻与汇总 Agent
│   ├── src/services/     # 查询解析与分析工作流
│   ├── src/web/          # FastAPI、SSE 与任务管理
│   ├── web/              # React 前端与生产构建
│   ├── reports/          # 分析报告
│   └── run_web.py        # Web 服务入口
├── a-share-mcp-is-just-i-need/  # A 股 MCP Server
├── train_qwen_sentiment.py      # 新闻情感模型训练
├── train_qwen_risk.py           # 新闻风险模型训练
└── requirements.txt
```

## 模型配置

复制配置模板并填写模型信息：

Windows：

```powershell
cd Financial-MCP-Agent
Copy-Item .env.example .env
```

Linux：

```bash
cp Financial-MCP-Agent/.env.example Financial-MCP-Agent/.env
```

编辑 `.env`：

```dotenv
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.deepseek.com
OPENAI_COMPATIBLE_MODEL=deepseek-v4-flash
SUMMARY_USE_LOCAL_MODEL=api
USE_LOCAL_MODEL=api
```

也可以直接设置系统已有的 `DeepSeek_API_KEY`，程序会自动映射为上述兼容配置。请勿提交包含真实密钥的 `.env`。

## Docker 启动

安装 Docker 与 Docker Compose 后，在项目根目录执行：

```bash
docker compose up -d --build
docker compose ps
```

本机浏览器访问：<http://127.0.0.1:8000>

常用命令：

```bash
docker compose logs -f web
docker compose restart web
docker compose down
```

日志和报告保存在 Docker 命名卷中，执行 `docker compose down` 不会删除；只有显式增加 `-v` 才会删除数据卷。

## 云服务器部署

```bash
git clone https://github.com/cuishiya/Multi-agent-stock-analysis-system.git
cd Multi-agent-stock-analysis-system
cp Financial-MCP-Agent/.env.example Financial-MCP-Agent/.env
nano Financial-MCP-Agent/.env
docker compose up -d --build
curl http://127.0.0.1:8000/api/health
```

更新版本：

```bash
git pull
docker compose up -d --build
```

Compose 默认只监听服务器本机的 `127.0.0.1:8000`，不要在安全组中直接开放 8000。需要公网访问时，请使用带访问认证的 Nginx/Caddy 反向代理，并配置域名与 HTTPS；也可以先用 `ssh -L 8000:127.0.0.1:8000 用户@服务器IP` 建立安全隧道。

## 本地开发

需要 Python 3.11、Node.js 18+ 和 Windows PowerShell。推荐使用 Conda 环境：

```powershell
conda create -n multi-agent-stock-py311 python=3.11.15 pip -y
conda activate multi-agent-stock-py311
python -m pip install -r requirements.txt
```

首次安装并构建前端：

```powershell
cd Financial-MCP-Agent/web
npm install
npm run build
```

启动后端与静态页面：

```powershell
cd ..
python run_web.py
```

浏览器访问：<http://127.0.0.1:8000>

## API

| 方法 | 地址 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 模型与 MCP 状态 |
| `GET` | `/api/examples` | 示例查询 |
| `POST` | `/api/analyses` | 创建分析任务 |
| `GET` | `/api/analyses/{task_id}` | 查询任务与报告 |
| `GET` | `/api/analyses/{task_id}/events` | SSE 实时事件 |
| `GET` | `/api/analyses/{task_id}/report` | 下载 Markdown 报告 |

## 说明

真实模式会调用外部模型 API 和本地 A 股 MCP Server，运行时间取决于网络、模型响应及数据源状态。分析结果应结合公司公告和原始数据独立判断。
