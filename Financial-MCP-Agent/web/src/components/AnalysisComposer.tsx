import type { ExampleQuery } from "../types";


interface AnalysisComposerProps {
  query: string;
  examples: ExampleQuery[];
  isRunning: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
}


export function AnalysisComposer({
  query,
  examples,
  isRunning,
  onQueryChange,
  onSubmit,
}: AnalysisComposerProps) {
  return (
    <section className="composer" aria-labelledby="composer-title">
      <div className="composer-heading">
        <div>
          <span className="eyebrow">INTELLIGENCE REQUEST</span>
          <h1 id="composer-title">让四位分析师，同时研究一家公司。</h1>
        </div>
        <span className="query-hint">支持名称 / 六位代码 / 自然语言</span>
      </div>
      <form
        className="query-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label htmlFor="analysis-query">分析要求</label>
        <textarea
          id="analysis-query"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="例如：分析贵州茅台 600519 的投资价值，重点关注中长期风险"
          rows={3}
          disabled={isRunning}
        />
        <button type="submit" className="primary-action" disabled={isRunning || !query.trim()}>
          {isRunning ? "分析进行中" : "开始分析"}<span aria-hidden="true">↗</span>
        </button>
      </form>
      <div className="example-row" aria-label="示例查询">
        <span>示例输入</span>
        {examples.map((example) => (
          <button
            key={example.code}
            type="button"
            onClick={() => onQueryChange(example.query)}
            disabled={isRunning}
          >
            {example.label} <b>{example.code}</b>
          </button>
        ))}
      </div>
    </section>
  );
}
