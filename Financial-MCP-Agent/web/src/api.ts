import type {
  AnalysisEvent,
  AnalysisEventType,
  AnalysisTask,
  ExampleQuery,
  HealthStatus,
} from "./types";


export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : null;
    throw new ApiError(detail || "请求失败，请稍后重试。", response.status);
  }
  return body as T;
}


export function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/api/health");
}


export function getExamples(): Promise<ExampleQuery[]> {
  return requestJson<ExampleQuery[]>("/api/examples");
}


export function createAnalysis(query: string): Promise<AnalysisTask> {
  return requestJson<AnalysisTask>("/api/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: query.trim() }),
  });
}


export function getAnalysis(taskId: string): Promise<AnalysisTask> {
  return requestJson<AnalysisTask>(`/api/analyses/${encodeURIComponent(taskId)}`);
}


const EVENT_TYPES: AnalysisEventType[] = [
  "task_created",
  "stock_identified",
  "agent_started",
  "agent_progress",
  "agent_completed",
  "agent_failed",
  "summary_started",
  "report_completed",
  "task_failed",
  "heartbeat",
];


interface SubscriptionHandlers {
  onEvent: (event: AnalysisEvent) => void;
  onConnectionError: () => void;
}


export function subscribeToAnalysis(
  taskId: string,
  handlers: SubscriptionHandlers,
): () => void {
  const source = new EventSource(
    `/api/analyses/${encodeURIComponent(taskId)}/events`,
  );

  EVENT_TYPES.forEach((eventType) => {
    source.addEventListener(eventType, (rawEvent) => {
      const message = rawEvent as MessageEvent<string>;
      try {
        const parsed = JSON.parse(message.data) as AnalysisEvent;
        if (eventType !== "heartbeat") {
          handlers.onEvent(parsed);
        }
      } catch {
        handlers.onConnectionError();
      }
    });
  });
  source.onerror = handlers.onConnectionError;

  return () => source.close();
}
