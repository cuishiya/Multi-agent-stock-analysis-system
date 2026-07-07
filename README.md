# Finance 股票投资顾问 Agent

本项目是一个面向股票投资分析的金融智能体实验项目，包含两部分核心能力：

1. 基于 LangGraph + MCP 的 A 股多智能体分析系统，可对股票进行基本面、技术面、估值、新闻和综合总结分析。
2. 基于 Qwen3-8B + LoRA 的 NASDAQ 新闻情感评分与风险评分模型训练、测试脚本。

> 免责声明：本项目输出仅用于学习、研究和辅助分析，不构成任何投资建议。投资决策需结合公开信息、个人风险承受能力和专业判断。

## 项目结构

```text
Finance/
├── Financial-MCP-Agent/              # A 股多智能体投资分析主程序
│   ├── src/
│   │   ├── main.py                   # LangGraph 工作流入口
│   │   ├── agents/                   # 基本面、技术面、估值、新闻、总结智能体
│   │   ├── tools/                    # MCP 客户端与模型配置
│   │   └── utils/                    # 日志、状态、LLM 客户端等工具
│   ├── logs/                         # 历史运行日志
│   └── reports/                      # 生成的分析报告
├── a-share-mcp-is-just-i-need/       # A 股数据 MCP Server
│   ├── mcp_server.py                 # MCP 服务入口
│   └── src/tools/                    # 行情、财报、指数、宏观、新闻等工具
├── nasdaq_news_sentiment/            # 新闻情感训练数据
│   └── 1.csv
├── risk_nasdaq/                      # 新闻风险训练数据
│   └── 2.csv
├── data_process.py                   # 新闻数据清洗与去重
├── download.py                       # 下载 Qwen3-8B 基座模型
├── train_qwen_sentiment.py           # 训练新闻情感评分 LoRA 模型
├── train_qwen_risk.py                # 训练新闻风险评分 LoRA 模型
├── test_qwen_sentiment.py            # 测试新闻情感评分模型
├── test_risk_model.py                # 测试新闻风险评分模型
└── requirements.txt                  # 项目主要依赖
```

## 功能概览

### A 股多智能体分析

`Financial-MCP-Agent/src/main.py` 使用 LangGraph 编排多个分析智能体：

- `fundamental_agent`：基本面分析，关注财务状况、盈利能力、行业地位等。
- `technical_agent`：技术面分析，关注价格趋势、成交量和技术指标。
- `value_agent`：估值分析，关注市盈率、市净率等估值指标。
- `news_agent`：新闻分析，关注公司和行业新闻、情绪与潜在风险。
- `summary_agent`：整合各智能体结果，生成综合投资分析报告。

A 股数据由 `a-share-mcp-is-just-i-need/mcp_server.py` 提供，工具覆盖行情、财报、指数、市场概览、宏观数据、日期工具、分析工具和新闻爬取等模块。

### Qwen 金融新闻评分模型

根目录下的训练脚本用于微调 Qwen3-8B：

- `train_qwen_sentiment.py`：基于 `nasdaq_news_sentiment/1.csv` 训练 1-5 分新闻情感模型。
- `train_qwen_risk.py`：基于 `risk_nasdaq/2.csv` 训练 1-5 分新闻风险模型。
- `test_qwen_sentiment.py` 和 `test_risk_model.py`：加载 LoRA 权重进行样例预测和真实数据测试。

## 环境准备

建议使用 Python 3.10+，并优先使用虚拟环境。

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

训练和数据处理脚本还会用到部分未写入 `requirements.txt` 的库，如 `torch`、`pandas`、`numpy`、`scikit-learn`、`datasets`、`jieba`、`tqdm`、`google-genai`、`backoff` 等。如运行时报缺失模块，可按需安装：

```bash
pip install torch pandas numpy scikit-learn datasets jieba tqdm google-genai backoff
```

## 环境变量

