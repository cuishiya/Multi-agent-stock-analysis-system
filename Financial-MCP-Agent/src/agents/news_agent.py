import asyncio
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import time

from src.utils.state_definition import AgentState
from src.tools.mcp_client import get_mcp_tools
from src.utils.logging_config import setup_logger, ERROR_ICON, SUCCESS_ICON, WAIT_ICON
from src.utils.execution_logger import get_execution_logger
from src.utils.environment import configure_deepseek_environment
from src.services.progress import emit_runtime_event
from dotenv import load_dotenv

# 从.env文件加载环境变量
load_dotenv(override=False)
configure_deepseek_environment()

logger = setup_logger(__name__)


def news_search_query(company_name: str | None, stock_code: str | None) -> str:
    """优先按公司名检索新闻；缺少名称时使用不带交易所前缀的代码。"""

    normalized_name = (company_name or "").strip()
    if normalized_name.lower() not in {"", "unknown", "unknown company"}:
        return normalized_name
    normalized_code = (stock_code or "").strip()
    for prefix in ("sh.", "sz.", "bj."):
        if normalized_code.lower().startswith(prefix):
            normalized_code = normalized_code[len(prefix) :]
            break
    return normalized_code


async def news_agent(state: AgentState) -> AgentState:
    """
    抓取一次真实新闻，并使用 DeepSeek 完成情感和风险分析。
    
    Args:
        state: 包含用户查询的当前 Agent状态

    Returns:
        更新后的AgentState，包含新闻分析结果
    """
    logger.info(
        f"{WAIT_ICON} NewsAgent: Starting DeepSeek news analysis.")

    # 获取执行日志记录器，用于记录 Agent的执行过程
    execution_logger = get_execution_logger()
    agent_name = "news_agent"

    # 从状态中提取当前数据、消息和元数据
    current_data = state.get("data", {})
    current_messages = state.get("messages", [])
    current_metadata = state.get("metadata", {})
    user_query = current_data.get("query")

    # 记录 Agent开始执行，包含关键信息
    execution_logger.log_agent_start(agent_name, {
        "user_query": user_query,
        "stock_code": current_data.get("stock_code"),
        "company_name": current_data.get("company_name"),
        "input_data_keys": list(current_data.keys())
    })

    # 验证用户查询是否存在
    if not user_query:
        logger.error(
            f"{ERROR_ICON} NewsAgent: User query is missing in state data.")
        current_data["news_analysis_error"] = "User query is missing."

        # 记录 Agent执行失败
        execution_logger.log_agent_complete(
            agent_name, current_data, 0, False, "User query is missing")

        return {"data": current_data, "messages": current_messages, "metadata": current_metadata}

    # 记录 Agent开始时间，用于计算执行时长
    agent_start_time = time.time()

    try:
        # 使用API调用
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        model_name = os.getenv("OPENAI_COMPATIBLE_MODEL")

        # 验证必要的环境变量是否存在
        if not all([api_key, base_url, model_name]):
            logger.error(f"{ERROR_ICON} NewsAgent: Missing OpenAI environment variables.")
            current_data["news_analysis_error"] = "Missing OpenAI environment variables."
            execution_logger.log_agent_complete(agent_name, current_data, time.time() - agent_start_time, False, "Missing OpenAI environment variables")
            return {"data": current_data, "messages": current_messages, "metadata": current_metadata}

        logger.info(f"{WAIT_ICON} NewsAgent: Creating ChatOpenAI with model {model_name}")
        # 创建LLM实例，设置合适的参数
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,  # 较低的温度确保分析的一致性
            max_tokens=6000   # 增加token数量用于详细分析
        )

        # 2. 获取MCP工具集
        logger.info(f"{WAIT_ICON} NewsAgent: Fetching MCP tools...")
        await emit_runtime_event(
            "agent_progress",
            {"agent": "news", "message": "正在连接 MCP 新闻数据工具"},
        )
        try:
            mcp_tools = await get_mcp_tools()
            if not mcp_tools:
                logger.error(
                    f"{ERROR_ICON} NewsAgent: No MCP tools available.")
                current_data["news_analysis_error"] = "No MCP tools available."

                # 记录 Agent执行失败
                execution_logger.log_agent_complete(agent_name, current_data, time.time(
                ) - agent_start_time, False, "No MCP tools available")

                return {"data": current_data, "messages": current_messages, "metadata": current_metadata}

            logger.info(
                f"{SUCCESS_ICON} NewsAgent: Successfully loaded {len(mcp_tools)} tools.")
            await emit_runtime_event(
                "agent_progress",
                {"agent": "news", "message": "新闻工具已就绪，正在抓取最新公开信息"},
            )

            # 打印可用工具列表，便于调试
            tool_names = [tool.name for tool in mcp_tools]
            logger.info(f"Available tools: {tool_names}")

            # 3. 只选择新闻抓取工具，避免模型在 ReAct 循环中重复调用无关工具
            crawl_news_tool = next(
                (tool for tool in mcp_tools if tool.name == "crawl_news"),
                None,
            )
            if crawl_news_tool is None:
                raise RuntimeError("crawl_news tool is unavailable")

            # 4. 抓取一次原始新闻，再统一交给 DeepSeek 分析
            stock_code = current_data.get('stock_code', 'Unknown')
            company_name = current_data.get('company_name', 'Unknown')
            current_time_info = current_data.get('current_time_info', '未知时间')
            current_date = current_data.get('current_date', '未知日期')

            tool_input = {
                "query": news_search_query(company_name, stock_code),
                "top_k": 5,
            }
            logger.info(f"{WAIT_ICON} NewsAgent: Crawling news once...")
            crawl_start_time = time.time()
            raw_news = await asyncio.wait_for(
                crawl_news_tool.ainvoke(tool_input),
                timeout=90,
            )
            crawl_execution_time = time.time() - crawl_start_time
            raw_news = str(raw_news)
            execution_logger.log_tool_usage(
                agent_name=agent_name,
                tool_name="crawl_news",
                tool_input=tool_input,
                tool_output=raw_news,
                execution_time=crawl_execution_time,
                success=True,
            )

            agent_input = f"""请基于下面已经抓取到的真实新闻，对{company_name}（股票代码：{stock_code}）进行分析。

当前时间：{current_time_info}
当前日期：{current_date}

分析要求：
1. 逐条列出新闻标题和关键信息；
2. 为每条新闻给出情感评分（1=负面，2=轻微负面，3=中性，4=正面，5=极正面）；
3. 为每条新闻给出风险评分（1=极低风险，2=低风险，3=中等风险，4=高风险，5=极高风险）；
4. 分析新闻对股价的潜在影响，识别关键事件和趋势；
5. 给出综合结论，并明确说明数据不足或新闻抓取失败的情况；
6. 不要编造输入中没有出现的新闻或事实。

已抓取的新闻原文：
{raw_news}
"""

            logger.info(f"Agent input: {agent_input}")

            # 5. 使用 DeepSeek 一次性完成情感、风险和综合分析
            logger.info(
                f"{WAIT_ICON} NewsAgent: Calling DeepSeek for news analysis...")
            await emit_runtime_event(
                "agent_progress",
                {"agent": "news", "message": "新闻已获取，正在进行情绪与风险分析"},
            )
            start_time = time.time()

            response = await asyncio.wait_for(
                llm.ainvoke([
                    SystemMessage(
                        content="你是严谨的A股新闻分析师，只能依据用户提供的新闻进行分析。"
                    ),
                    HumanMessage(content=agent_input),
                ]),
                timeout=120,
            )

            end_time = time.time()
            execution_time = end_time - start_time

            logger.info(
                f"DeepSeek news analysis completed in {execution_time:.2f} seconds")

            final_output = str(response.content).strip()
            if not final_output:
                raise RuntimeError("DeepSeek returned an empty news analysis")

            logger.info(
                f"Final extracted analysis length: {len(final_output)} characters")

            # 7. 记录LLM交互，用于后续分析和优化
            model_config = {
                "model": model_name,
                "temperature": 0.3,
                "max_tokens": 6000,
                "api_base": base_url
            }
            
            execution_logger.log_llm_interaction(
                agent_name=agent_name,
                interaction_type="deepseek_news_analysis",
                input_messages=[{"role": "user", "content": agent_input}],
                output_content=final_output,
                model_config=model_config,
                execution_time=execution_time
            )

            logger.info(
                f"{SUCCESS_ICON} NewsAgent: Successfully completed news analysis.")
            
            # 8. 更新状态，保存分析结果和元数据
            current_data["news_analysis"] = final_output
            current_metadata["news_agent_executed"] = True
            current_metadata["news_agent_timestamp"] = str(time.time())
            current_metadata["news_agent_execution_time"] = f"{execution_time:.2f} seconds"

            # 9. 添加消息记录，保持对话历史
            new_message = {"role": "assistant", "content": "新闻分析已完成"}
            updated_messages = current_messages + [new_message]

            # 记录 Agent执行成功
            total_execution_time = time.time() - agent_start_time
            execution_logger.log_agent_complete(agent_name, {
                "news_analysis_length": len(final_output),
                "analysis_preview": final_output[:500] if len(final_output) > 500 else final_output,
                "llm_execution_time": execution_time,
                "total_execution_time": total_execution_time
            }, total_execution_time, True)

            return {
                "data": current_data,
                "messages": updated_messages,
                "metadata": current_metadata
            }

        except Exception as e:
            logger.error(
                f"{ERROR_ICON} NewsAgent: Error in MCP or agent execution: {e}", exc_info=True)
            current_data[
                "news_analysis_error"] = f"Error in MCP or agent execution: {e}"
            current_data["news_analysis"] = f"新闻分析过程中出现错误: {str(e)}"
            current_metadata["news_agent_error"] = str(e)

            # 记录 Agent执行失败
            execution_logger.log_agent_complete(
                agent_name, current_data, time.time() - agent_start_time, False, str(e))

            return {
                "data": current_data,
                "messages": current_messages,
                "metadata": current_metadata
            }

    except Exception as e:
        logger.error(
            f"{ERROR_ICON} NewsAgent: Error during execution: {e}", exc_info=True)
        current_data["news_analysis_error"] = f"Error during execution: {e}"
        current_metadata["news_agent_error"] = str(e)

        # 记录 Agent执行失败
        execution_logger.log_agent_complete(
            agent_name, current_data, time.time() - agent_start_time, False, str(e))

        return {
            "data": current_data,
            "messages": current_messages,
            "metadata": current_metadata
        }
