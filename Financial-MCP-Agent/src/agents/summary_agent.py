"""
Summary Agent: Consolidates analyses from other agents into a final report.
汇总 Agent：将其他 Agent的分析结果整合成最终报告
"""
import os
import time
import uuid
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Dict, Any
from langchain_openai import ChatOpenAI  # 恢复OpenAI导入
import re

from src.services.progress import emit_runtime_event
from src.utils.state_definition import AgentState
from src.utils.logging_config import setup_logger, ERROR_ICON, SUCCESS_ICON, WAIT_ICON
from src.utils.execution_logger import get_execution_logger
from src.utils.environment import configure_deepseek_environment
from dotenv import load_dotenv

# 从.env文件加载环境变量
load_dotenv(override=False)
configure_deepseek_environment()

logger = setup_logger(__name__)


async def collect_report_stream(stream: AsyncIterable[Any]) -> str:
    """收集模型流式输出，并把每段 Markdown 实时推送给 Web 客户端。"""

    parts: list[str] = []
    pending = ""
    async for chunk in stream:
        content = getattr(chunk, "content", "")
        if not isinstance(content, str) or not content:
            continue
        parts.append(content)
        pending += content
        if len(pending) >= 160 or pending.endswith("\n\n"):
            await emit_runtime_event("report_delta", {"delta": pending})
            pending = ""
    if pending:
        await emit_runtime_event("report_delta", {"delta": pending})
    return "".join(parts)


async def publish_report_text(report: str, *, chunk_size: int = 240) -> None:
    """为不支持原生流式输出的本地模型分段发布报告。"""

    for start in range(0, len(report), chunk_size):
        await emit_runtime_event(
            "report_delta",
            {"delta": report[start : start + chunk_size]},
        )


def _safe_filename_part(value: str | None, fallback: str) -> str:
    cleaned = re.sub(
        r"[^0-9A-Za-z\u3400-\u9fff_-]+",
        "_",
        (value or "").strip(),
    ).strip("._-")
    return (cleaned[:60] or fallback)


def build_report_filename(
    company_name: str | None,
    stock_code: str | None,
    is_error: bool = False,
) -> str:
    """生成不可穿越目录且并发安全的报告文件名。"""

    company = _safe_filename_part(company_name, "stock_analysis")
    code = _safe_filename_part(
        (stock_code or "").replace("sh.", "").replace("sz.", ""),
        "unknown",
    )
    prefix = "error_report" if is_error else "report"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{company}_{code}_{timestamp}_{unique_id}.md"


def report_output_path(filename: str) -> Path:
    reports_dir = Path(__file__).resolve().parents[2] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = (reports_dir / filename).resolve()
    if reports_dir.resolve() not in report_path.parents:
        raise ValueError("报告路径超出 reports 目录")
    return report_path


