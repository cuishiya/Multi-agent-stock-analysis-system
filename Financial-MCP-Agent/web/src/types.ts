export type TaskStatus = "queued" | "running" | "completed" | "failed";

export type AgentKey =
  | "fundamental"
  | "technical"
  | "value"
  | "news"
  | "summary";

export type AnalysisEventType =
  | "task_created"
  | "stock_identified"
  | "agent_started"
  | "agent_progress"
  | "agent_completed"
  | "agent_failed"
  | "summary_started"
  | "report_completed"
  | "task_failed"
  | "heartbeat";

export interface AnalysisEvent {
  id: number;
  type: AnalysisEventType;
  task_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface StockTarget {
  company_name: string | null;
  stock_code: string | null;
  market_code: string | null;
}

export interface AnalysisTask {
  task_id: string;
  query: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  target: StockTarget | null;
  report_markdown: string | null;
  report_path: string | null;
  report_download_url: string | null;
  error: string | null;
  events: AnalysisEvent[];
}

export interface ExampleQuery {
  label: string;
  code: string;
  query: string;
}

export interface HealthStatus {
  web: { status: string };
  model: { configured: boolean; model: string | null };
  mcp: { configured: boolean; server: string };
}
