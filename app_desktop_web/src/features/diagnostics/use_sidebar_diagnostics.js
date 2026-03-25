import { useEffect, useEffectEvent, useRef, useState } from "react";


const FOREGROUND_POLL_MS = 1500;
const BACKGROUND_POLL_MS = 5000;


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


export function useSidebarDiagnostics(client) {
  const [state, setState] = useState({
    error: "",
    isLoading: true,
    isRefreshing: false,
    snapshot: null,
  });
  const requestInFlightRef = useRef(false);

  const loadSnapshot = useEffectEvent(async ({ background = false } = {}) => {
    if (!client || requestInFlightRef.current) {
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
      setState({
        error: "",
        isLoading: false,
        isRefreshing: false,
        snapshot: nextSnapshot,
      });
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

  useEffect(() => {
    let disposed = false;
    let timerId = null;

    const scheduleNext = (delayMs) => {
      if (disposed) {
        return;
      }
      timerId = window.setTimeout(async () => {
        await loadSnapshot({ background: true });
        const nextDelay = document.visibilityState === "hidden"
          ? BACKGROUND_POLL_MS
          : FOREGROUND_POLL_MS;
        scheduleNext(nextDelay);
      }, delayMs);
    };

    void loadSnapshot({ background: false }).then(() => {
      const nextDelay = document.visibilityState === "hidden"
        ? BACKGROUND_POLL_MS
        : FOREGROUND_POLL_MS;
      scheduleNext(nextDelay);
    });

    const handleVisibilityChange = () => {
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
      scheduleNext(0);
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      disposed = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [client]);

  return {
    ...state,
    refresh: async () => {
      await loadSnapshot({ background: false });
    },
  };
}
