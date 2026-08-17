import type { AgentKey, AnalysisEvent } from "../types";


type AgentStatus = "等待中" | "分析中" | "已完成" | "失败";

const AGENTS: Array<{ key: AgentKey; label: string; detail: string }> = [
  { key: "fundamental", label: "基本面 Agent", detail: "财报 · 盈利 · 现金流" },
  { key: "technical", label: "技术面 Agent", detail: "趋势 · 成交量 · 指标" },
  { key: "value", label: "估值 Agent", detail: "PE · PB · 安全边际" },
  { key: "news", label: "新闻 Agent", detail: "舆情 · 事件 · 风险" },
];


function statusFor(agent: AgentKey, events: AnalysisEvent[]): AgentStatus {
  let status: AgentStatus = "等待中";
  events.forEach((event) => {
    if (event.payload.agent !== agent) return;
    if (event.type === "agent_started" || event.type === "summary_started") status = "分析中";
    if (event.type === "agent_completed") status = "已完成";
    if (event.type === "agent_failed") status = "失败";
  });
  return status;
}


export function AgentOrbit({ events }: { events: AnalysisEvent[] }) {
  const summaryStatus: AgentStatus = events.some((event) => event.type === "report_completed")
    ? "已完成"
    : events.some((event) => event.type === "summary_started")
      ? "分析中"
      : "等待中";

  return (
    <section className="orbit-panel" aria-labelledby="orbit-title">
      <header className="panel-header">
        <div><span className="eyebrow">LIVE ORCHESTRATION</span><h2 id="orbit-title">Agent 协作轨道</h2></div>
        <span className="live-indicator"><i /> 实时编排</span>
      </header>
      <div className="agent-orbit">
        <div className="orbit-ring" aria-hidden="true" />
        <article className={`agent-node summary ${summaryStatus}`} aria-label={`汇总 Agent：${summaryStatus}`}>
          <span>SUMMARY</span><b>汇总 Agent</b><em>{summaryStatus}</em>
        </article>
        {AGENTS.map((agent, index) => {
          const status = statusFor(agent.key, events);
          return (
            <article
              key={agent.key}
              className={`agent-node agent-${index + 1} ${status}`}
              aria-label={`${agent.label}：${status}`}
            >
              <span>{agent.key.toUpperCase()}</span>
              <b>{agent.label}</b>
              <small>{agent.detail}</small>
              <em>{status}</em>
            </article>
          );
        })}
      </div>
      <div className="agent-mobile-list">
        {AGENTS.map((agent) => {
          const status = statusFor(agent.key, events);
          return <div key={agent.key}><span>{agent.label}</span><b>{status}</b></div>;
        })}
      </div>
    </section>
  );
}
