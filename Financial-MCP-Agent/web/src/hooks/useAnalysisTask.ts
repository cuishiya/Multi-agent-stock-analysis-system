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
  const subscriptionTaskId = useRef<string | null>(null);
  const activeTaskId = useRef<string | null>(null);
  const taskGeneration = useRef(0);
  const terminalRefreshes = useRef(new Set<string>());
  const terminalRetryTimers = useRef(new Set<number>());

  const stopSubscription = useCallback((expectedTaskId?: string) => {
    if (expectedTaskId && subscriptionTaskId.current !== expectedTaskId) return;
    closeSubscription.current?.();
    closeSubscription.current = null;
    subscriptionTaskId.current = null;
  }, []);

  const clearTerminalRetries = useCallback(() => {
    terminalRetryTimers.current.forEach((timer) => window.clearTimeout(timer));
    terminalRetryTimers.current.clear();
    terminalRefreshes.current.clear();
  }, []);

  const applySnapshot = useCallback((snapshot: AnalysisTask) => {
    setTask(snapshot);
    setEvents(snapshot.events);
    if (snapshot.status === "completed" || snapshot.status === "failed") {
      sessionStorage.removeItem(SESSION_TASK_KEY);
    }
  }, []);

  const refreshTask = useCallback(async (taskId: string) => {
    const snapshot = await getAnalysis(taskId);
    if (activeTaskId.current === taskId) {
      applySnapshot(snapshot);
    }
    return snapshot;
  }, [applySnapshot]);

  const settleTerminalTask = useCallback((taskId: string) => {
    if (terminalRefreshes.current.has(taskId)) return;
    terminalRefreshes.current.add(taskId);

    const retryDelays = [750, 2000];
    const finish = () => terminalRefreshes.current.delete(taskId);
    const attempt = async (attemptIndex: number): Promise<void> => {
      if (activeTaskId.current !== taskId) {
        finish();
        return;
      }

      try {
        const snapshot = await getAnalysis(taskId);
        if (activeTaskId.current !== taskId) {
          finish();
          return;
        }
        if (snapshot.status !== "completed" && snapshot.status !== "failed") {
          throw new Error("terminal snapshot is not ready");
        }
        applySnapshot(snapshot);
        setConnectionWarning(false);
        stopSubscription(taskId);
        finish();
      } catch {
        if (activeTaskId.current !== taskId) {
          finish();
          return;
        }
        setConnectionWarning(true);
        const delay = retryDelays[attemptIndex];
        if (delay === undefined) {
          setError("分析已结束，但最终报告状态暂时无法读取，请刷新页面重试。");
          stopSubscription(taskId);
          finish();
          return;
        }
        const timer = window.setTimeout(() => {
          terminalRetryTimers.current.delete(timer);
          void attempt(attemptIndex + 1);
        }, delay);
        terminalRetryTimers.current.add(timer);
      }
    };

    void attempt(0);
  }, [applySnapshot, stopSubscription]);

  const connect = useCallback(
    (taskId: string, afterId = 0) => {
      stopSubscription();
      activeTaskId.current = taskId;
      setConnectionWarning(false);
      closeSubscription.current = subscribeToAnalysis(taskId, afterId, {
        onEvent: (event) => {
          if (activeTaskId.current !== taskId) return;
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
            const status = event.type === "report_completed"
              ? "completed"
              : event.type === "task_failed"
                ? "failed"
                : "running";
            const taskError = event.type === "task_failed"
              && typeof event.payload.message === "string"
              ? event.payload.message
              : current.error;
            return {
              ...current,
              status,
              updated_at: event.timestamp,
              report_markdown: delta
                ? `${current.report_markdown || ""}${delta}`
                : current.report_markdown,
              error: taskError,
            };
          });
          if (event.type === "report_completed" || event.type === "task_failed") {
            settleTerminalTask(taskId);
          }
        },
        onConnectionError: () => {
          if (activeTaskId.current === taskId) setConnectionWarning(true);
        },
      });
      subscriptionTaskId.current = taskId;
    },
    [settleTerminalTask, stopSubscription],
  );

  useEffect(() => {
    const taskId = sessionStorage.getItem(SESSION_TASK_KEY);
    if (taskId) {
      activeTaskId.current = taskId;
      void refreshTask(taskId)
        .then((snapshot) => {
          if (activeTaskId.current !== taskId) return;
          if (snapshot.status === "queued" || snapshot.status === "running") {
            const lastEvent = snapshot.events[snapshot.events.length - 1];
            connect(taskId, lastEvent?.id ?? 0);
          }
        })
        .catch(() => {
          if (activeTaskId.current === taskId) {
            activeTaskId.current = null;
            sessionStorage.removeItem(SESSION_TASK_KEY);
          }
        });
    }
    return () => {
      taskGeneration.current += 1;
      activeTaskId.current = null;
      clearTerminalRetries();
      stopSubscription();
    };
  }, [clearTerminalRetries, connect, refreshTask, stopSubscription]);

  const start = useCallback(
    async (query: string) => {
      const generation = taskGeneration.current + 1;
      taskGeneration.current = generation;
      activeTaskId.current = null;
      clearTerminalRetries();
      stopSubscription();
      setError(null);
      setConnectionWarning(false);
      setEvents([]);
      try {
        const created = await createAnalysis(query);
        if (taskGeneration.current !== generation) return;
        activeTaskId.current = created.task_id;
        setTask(created);
        setEvents(created.events);
        sessionStorage.setItem(SESSION_TASK_KEY, created.task_id);
        const lastEvent = created.events[created.events.length - 1];
        connect(created.task_id, lastEvent?.id ?? 0);
      } catch (reason) {
        if (taskGeneration.current !== generation) return;
        setError(reason instanceof Error ? reason.message : "无法创建分析任务。");
      }
    },
    [clearTerminalRetries, connect, stopSubscription],
  );

  const reset = useCallback(() => {
    taskGeneration.current += 1;
    activeTaskId.current = null;
    clearTerminalRetries();
    stopSubscription();
    sessionStorage.removeItem(SESSION_TASK_KEY);
    setTask(null);
    setEvents([]);
    setError(null);
    setConnectionWarning(false);
  }, [clearTerminalRetries, stopSubscription]);

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
