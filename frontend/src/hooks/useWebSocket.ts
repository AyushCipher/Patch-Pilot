import { useEffect, useRef, useState } from "react";
import { wsBaseUrl } from "../api/client";
import type { TraceEvent } from "../types";

export function useRunTraceSocket(runId: string | null): {
  events: TraceEvent[];
  connected: boolean;
  finished: boolean;
} {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [finished, setFinished] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setFinished(false);

    const socket = new WebSocket(`${wsBaseUrl()}/ws/runs/${runId}`);
    socketRef.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as TraceEvent;
      if (event.type === "connection_closed") {
        setFinished(true);
        return;
      }
      setEvents((prev) => [...prev, event]);
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [runId]);

  return { events, connected, finished };
}
