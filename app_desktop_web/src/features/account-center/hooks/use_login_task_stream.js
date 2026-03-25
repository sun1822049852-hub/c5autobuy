import { useEffect, useRef, useState } from "react";


const TERMINAL_TASK_STATES = new Set(["succeeded", "success", "failed", "cancelled", "conflict"]);


export function useLoginTaskStream({ client }) {
  const [isStarting, setIsStarting] = useState(false);
  const [taskSnapshot, setTaskSnapshot] = useState(null);
  const requestIdRef = useRef(0);

  useEffect(() => () => {
    requestIdRef.current += 1;
  }, []);

  return {
    isStarting,
    reset() {
      requestIdRef.current += 1;
      setIsStarting(false);
      setTaskSnapshot(null);
    },
    async start(accountId, { onSnapshot, onTerminal } = {}) {
      requestIdRef.current += 1;
      const requestId = requestIdRef.current;
      setIsStarting(true);
      setTaskSnapshot(null);

      try {
        const initialTask = await client.startLogin(accountId);
        if (requestId !== requestIdRef.current) {
          return null;
        }

        setTaskSnapshot(initialTask);
        await onSnapshot?.(initialTask);

        for await (const snapshot of client.watchTask(initialTask.task_id)) {
          if (requestId !== requestIdRef.current) {
            return null;
          }

          setTaskSnapshot(snapshot);
          await onSnapshot?.(snapshot);

          if (TERMINAL_TASK_STATES.has(snapshot.state)) {
            await onTerminal?.(snapshot);
            break;
          }
        }

        return initialTask;
      } finally {
        if (requestId === requestIdRef.current) {
          setIsStarting(false);
        }
      }
    },
    taskSnapshot,
  };
}
