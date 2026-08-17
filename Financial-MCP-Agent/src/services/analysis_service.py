"""可由命令行和 Web 层共同调用的股票分析工作流。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from langgraph.graph import END, StateGraph

from src.services.query_parser import StockTarget, build_initial_state, parse_stock_target
from src.utils.state_definition import AgentState


AgentFunction = Callable[[AgentState], Awaitable[dict[str, Any]]]
EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class AnalysisAgents:
    fundamental: AgentFunction
    technical: AgentFunction
    value: AgentFunction
    news: AgentFunction
    summary: AgentFunction


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    report_markdown: str
    report_path: str | None
    target: StockTarget
    final_state: Mapping[str, Any]


def _default_agents() -> AnalysisAgents:
    from src.agents.fundamental_agent import fundamental_agent
    from src.agents.news_agent import news_agent
    from src.agents.summary_agent import summary_agent
    from src.agents.technical_agent import technical_agent
    from src.agents.value_agent import value_agent

    return AnalysisAgents(
        fundamental=fundamental_agent,
        technical=technical_agent,
        value=value_agent,
        news=news_agent,
        summary=summary_agent,
    )


def _tracked_agent(
    name: str,
    analysis_key: str,
    agent: AgentFunction,
    emit: EventSink,
) -> AgentFunction:
    async def run(state: AgentState) -> dict[str, Any]:
        await emit("agent_started", {"agent": name})
        try:
            result = await agent(state)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            await emit("agent_failed", {"agent": name, "message": message})
            return {
                "data": {
                    f"{analysis_key}_error": message,
                    analysis_key: f"该分析维度执行失败：{message}",
                }
            }

        await emit("agent_completed", {"agent": name})
        return result

    return run


def build_analysis_graph(agents: AnalysisAgents, emit: EventSink):
    """构建带用户可见生命周期事件的并行 LangGraph。"""

    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", lambda state: state)
    workflow.add_node(
        "fundamental_analyst",
        _tracked_agent("fundamental", "fundamental_analysis", agents.fundamental, emit),
    )
    workflow.add_node(
        "technical_analyst",
        _tracked_agent("technical", "technical_analysis", agents.technical, emit),
    )
    workflow.add_node(
        "value_analyst",
        _tracked_agent("value", "value_analysis", agents.value, emit),
    )
    workflow.add_node(
        "news_analyst",
        _tracked_agent("news", "news_analysis", agents.news, emit),
    )

    async def run_summary(state: AgentState) -> dict[str, Any]:
        await emit("summary_started", {"agent": "summary"})
        return await agents.summary(state)

    workflow.add_node("summarizer", run_summary)
    workflow.set_entry_point("start_node")

    for node in (
        "fundamental_analyst",
        "technical_analyst",
        "value_analyst",
        "news_analyst",
    ):
        workflow.add_edge("start_node", node)
        workflow.add_edge(node, "summarizer")

    workflow.add_edge("summarizer", END)
    return workflow.compile()


async def run_analysis(
    query: str,
    emit: EventSink,
    *,
    agents: AnalysisAgents | None = None,
) -> AnalysisResult:
    """识别标的并执行一次真实或注入的股票分析工作流。"""

    target = parse_stock_target(query)
    if not target.company_name and not target.raw_code:
        raise ValueError("无法识别股票，请输入股票名称或六位股票代码。")

    await emit(
        "stock_identified",
        {
            "company_name": target.company_name,
            "stock_code": target.raw_code,
            "market_code": target.market_code,
        },
    )
    graph = build_analysis_graph(agents or _default_agents(), emit)
    final_state = await graph.ainvoke(build_initial_state(query, target))
    data = final_state.get("data", {}) if final_state else {}
    report_markdown = data.get("final_report")
    if not isinstance(report_markdown, str) or not report_markdown.strip():
        raise RuntimeError("分析已结束，但未生成可用报告。")

    report_path = data.get("report_path")
    await emit(
        "report_completed",
        {
            "report_path": report_path,
            "report_length": len(report_markdown),
        },
    )
    return AnalysisResult(
        report_markdown=report_markdown,
        report_path=report_path if isinstance(report_path, str) else None,
        target=target,
        final_state=final_state,
    )