def truncate_report_at_baseline_time(report_content: str, current_time_info: str) -> str:
    """
    使用正则表达式截断报告，在"分析基准时间"那一行之后停止
    
    Args:
        report_content: 完整的报告内容
        current_time_info: 当前时间信息
    
    Returns:
        截断后的报告内容
    """
    # 构建多种可能的"分析基准时间"模式
    baseline_patterns = [
        rf'分析基准时间[：:]\s*{re.escape(current_time_info)}',
        rf'分析基准时间[：:]\s*{re.escape(current_time_info)}\s*$',
        rf'基准时间[：:]\s*{re.escape(current_time_info)}',
        rf'时间基准[：:]\s*{re.escape(current_time_info)}',
        rf'分析时间[：:]\s*{re.escape(current_time_info)}',
        rf'报告时间[：:]\s*{re.escape(current_time_info)}',
        rf'生成时间[：:]\s*{re.escape(current_time_info)}',
        rf'更新时间[：:]\s*{re.escape(current_time_info)}',
        rf'数据时间[：:]\s*{re.escape(current_time_info)}',
        rf'分析基准[：:]\s*{re.escape(current_time_info)}'
    ]
    
    # 尝试匹配各种模式
    for pattern in baseline_patterns:
        match = re.search(pattern, report_content, re.MULTILINE | re.IGNORECASE)
        if match:
            # 找到匹配位置，截断到该行的末尾
            end_pos = match.end()
            
            # 查找该行的结束位置（换行符）
            line_end = report_content.find('\n', end_pos)
            if line_end == -1:
                # 如果没有换行符，说明是最后一行，直接截断
                truncated_content = report_content[:end_pos].strip()
            else:
                # 截断到该行结束
                truncated_content = report_content[:line_end].strip()
            
            logger.info(f"截断报告在'分析基准时间'行之后，截断位置: {end_pos}")
            return truncated_content
    
    # 如果没有找到匹配的模式，尝试查找包含时间信息的行
    time_patterns = [
        rf'.*{re.escape(current_time_info)}.*',
        rf'.*{re.escape(current_time_info.split()[0])}.*',  # 只匹配日期部分
        rf'.*{re.escape(current_time_info.split()[1])}.*'   # 只匹配时间部分
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, report_content, re.MULTILINE | re.IGNORECASE)
        if match:
            end_pos = match.end()
            line_end = report_content.find('\n', end_pos)
            if line_end == -1:
                truncated_content = report_content[:end_pos].strip()
            else:
                truncated_content = report_content[:line_end].strip()
            
            logger.info(f"截断报告在时间信息行之后，截断位置: {end_pos}")
            return truncated_content
    
    # 如果都没有找到，返回原始内容
    logger.warning("未找到'分析基准时间'模式，返回原始报告内容")
    return report_content


def load_finr1_model(model_path="/home/ubuntu/桌面/model_download/Fin_R1"):
    """加载FinR1模型"""
    logger.info(f"{WAIT_ICON} Loading FinR1 model from {model_path}...")
    
    try:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as exc:
            raise RuntimeError(
                "本地 FinR1 模式需要额外安装 torch、transformers 和 bitsandbytes。"
            ) from exc

        # 加载tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # 加载模型（4-bit 量化，约 5GB 显存）
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True
        )
        
        model.eval()
        logger.info(f"{SUCCESS_ICON} FinR1 model loaded successfully")
        return model, tokenizer
    
    except Exception as e:
        logger.error(f"{ERROR_ICON} Failed to load FinR1 model: {e}")
        raise e


def generate_report_with_finr1(model, tokenizer, prompt, max_new_tokens=5000):
    """使用FinR1模型生成报告"""
    
    try:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("本地 FinR1 模式需要额外安装 torch。") from exc

        # 编码输入
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        # 生成预测
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.5,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # 解码输出
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # 提取生成的报告部分（移除输入提示）
        # 方法1：尝试通过字符串匹配移除输入提示
        if prompt in generated_text:
            report = generated_text[len(prompt):].strip()
        else:
            # 方法2：如果字符串匹配失败，尝试通过token长度来提取
            input_length = len(tokenizer.encode(prompt, return_tensors="pt")[0])
            output_length = len(outputs[0])
            
            if output_length > input_length:
                # 只保留新生成的部分
                new_tokens = outputs[0][input_length:]
                report = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            else:
                # 如果无法确定，返回完整文本但尝试清理
                report = generated_text.strip()
        
        return report
    
    except Exception as e:
        logger.error(f"{ERROR_ICON} Error generating report with FinR1: {e}")
        raise e


def get_model_choice():
    """获取模型选择，汇总Agent默认使用本地FinR1"""
    model_choice = os.getenv("SUMMARY_USE_LOCAL_MODEL", "local").lower()
    return model_choice


