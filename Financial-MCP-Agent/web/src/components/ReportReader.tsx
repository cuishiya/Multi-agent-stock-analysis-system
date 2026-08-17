import { Children, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AnalysisTask } from "../types";
import { extractHeadings, headingId, sanitizeMarkdown } from "../utils/markdown";
import { ReportOutline } from "./ReportOutline";


interface ReportReaderProps {
  task: AnalysisTask;
  onNewAnalysis: () => void;
  onShowProcess: () => void;
}


function nodeText(children: React.ReactNode): string {
  return Children.toArray(children).join("");
}


export function ReportReader({ task, onNewAnalysis, onShowProcess }: ReportReaderProps) {
  const [copied, setCopied] = useState(false);
  const markdown = task.report_markdown || "";
  const safeMarkdown = useMemo(() => sanitizeMarkdown(markdown), [markdown]);
  const headings = useMemo(() => extractHeadings(safeMarkdown), [safeMarkdown]);

  async function copyReport() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="report-page">
      <header className="report-toolbar">
        <button type="button" className="text-action" onClick={onShowProcess}>← 查看执行过程</button>
        <span className="report-status">✓ 4 个研究 Agent 已完成 · 综合报告已生成</span>
        <button type="button" className="text-action" onClick={() => void copyReport()}>{copied ? "已复制" : "复制全文"}</button>
        {task.report_download_url && <a className="text-action" href={task.report_download_url}>下载 Markdown</a>}
        <button type="button" className="new-analysis" onClick={onNewAnalysis}>开始新分析 ↗</button>
      </header>

      <div className="report-document">
        <div className="report-kicker">A-SHARE INVESTMENT RESEARCH / 综合分析报告</div>
        <div className="report-meta">
          <span>{task.target?.company_name || "股票分析"}</span>
          <span>{task.target?.market_code?.toUpperCase() || "A-SHARE"}</span>
          <span>生成时间 {new Date(task.updated_at).toLocaleString("zh-CN", { hour12: false })}</span>
          <span>报告编号 {task.task_id}</span>
        </div>
        <div className="report-layout">
          <article className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 id={headingId(nodeText(children))}>{children}</h1>,
                h2: ({ children }) => <h2 id={headingId(nodeText(children))}>{children}</h2>,
                h3: ({ children }) => <h3 id={headingId(nodeText(children))}>{children}</h3>,
                a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
              }}
            >
              {safeMarkdown}
            </ReactMarkdown>
            <footer className="report-disclaimer">
              本报告由 AI 基于公开数据生成，仅用于学习研究和辅助分析，不构成投资建议。股市有风险，投资需谨慎。
            </footer>
          </article>
          <ReportOutline headings={headings} />
        </div>
      </div>
    </div>
  );
}
