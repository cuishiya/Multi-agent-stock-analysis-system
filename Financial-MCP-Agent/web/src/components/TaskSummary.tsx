import type { AnalysisEvent, AnalysisTask, HealthStatus } from "../types";


const RESEARCH_AGENTS = new Set(["fundamental", "technical", "value", "news"]);


function isResearchAgentEvent(event: AnalysisEvent) {
  return typeof event.payload.agent === "string"
    && RESEARCH_AGENTS.has(event.payload.agent);
}


export function TaskSummary({
  task,
  events,
  health,
}: {
  task: AnalysisTask | null;
  events: AnalysisEvent[];
  health: HealthStatus | null;
}) {
  const completed = events.filter((event) => (
    event.type === "agent_completed" && isResearchAgentEvent(event)
  )).length;
  const failed = events.filter((event) => (
    event.type === "agent_failed" && isResearchAgentEvent(event)
  )).length;
  const progress = Math.min(((completed + failed) / 4) * 72 + (events.some((event) => event.type === "summary_started") ? 18 : 0) + (task?.status === "completed" ? 10 : 0), 100);
  return (
    <aside className="task-summary" aria-label="任务摘要">
      <div className="summary-label">RESEARCH BRIEF</div>
      {task?.target && (
        <div className="target-name">
          <span>{task.target.company_name}</span>
          <b>{task.target.market_code?.toUpperCase()}</b>
        </div>
      )}
      <div className="progress-copy"><span>总体进度</span><b>{Math.round(progress)}%</b></div>
      <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
      <dl className="summary-stats"><div><dt>完成 Agent</dt><dd>{completed} / 4</dd></div><div><dt>失败 Agent</dt><dd>{failed}</dd></div><div><dt>模型状态</dt><dd>{health?.model.configured ? "已配置" : "待配置"}</dd></div><div><dt>MCP 数据</dt><dd>{health?.mcp.configured ? "入口就绪" : "不可用"}</dd></div></dl>
      {task ? <div className="task-number">TASK {task.task_id}</div> : <p className="summary-guide">选择示例或输入股票名称和代码，系统会并行执行四个研究维度。</p>}
    </aside>
  );
}
