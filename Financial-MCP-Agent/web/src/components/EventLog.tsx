import type { AnalysisEvent } from "../types";


const AGENT_NAMES: Record<string, string> = {
  fundamental: "基本面 Agent",
  technical: "技术面 Agent",
  value: "估值 Agent",
  news: "新闻 Agent",
  summary: "汇总 Agent",
};


function eventMessage(event: AnalysisEvent): string {
  const agent = AGENT_NAMES[String(event.payload.agent)] ?? "分析任务";
  const customMessage = typeof event.payload.message === "string" ? event.payload.message : null;
  switch (event.type) {
    case "task_created": return "分析任务已创建";
    case "stock_identified": return `已识别标的 ${event.payload.company_name || ""} ${event.payload.stock_code || ""}`.trim();
    case "agent_started": return `${agent} 开始分析`;
    case "agent_progress": return customMessage || `${agent} 正在获取数据`;
    case "agent_completed": return `${agent} 分析完成`;
    case "agent_failed": return `${agent} 执行失败：${customMessage || "未知原因"}`;
    case "summary_started": return "汇总 Agent 正在整合四个维度";
    case "report_completed": return "综合分析报告已生成";
    case "task_failed": return `分析任务失败：${customMessage || "未知原因"}`;
    default: return "任务状态已更新";
  }
}


export function EventLog({ events }: { events: AnalysisEvent[] }) {
  const visible = events.filter((event) => event.type !== "heartbeat").slice(-8);
  return (
    <section className="event-panel">
      <header className="panel-header compact"><div><span className="eyebrow">EXECUTION TRACE</span><h2>执行日志</h2></div><span>最近 {visible.length} 条</span></header>
      <div className="event-log" role="log" aria-label="执行日志" aria-live="polite">
        {visible.length === 0 ? (
          <p className="empty-log">提交分析后，这里会实时显示 Agent 执行过程。</p>
        ) : visible.map((event) => (
          <div className={`event-row ${event.type.includes("failed") ? "error" : ""}`} key={event.id}>
            <time>{new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour12: false })}</time>
            <i aria-hidden="true" />
            <span>{eventMessage(event)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
