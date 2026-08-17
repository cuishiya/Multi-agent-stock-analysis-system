interface SidebarProps {
  active: "workspace" | "report";
}


export function Sidebar({ active }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand-mark" aria-hidden="true"><span>SA</span></div>
      <div className="brand-name">股票分析<br />Agent 系统</div>
      <nav aria-label="主导航">
        <span className={active === "workspace" ? "nav-item active" : "nav-item"}>
          <i aria-hidden="true">◈</i> 智能分析
        </span>
        <span className={active === "report" ? "nav-item active" : "nav-item"}>
          <i aria-hidden="true">⌁</i> 分析报告
        </span>
        <span className="nav-item"><i aria-hidden="true">◎</i> 系统状态</span>
      </nav>
      <div className="sidebar-meta">
        <span>LANGGRAPH × MCP</span>
        <span>FOUR-AGENT RESEARCH</span>
        <p>基于公开数据的辅助研究<br />不构成任何投资建议</p>
      </div>
    </aside>
  );
}
