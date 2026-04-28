import { useEffect, useEffectEvent, useRef, useState } from "react";

const MAX_RETAINED_EVENT_ROWS = 500;
const MAX_RETAINED_ACCOUNT_ROWS = 40;
const MAX_RETAINED_LOGIN_TASKS = 40;


function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}


function isSidebarDiagnosticsSnapshot(value) {
  return isObject(value)
    && isObject(value.summary)
    && isObject(value.query)
    && isObject(value.purchase)
    && isObject(value.login_tasks)
    && typeof value.updated_at === "string";
}


function toErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "诊断数据加载失败";
}


function asArray(value) {
  return Array.isArray(value) ? value : [];
}


function normalizeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}


function hasRawDetails(row) {
  return Boolean(
    row?.status_code
    || row?.http_status
    || row?.response_status
    || row?.request_method
    || row?.request_path
    || row?.path
    || row?.response_text
    || row?.raw_response
    || row?.response_body
    || row?.payload
    || row?.result
    || row?.error
    || row?.error_message,
  );
}


function isErrorLike(value) {
  const normalized = normalizeText(value).toLowerCase();
  return normalized === "error"
    || normalized === "failed"
    || normalized === "failure"
    || normalized === "conflict"
    || normalized === "cancelled";
}


function isRetainableEvent(_row) {
  // 保留全部事件（后端已限 500 条）
  return true;
}


function isRetainableAccountRow(row) {
  return Boolean(normalizeText(row?.last_error || row?.disabled_reason));
}


function isRetainableLoginTask(task) {
  return isErrorLike(task?.state)
    || Boolean(normalizeText(task?.error))
    || asArray(task?.events).some((event) => isRetainableEvent(event));
}


function getRowTime(row) {
  return normalizeText(
    row?.timestamp
    || row?.occurred_at
    || row?.updated_at
    || row?.started_at
    || row?.last_seen_at,
  );
}


function compareRowsByTimeDesc(left, right) {
  const leftTime = getRowTime(left);
  const rightTime = getRowTime(right);

  if (leftTime === rightTime) {
    return 0;
  }
  return leftTime < rightTime ? 1 : -1;
}


function buildEventSignature(row) {
  return [
    getRowTime(row),
    normalizeText(row?.level || row?.status || row?.state),
    normalizeText(row?.account_id),
    normalizeText(row?.account_display_name),
    normalizeText(row?.query_item_id || row?.query_item_name),
    normalizeText(row?.message || row?.last_message),
    normalizeText(row?.error || row?.error_message),
    normalizeText(row?.status_code || row?.http_status || row?.response_status),
    normalizeText(row?.request_method || row?.method),
    normalizeText(row?.request_path || row?.path || row?.url_path),
    normalizeText(row?.response_text || row?.raw_response || row?.response_body),
  ].join("|");
}


function buildAccountRowSignature(row) {
  return [
    normalizeText(row?.account_id),
    normalizeText(row?.display_name),
    normalizeText(row?.mode_type || row?.purchase_pool_state),
    normalizeText(row?.last_error || row?.disabled_reason),
  ].join("|");
}


function buildTaskSignature(task) {
  return normalizeText(task?.task_id)
    || [
      normalizeText(task?.account_id),
      normalizeText(task?.started_at),
      normalizeText(task?.state),
    ].join("|");
}


function mergeUniqueRows(previousRows, nextRows, { getKey, shouldRetain, maxRows }) {
  const rowsByKey = new Map();

  for (const row of asArray(previousRows)) {
    if (!shouldRetain(row)) {
      continue;
    }
    const key = getKey(row);
    if (key) {
      rowsByKey.set(key, row);
    }
  }

  for (const row of asArray(nextRows)) {
    const key = getKey(row);
    if (!key) {
      continue;
    }
    const current = rowsByKey.get(key);
    rowsByKey.set(key, current ? { ...current, ...row } : row);
  }

  return Array.from(rowsByKey.values())
    .sort(compareRowsByTimeDesc)
    .slice(0, maxRows);
}


function takeLatestRows(rows, { maxRows }) {
  return asArray(rows)
    .slice()
    .sort(compareRowsByTimeDesc)
    .slice(0, maxRows);
}


function mergeLoginTask(previousTask, nextTask) {
  return {
    ...previousTask,
    ...nextTask,
    error: nextTask.error || previousTask.error,
    last_message: nextTask.last_message || previousTask.last_message,
    events: mergeUniqueRows(previousTask.events, nextTask.events, {
      getKey: buildEventSignature,
      maxRows: MAX_RETAINED_EVENT_ROWS,
      shouldRetain: isRetainableEvent,
    }),
  };
}


function mergeLoginTasks(previousTasks, nextTasks) {
  const tasksById = new Map();

  for (const task of asArray(previousTasks)) {
    if (!isRetainableLoginTask(task)) {
      continue;
    }
    const key = buildTaskSignature(task);
    if (key) {
      tasksById.set(key, task);
    }
  }

  for (const task of asArray(nextTasks)) {
    const key = buildTaskSignature(task);
    if (!key) {
      continue;
    }
    const previousTask = tasksById.get(key);
    tasksById.set(key, previousTask ? mergeLoginTask(previousTask, task) : task);
  }

  return Array.from(tasksById.values())
    .sort(compareRowsByTimeDesc)
    .slice(0, MAX_RETAINED_LOGIN_TASKS);
}


