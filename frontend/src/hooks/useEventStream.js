import { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../App";

/**
 * SSE hook for real-time dashboard notifications.
 *
 * Connects to GET /api/events/stream?token=<jwt> and yields parsed events.
 * Reconnects automatically on disconnect with exponential backoff.
 * If the SSE endpoint is unavailable, the app works normally (graceful degradation).
 *
 * @param {Object} options
 * @param {Function} options.onEvent - callback invoked with each event object
 * @returns {{ connected: boolean, eventCount: number }}
 */
export default function useEventStream({ onEvent } = {}) {
  const [connected, setConnected] = useState(false);
  const [eventCount, setEventCount] = useState(0);
  const retryRef = useRef(0);
  const esRef = useRef(null);
  const onEventRef = useRef(onEvent);

  // Keep callback ref fresh without re-triggering effect
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    const token = localStorage.getItem("token");
    if (!token || !API) return;

    // Close any existing connection
    if (esRef.current) {
      esRef.current.close();
    }

    const url = `${API}/events/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      retryRef.current = 0; // Reset backoff on successful connect
    };

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        setEventCount((c) => c + 1);
        if (onEventRef.current) {
          onEventRef.current(event);
        }
      } catch {
        // Ignore malformed events
      }
    };

    es.onerror = () => {
      es.close();
      setConnected(false);
      // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
      const delay = Math.min(2000 * Math.pow(2, retryRef.current), 30000);
      retryRef.current += 1;
      setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);

  return { connected, eventCount };
}
