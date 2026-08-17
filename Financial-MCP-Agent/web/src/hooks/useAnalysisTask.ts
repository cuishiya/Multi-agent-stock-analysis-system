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
    (taskId: string) => {
      stopSubscription();
      setConnectionWarning(false);
      closeSubscription.current = subscribeToAnalysis(taskId, {
        onEvent: (event) => {
          setConnectionWarning(false);
          setEvents((current) => {
            if (current.some((item) => item.id === event.id)) return current;
            return [...current, event].sort((a, b) => a.id - b.id);
          });
          setTask((current) =>
            current
              ? { ...current, status: "running", updated_at: event.timestamp }
              : current,
          );
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
            connect(taskId);
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
        connect(created.task_id);
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
