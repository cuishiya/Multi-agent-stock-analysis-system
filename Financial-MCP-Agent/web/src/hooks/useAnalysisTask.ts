import { useCallback, useEffect, useRef, useState } from "react";

import {
  createAnalysis,
  getAnalysis,
  subscribeToAnalysis,
} from "../api";
import type { AnalysisEvent, AnalysisTask } from "../types";


const SESSION_TASK_KEY = "stock-analysis-current-task";


export function useAnalysisTask() {
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connectionWarning, setConnectionWarning] = useState(false);
  const closeSubscription = useRef<(() => void) | null>(null);

  const stopSubscription = useCallback(() => {
    closeSubscription.current?.();
    closeSubscription.current = null;
  }, []);

  const refreshTask = useCallback(async (taskId: string) => {
    const snapshot = await getAnalysis(taskId);
    setTask(snapshot);
    setEvents(snapshot.events);
    if (snapshot.status === "completed" || snapshot.status === "failed") {
      sessionStorage.removeItem(SESSION_TASK_KEY);
    }
    return snapshot;
  }, []);

  const connect = useCallback(
    (taskId: string, afterId = 0) => {
      stopSubscription();
      setConnectionWarning(false);
      closeSubscription.current = subscribeToAnalysis(taskId, afterId, {
        onEvent: (event) => {
          setConnectionWarning(false);
          setEvents((current) => {
            if (current.some((item) => item.id === event.id)) return current;
            return [...current, event].sort((a, b) => a.id - b.id);
          });
          setTask((current) => {
            if (!current) return current;
            const delta = event.type === "report_delta" && typeof event.payload.delta === "string"
              ? event.payload.delta
              : "";
            return {
              ...current,
              status: "running",
              updated_at: event.timestamp,
              report_markdown: delta
                ? `${current.report_markdown || ""}${delta}`
                : current.report_markdown,
            };
          });
          if (event.type === "report_completed" || event.type === "task_failed") {
            void refreshTask(taskId).finally(stopSubscription);
          }
        },
        onConnectionError: () => setConnectionWarning(true),
      });
    },
    [refreshTask, stopSubscription],
  );

  useEffect(() => {
    const taskId = sessionStorage.getItem(SESSION_TASK_KEY);
    if (taskId) {
      void refreshTask(taskId)
        .then((snapshot) => {
          if (snapshot.status === "queued" || snapshot.status === "running") {
            const lastEvent = snapshot.events[snapshot.events.length - 1];
            connect(taskId, lastEvent?.id ?? 0);
          }
        })
        .catch(() => sessionStorage.removeItem(SESSION_TASK_KEY));
    }
    return stopSubscription;
  }, [connect, refreshTask, stopSubscription]);

  const start = useCallback(
    async (query: string) => {
      setError(null);
      setConnectionWarning(false);
      setEvents([]);
      try {
        const created = await createAnalysis(query);
        setTask(created);
        setEvents(created.events);
        sessionStorage.setItem(SESSION_TASK_KEY, created.task_id);
        const lastEvent = created.events[created.events.length - 1];
        connect(created.task_id, lastEvent?.id ?? 0);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "无法创建分析任务。");
      }
    },
    [connect],
  );

  const reset = useCallback(() => {
    stopSubscription();
    sessionStorage.removeItem(SESSION_TASK_KEY);
    setTask(null);
    setEvents([]);
    setError(null);
    setConnectionWarning(false);
  }, [stopSubscription]);

  return {
    task,
    events,
    error,
    connectionWarning,
    isRunning: task?.status === "queued" || task?.status === "running",
    start,
    reset,
  };
}