async def summary_agent(state: AgentState) -> Dict[str, Any]:
    """
    整合基本面、技术面和估值分析的结果
    使用LLM生成最终的综合性报告
    """
    logger.info(f"{WAIT_ICON} SummaryAgent: Starting to consolidate analyses.")

    # 获取执行日志记录器，用于记录 Agent的执行过程
    execution_logger = get_execution_logger()
    agent_name = "summary_agent"

    # 从状态中提取当前数据、消息和用户查询
    current_data = state.get("data", {})
    messages = state.get("messages", [])
    user_query = current_data.get("query", "")

    # 记录 Agent开始执行，包含可用的分析类型
    execution_logger.log_agent_start(agent_name, {
        "user_query": user_query,
        "available_analyses": {
            "fundamental": "fundamental_analysis" in current_data,
            "technical": "technical_analysis" in current_data,
            "value": "value_analysis" in current_data,
            "news": "news_analysis" in current_data
        },
        "input_data_keys": list(current_data.keys())
    })

    # 记录 Agent开始时间，用于计算执行时长
    agent_start_time = time.time()

    # 获取之前 Agent的分析结果
    fundamental_analysis = current_data.get(
        "fundamental_analysis", "Not available")
    technical_analysis = current_data.get(
        "technical_analysis", "Not available")
    value_analysis = current_data.get("value_analysis", "Not available")
    news_analysis = current_data.get("news_analysis", "Not available")

    # 处理各个分析的错误信息
    errors = []
    if "fundamental_analysis_error" in current_data:
        errors.append(
            f"Fundamental Analysis Error: {current_data['fundamental_analysis_error']}")
    if "technical_analysis_error" in current_data:
        errors.append(
            f"Technical Analysis Error: {current_data['technical_analysis_error']}")
    if "value_analysis_error" in current_data:
        errors.append(
            f"Value Analysis Error: {current_data['value_analysis_error']}")
    if "news_analysis_error" in current_data:
        errors.append(
            f"News Analysis Error: {current_data['news_analysis_error']}")

    # 基本股票标识信息
    stock_code = current_data.get("stock_code", "Unknown Stock")
    company_name = current_data.get("company_name", "Unknown Company")

    try:
        # 获取模型选择
        model_choice = get_model_choice()
        logger.info(f"{WAIT_ICON} SummaryAgent: Using model choice: {model_choice}")

        # 获取当前时间信息，用于报告中的时间标注
        current_time_info = current_data.get("current_time_info", "未知时间")
        current_date = current_data.get("current_date", "未知日期")

        # 准备汇总的系统提示词
        system_prompt = f"""
        你是一个专业金融分析师，负责创建全面、深入的股票分析报告。
        
        **重要时间信息：当前实际时间是 {current_time_info}**
        **分析基准日期：{current_date}**
        
        这是真实的当前时间，不是你的训练数据截止时间。请在生成报告时：
        - 基于实际当前时间来判断数据的时效性
        - 正确标注"最新"、"近期"、"历史"等时间概念
        - 在报告中明确标注分析的时间基准点为：{current_date}
        - 所有时间相关的描述都要基于这个实际日期
        
        你的任务是综合四种不同的分析结果：
        1. 基本面分析 - 关注财务报表、商业模式和公司基本面
        2. 技术分析 - 关注价格趋势、交易量模式和技术指标
        3. 估值分析 - 关注估值指标和相对价值
        4. 新闻分析 - 关注市场情绪、重要事件和媒体报道对股价的影响

        请创建一份结构清晰、内容连贯的报告，整合所有四种分析的见解。
        即使某些分析数据不完整或缺失，也请基于可用信息提供最佳的综合分析。

        **严格遵循以下报告格式和结构：**
        
        # [公司名称]([股票代码]) 综合分析报告
        
        ## 执行摘要
        [提供简明扼要的总体分析和投资建议，包括风险等级和预期回报]
        
        ## 公司概况
        [简要介绍公司的业务、行业地位、主要产品或服务]
        
        ## 基本面分析
        [详细分析公司财务状况、盈利能力、成长性、资产负债情况等]
        
        ## 技术分析
        [详细分析价格趋势、技术指标、支撑位和阻力位、交易量等]
        
        ## 估值分析
        [详细分析估值指标、与行业平均水平比较、历史估值水平、股息收益率等]
        
        ## 新闻分析
        [详细分析市场情绪、重要新闻事件、媒体报道、分析师评级变化等对股价的影响]
        
        ## 综合评估
        [分析不同分析方法之间的一致点和分歧点，提供更全面的投资视角]
        
        ## 风险因素
        [详细分析潜在的风险因素，包括市场风险、行业风险、公司特定风险等]
        
        ## 投资建议
        [提供明确的投资建议，包括目标价格、投资时间范围、适合的投资者类型等]
        
        ## 附录：数据来源与限制
        [说明数据来源，以及分析过程中遇到的任何数据限制或缺失]

        输出必须是有效的Markdown格式，使用适当的标题、项目符号和格式。
        不要包含任何代码块标记，如```markdown或```，直接输出纯Markdown内容。
        
        使用专业的金融语言，但保持可读性。报告应该全面且深入，包含足够的细节和数据支持，
        同时聚焦于最重要的见解，帮助投资者做出决策。
        
        **重要提醒：**
        - 请在报告末尾明确标注分析基准时间：{current_time_info}
        - 基于这个实际时间来判断所有数据的时效性
        - 避免使用模糊的时间概念，要基于实际当前时间进行判断
        - 严格按照上述格式和结构生成报告，确保每个章节都有实质性内容
        
        如果某些分析数据不完整或有错误，请在报告中明确说明，并尽可能基于可用信息提供有价值的分析。
        """

        # 准备汇总提示词
        user_prompt = f"""
        Please create a comprehensive analysis report for {company_name} ({stock_code}) based on the following analyses.
        
        Original user query: {user_query}
        
        FUNDAMENTAL ANALYSIS:
        {fundamental_analysis}
        
        TECHNICAL ANALYSIS:
        {technical_analysis}
        
        VALUE ANALYSIS:
        {value_analysis}
        
        NEWS ANALYSIS:
        {news_analysis}
        
        {"ANALYSIS ISSUES:" if errors else ""}
        {". ".join(errors) if errors else ""}
        
        IMPORTANT: Your output MUST be in valid Markdown format with proper headings, bullet points, 
        and formatting. Include a clear recommendation section at the end.
        
        DO NOT include any code block markers like ```markdown or ``` in your output.
        Just write pure Markdown content directly.
        """

        # 根据模型选择决定使用哪种方式生成报告
        if model_choice == "local":
            # 使用本地FinR1模型
            logger.info(f"{WAIT_ICON} SummaryAgent: Using local FinR1 model...")
            
            # 记录模型配置信息
            model_config = {
                "model": "FinR1",
                "temperature": 0.5,
                "max_tokens": 5000,
                "model_path": "/home/ubuntu/桌面/model_download/Fin_R1"
            }

            # 加载FinR1模型
            model, tokenizer = load_finr1_model()

            # 组合完整的提示词
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # 记录LLM交互开始时间
            llm_start_time = time.time()

            # 使用FinR1模型生成最终报告
            final_report = generate_report_with_finr1(model, tokenizer, full_prompt)
            await publish_report_text(final_report)

            # 记录LLM交互执行时间
            llm_execution_time = time.time() - llm_start_time

        else:
            # 默认使用API接口
            logger.info(f"{WAIT_ICON} SummaryAgent: Using OpenAI API...")
            
            # 创建OpenAI模型（使用直接API调用，而不是ReAct框架进行汇总）
            api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
            base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
            model_name = os.getenv("OPENAI_COMPATIBLE_MODEL")

            # 验证必要的环境变量是否存在
            if not all([api_key, base_url, model_name]):
                logger.error(
                    f"{ERROR_ICON} SummaryAgent: Missing OpenAI environment variables.")
                current_data["summary_error"] = "Missing OpenAI environment variables."

                # 记录 Agent执行失败
                execution_logger.log_agent_complete(agent_name, current_data, time.time(
                ) - agent_start_time, False, "Missing OpenAI environment variables")

                return {"data": current_data, "messages": messages}

            # 记录模型配置信息
            model_config = {
                "model": model_name,
                "temperature": 0.5,
                "max_tokens": 5000,
                "api_base": base_url
            }

            # 准备汇总提示词消息列表
            summary_prompt_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 使用ChatOpenAI模型
            logger.info(f"{WAIT_ICON} SummaryAgent: Creating ChatOpenAI with model {model_name}")
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=0.5,  # 提高温度以增加创造性和更自然的表达
                max_tokens=5000   # 增大输出长度以生成更详细的综合报告
            )

            # 记录LLM交互开始时间
            llm_start_time = time.time()

            # 流式生成最终报告，并通过 SSE 逐段推送给前端
            final_report = await collect_report_stream(
                llm.astream(summary_prompt_messages)
            )

            # 记录LLM交互执行时间
            llm_execution_time = time.time() - llm_start_time

        # 记录LLM交互详情，用于后续分析和优化
        execution_logger.log_llm_interaction(
            agent_name=agent_name,
            interaction_type="summary_generation",
            input_messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            output_content=final_report,
            model_config=model_config,
            execution_time=llm_execution_time
        )

        # 移除任何可能出现的markdown代码块标记
        final_report = final_report.replace(
            "```markdown", "").replace("```", "").strip()
        
        # 使用正则表达式截断"分析基准时间"那一行之后的内容
        final_report = truncate_report_at_baseline_time(final_report, current_time_info)

        logger.info(
            f"{SUCCESS_ICON} SummaryAgent: Final report generated for {company_name} ({stock_code}).")
        logger.debug(f"Final report preview: {final_report[:300]}...")

        fallback_name = user_query.replace("分析", "").strip()
        filename_company = (
            fallback_name
            if company_name in {"Unknown Company", "Extracted from analysis"}
            else company_name
        )
        report_path = report_output_path(
            build_report_filename(filename_company, stock_code)
        )

        with report_path.open("w", encoding="utf-8") as f:
            f.write(final_report)

        logger.info(
            f"{SUCCESS_ICON} SummaryAgent: Report saved to {report_path}")

        # 返回更新后的状态，包含最终报告
        current_data["final_report"] = final_report
        current_data["report_path"] = str(report_path)

        # 记录 Agent执行成功
        total_execution_time = time.time() - agent_start_time
        execution_logger.log_agent_complete(agent_name, {
            "final_report_length": len(final_report),
            "report_path": str(report_path),
            "report_preview": final_report,
            "llm_execution_time": llm_execution_time,
            "total_execution_time": total_execution_time
        }, total_execution_time, True)

        return {"data": current_data, "messages": messages}

    except Exception as e:
        logger.error(
            f"{ERROR_ICON} SummaryAgent: Error generating final report: {e}", exc_info=True)
        current_data["summary_error"] = f"Error generating final report: {e}"

        # 即使出现错误也创建最小化的报告
        error_report = f"""
        # Analysis Report for {company_name} ({stock_code})
        
        **Error encountered during report generation**: {e}
        
        ## Available Analysis Fragments:
        
        - Fundamental Analysis: {"Available" if fundamental_analysis != "Not available" else "Not available"}
        - Technical Analysis: {"Available" if technical_analysis != "Not available" else "Not available"}
        - Value Analysis: {"Available" if value_analysis != "Not available" else "Not available"}
        - News Analysis: {"Available" if news_analysis != "Not available" else "Not available"}
        
        Please review the individual analyses directly for more information.
        """
        current_data["final_report"] = error_report

        fallback_name = user_query.replace("分析", "").strip()
        filename_company = (
            fallback_name
            if company_name in {"Unknown Company", "Extracted from analysis"}
            else company_name
        )
        report_path = report_output_path(
            build_report_filename(filename_company, stock_code, is_error=True)
        )

        with report_path.open("w", encoding="utf-8") as f:
            f.write(error_report)

        logger.info(
            f"{ERROR_ICON} SummaryAgent: Error report saved to {report_path}")
        current_data["report_path"] = str(report_path)

        # 记录 Agent执行失败
        execution_logger.log_agent_complete(
            agent_name, current_data, time.time() - agent_start_time, False, str(e))

        return {"data": current_data, "messages": messages}