function retainErrorText(nextValue, previousValue) {
  return normalizeText(nextValue) || normalizeText(previousValue) || "";
}


function mergeDiagnosticsSnapshot(previousSnapshot, nextSnapshot) {
  if (!previousSnapshot) {
    return nextSnapshot;
  }

  return {
    ...nextSnapshot,
    summary: {
      ...nextSnapshot.summary,
      last_error: normalizeText(nextSnapshot.summary.last_error),
    },
    query: {
      ...nextSnapshot.query,
      last_error: retainErrorText(nextSnapshot.query.last_error, previousSnapshot.query?.last_error),
      account_rows: mergeUniqueRows(previousSnapshot.query?.account_rows, nextSnapshot.query.account_rows, {
        getKey: buildAccountRowSignature,
        maxRows: MAX_RETAINED_ACCOUNT_ROWS,
        shouldRetain: isRetainableAccountRow,
      }),
      recent_events: takeLatestRows(nextSnapshot.query.recent_events, {
        maxRows: MAX_RETAINED_EVENT_ROWS,
      }),
    },
    purchase: {
      ...nextSnapshot.purchase,
      last_error: retainErrorText(nextSnapshot.purchase.last_error, previousSnapshot.purchase?.last_error),
      account_rows: mergeUniqueRows(previousSnapshot.purchase?.account_rows, nextSnapshot.purchase.account_rows, {
        getKey: buildAccountRowSignature,
        maxRows: MAX_RETAINED_ACCOUNT_ROWS,
        shouldRetain: isRetainableAccountRow,
      }),
      recent_events: takeLatestRows(nextSnapshot.purchase.recent_events, {
        maxRows: MAX_RETAINED_EVENT_ROWS,
      }),
    },
    login_tasks: {
      ...nextSnapshot.login_tasks,
      recent_tasks: mergeLoginTasks(previousSnapshot.login_tasks?.recent_tasks, nextSnapshot.login_tasks.recent_tasks),
    },
  };
}


export function useSidebarDiagnostics(client, { enabled = true } = {}) {
  const [state, setState] = useState({
    error: "",
    isLoading: true,
    isRefreshing: false,
    snapshot: null,
  });
  const [isDocumentVisible, setIsDocumentVisible] = useState(() => document.visibilityState !== "hidden");
  const requestInFlightRef = useRef(false);
  const snapshotRef = useRef(null);
  const streamCleanupRef = useRef(() => {});
  const shouldLoadSnapshot = enabled;

  useEffect(() => {
    snapshotRef.current = state.snapshot;
  }, [state.snapshot]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsDocumentVisible(document.visibilityState !== "hidden");
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  const loadSnapshot = useEffectEvent(async ({ background = false } = {}) => {
    if (!shouldLoadSnapshot || !client || requestInFlightRef.current) {
      return;
    }

    requestInFlightRef.current = true;
    setState((current) => ({
      ...current,
      error: "",
      isLoading: current.snapshot === null && !background,
      isRefreshing: background || current.snapshot !== null,
    }));

    try {
      const nextSnapshot = await client.getSidebarDiagnostics();
      if (!isSidebarDiagnosticsSnapshot(nextSnapshot)) {
        throw new Error("诊断数据格式错误");
      }
      setState((current) => ({
        error: "",
        isLoading: false,
        isRefreshing: false,
        snapshot: mergeDiagnosticsSnapshot(current.snapshot, nextSnapshot),
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        error: toErrorMessage(error),
        isLoading: false,
        isRefreshing: false,
      }));
    } finally {
      requestInFlightRef.current = false;
    }
  });

  const stopStream = () => {
    const cleanup = streamCleanupRef.current;
    streamCleanupRef.current = () => {};
    cleanup?.();
  };

  useEffect(() => {
    if (!client || !enabled) {
      stopStream();
      return undefined;
    }

    if (!isDocumentVisible) {
      stopStream();
      return undefined;
    }

    let disposed = false;
    const startStream = () => {
      stopStream();
      const iterator = client.watchSidebarDiagnosticsUpdates();
      let streamDisposed = false;
      streamCleanupRef.current = () => {
        streamDisposed = true;
        Promise.resolve(iterator.return?.()).catch(() => {});
      };

      void (async () => {
        try {
          for await (const nextSnapshot of iterator) {
            if (disposed || streamDisposed) {
              return;
            }
            if (!isSidebarDiagnosticsSnapshot(nextSnapshot)) {
              throw new Error("诊断数据格式错误");
            }
            setState((current) => ({
              error: "",
              isLoading: false,
              isRefreshing: false,
              snapshot: mergeDiagnosticsSnapshot(current.snapshot, nextSnapshot),
            }));
          }
        } catch (error) {
          if (disposed || streamDisposed) {
            return;
          }
          setState((current) => ({
            ...current,
            error: toErrorMessage(error),
            isLoading: false,
            isRefreshing: false,
          }));
        }
      })();
    };

    void loadSnapshot({ background: snapshotRef.current !== null }).then(() => {
      if (disposed) {
        return;
      }
      startStream();
    });

    return () => {
      disposed = true;
      stopStream();
    };
  }, [client, enabled, isDocumentVisible]);

  return {
    ...state,
    refresh: async () => {
      await loadSnapshot({ background: false });
    },
  };
}