在 `Financial-MCP-Agent/.env` 中配置大模型 API。项目支持 OpenAI Compatible API，也保留了 Gemini 客户端相关配置。

```env
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://your-api-base-url/v1
OPENAI_COMPATIBLE_MODEL=your_model_name

# 可选：Gemini 客户端
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-1.5-flash

# 可选：summary_agent 中用于选择本地/API模型的开关
USE_LOCAL_MODEL=api
```

## 运行 A 股分析 Agent

进入 `Financial-MCP-Agent` 目录运行主程序：

```bash
cd Financial-MCP-Agent
python -m src.main --command "请帮我分析一下贵州茅台 600519 的投资价值"
```

也可以不传 `--command`，进入交互式输入：

```bash
python -m src.main
```

运行后系统会：

1. 启动并连接 A 股 MCP Server。
2. 自动识别查询中的股票名称或股票代码。
3. 并行执行基本面、技术面、估值、新闻分析。
4. 由总结智能体生成综合报告。
5. 将执行过程写入 `Financial-MCP-Agent/logs/`，报告写入 `reports/` 或对应运行日志目录。

### MCP 路径配置

`Financial-MCP-Agent/src/tools/mcp_config.py` 中默认 MCP Server 路径为：

```python
r"/root/code/Finance/a-share-mcp-is-just-i-need"
```

如果你在 Windows 或其他本地路径运行，需要将它改成当前机器上的实际路径，例如：

```python
r"E:\...\Finance\a-share-mcp-is-just-i-need"
```

## 下载 Qwen3-8B 模型

`download.py` 会从 Hugging Face 下载 `Qwen/Qwen3-8B` 到本地 `./Qwen`：

```bash
python download.py
```

如果网络环境无法访问 Hugging Face，需要提前配置镜像、代理或手动准备模型文件。

## 训练新闻情感/风险模型

训练脚本当前默认从 `/root/code/Finance/Qwen` 加载基座模型。如果你的模型在项目根目录的 `Qwen/`，需要先把脚本中的 `model_name` 路径改成实际路径。

训练情感模型：

```bash
python train_qwen_sentiment.py
```

训练风险模型：

```bash
python train_qwen_risk.py
```

默认输出目录：

- 情感模型：`qwen_sentiment_model/`
- 风险模型：`qwen_risk_model/`

## 测试模型

测试情感评分模型：

```bash
python test_qwen_sentiment.py
```

测试风险评分模型：

```bash
python test_risk_model.py
```

测试脚本默认加载：

- 基座模型：`/root/code/Finance/Qwen`
- 情感 LoRA：`/root/code/Finance/qwen_sentiment_model`
- 风险 LoRA：`/root/code/Finance/qwen_risk_model`

本地运行前请根据实际目录调整脚本中的模型路径。

## 数据处理

`data_process.py` 提供新闻数据去重和预处理能力，使用了标题相似度、MinHash、SimHash 等方法。默认输入路径偏向 Linux 环境：

```python
/mnt/data/Finance/risk_nasdaq/2.csv
```

如需处理本项目内置 CSV，请将路径改为：

```python
r"risk_nasdaq/2.csv"
```

## 常见问题

### 1. 中文注释或输出显示乱码

部分源码注释可能在非 UTF-8 终端下显示异常。建议使用 UTF-8 编码的编辑器和终端。

### 2. MCP 工具加载失败

优先检查：

- `Financial-MCP-Agent/src/tools/mcp_config.py` 中的 `--directory` 路径是否正确。
- 是否安装了 `uv` 和 `mcp` 相关依赖。
- 是否能单独运行 `a-share-mcp-is-just-i-need/mcp_server.py`。

### 3. CUDA 或显存不足

Qwen3-8B 微调需要较高显存。可以考虑减小 batch size、使用量化加载、缩短 `max_length`，或改用更小的模型。

### 4. API 调用失败

检查 `.env` 中的 `OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_BASE_URL`、`OPENAI_COMPATIBLE_MODEL` 是否配置正确，并确认服务商接口可访问。

