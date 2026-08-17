import { useEffect, useRef, useState } from "react";

import { getExamples, getHealth } from "./api";
import { AgentOrbit } from "./components/AgentOrbit";
import { AnalysisComposer } from "./components/AnalysisComposer";
import { EventLog } from "./components/EventLog";
import { ReportReader } from "./components/ReportReader";
import { Sidebar } from "./components/Sidebar";
import { TaskSummary } from "./components/TaskSummary";
import { useAnalysisTask } from "./hooks/useAnalysisTask";
import type { ExampleQuery, HealthStatus } from "./types";


export default function App() {
  const [query, setQuery] = useState("");
  const [examples, setExamples] = useState<ExampleQuery[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [showReport, setShowReport] = useState(true);
  const openedReportTask = useRef<string | null>(null);
  const analysis = useAnalysisTask();

  useEffect(() => {
    void getExamples().then(setExamples).catch(() => setExamples([]));
    void getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (
      analysis.task?.report_markdown &&
      openedReportTask.current !== analysis.task.task_id
    ) {
      openedReportTask.current = analysis.task.task_id;
      setShowReport(true);
    }
    if (analysis.task?.status === "completed" && analysis.task.report_markdown) {
      setShowReport(true);
    }
  }, [analysis.task?.report_markdown, analysis.task?.status, analysis.task?.task_id]);

  if (analysis.task?.report_markdown && showReport) {
    return (
      <div className="app-shell">
        <Sidebar active="report" />
        <main className="app-main">
          <ReportReader
            task={analysis.task}
            onShowProcess={() => setShowReport(false)}
            onNewAnalysis={() => {
              analysis.reset();
              openedReportTask.current = null;
              setQuery("");
              setShowReport(false);
            }}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar active="workspace" />
      <main className="app-main">
        <header className="topbar">
          <span className="mobile-brand">股票分析 Agent 系统</span>
          <div className="system-pill"><i className={health?.web.status === "online" ? "online" : ""} /> Web 服务</div>
          <div className="system-pill"><i className={health?.mcp.configured ? "online" : "warning"} /> MCP 数据</div>
          <div className="system-pill"><i className={health?.model.configured ? "online" : "warning"} /> {health?.model.model || "模型待配置"}</div>
          <span className="market-label">A-SHARE RESEARCH TERMINAL</span>
        </header>
        <div className="workspace">
          <AnalysisComposer
            query={query}
            examples={examples}
            isRunning={analysis.isRunning}
            onQueryChange={setQuery}
            onSubmit={() => void analysis.start(query)}
          />
          {analysis.error && <div className="alert error-alert" role="alert">{analysis.error}</div>}
          {analysis.connectionWarning && <div className="alert warning-alert" role="status">实时连接中断，正在尝试恢复…已有进度不会丢失。</div>}
          {analysis.task?.status === "completed" && analysis.task.report_markdown && (
            <div className="report-ready"><span>综合分析报告已生成。</span><button type="button" onClick={() => setShowReport(true)}>阅读报告 →</button></div>
          )}
          <div className="workspace-grid">
            <div className="analysis-stage">
              <AgentOrbit events={analysis.events} />
              <EventLog events={analysis.events} />
            </div>
            <TaskSummary task={analysis.task} events={analysis.events} health={health} />
          </div>
        </div>
      </main>
    </div>
  );
}
