import type { MarkdownHeading } from "../utils/markdown";


export function ReportOutline({ headings }: { headings: MarkdownHeading[] }) {
  const sections = headings.filter((heading) => heading.depth > 1);
  return (
    <nav className="report-outline" aria-label="报告目录">
      <span>报告目录</span>
      {sections.map((heading) => (
        <a key={heading.id} href={`#${heading.id}`} className={`depth-${heading.depth}`}>
          {heading.text}
        </a>
      ))}
      <div className="outline-note">
        <b>AI 研究说明</b>
        报告由多个 Agent 基于公开数据生成，请结合原始披露独立判断。
      </div>
    </nav>
  );
}
