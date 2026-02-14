/**
 * useAnalysis - Custom React hook for WebSocket-based PR analysis.
 *
 * WHY A CUSTOM HOOK?
 *   React hooks let us encapsulate stateful logic and reuse it.
 *   This hook handles:
 *     - WebSocket connection lifecycle (open/close/error)
 *     - Sending analysis requests
 *     - Receiving and processing real-time events
 *     - Tracking per-agent status for the UI
 *
 * HOW IT WORKS:
 *   1. Component calls startAnalysis(input)
 *   2. Hook opens WebSocket to /ws/analyze
 *   3. Sends the input (diff_text or pr_url)
 *   4. Processes incoming events and updates state
 *   5. Component re-renders on each state change (agents lighting up, etc.)
 *   6. When analysis_completed arrives, stores final result
 */

import { useCallback, useRef, useState } from "react";
import type {
  AgentStatus,
  AgentType,
  AnalysisResult,
  ConnectionState,
  WSEvent,
} from "../types";

const AGENTS: AgentType[] = [
  "security",
  "performance",
  "testing",
  "documentation",
  "standards",
];

function initialAgentStatuses(): AgentStatus[] {
  return AGENTS.map((name) => ({ name, status: "waiting" }));
}

export function useAnalysis() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(
    initialAgentStatuses()
  );
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const updateAgent = useCallback(
    (agentName: AgentType, update: Partial<AgentStatus>) => {
      setAgentStatuses((prev) =>
        prev.map((a) => (a.name === agentName ? { ...a, ...update } : a))
      );
    },
    []
  );

  const handleEvent = useCallback(
    (event: WSEvent) => {
      setEvents((prev) => [...prev, event]);

      switch (event.event_type) {
        case "fetch_started":
          setConnectionState("analyzing");
          break;

        case "fetch_completed":
          // PR metadata received
          break;

        case "analysis_started":
          setConnectionState("analyzing");
          // Mark all agents as running
          setAgentStatuses(
            AGENTS.map((name) => ({ name, status: "running" }))
          );
          break;

        case "agent_started":
          if (event.agent) {
            updateAgent(event.agent, { status: "running" });
          }
          break;

        case "agent_completed":
          if (event.agent && event.data) {
            updateAgent(event.agent, {
              status: "completed",
              findingsCount: event.data.findings_count as number,
              executionTime: event.data.execution_time as number,
            });
          }
          break;

        case "analysis_completed":
          setConnectionState("completed");
          if (event.data) {
            setResult(event.data as unknown as AnalysisResult);
          }
          break;

        case "error":
          setConnectionState("error");
          setError(event.message);
          break;
      }
    },
    [updateAgent]
  );

  const startAnalysis = useCallback(
    (input: { diff_text?: string; pr_url?: string }) => {
      // Reset state
      setConnectionState("connecting");
      setAgentStatuses(initialAgentStatuses());
      setEvents([]);
      setResult(null);
      setError(null);

      // Close existing connection
      if (wsRef.current) {
        wsRef.current.close();
      }

      // Determine WebSocket URL
      // In dev, Vite proxy handles /ws -> backend
      // In production, use the same host
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/analyze`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState("connected");
        // Send the analysis request
        ws.send(JSON.stringify(input));
      };

      ws.onmessage = (msg) => {
        try {
          const event: WSEvent = JSON.parse(msg.data);
          handleEvent(event);
        } catch {
          console.error("Failed to parse WebSocket message:", msg.data);
        }
      };

      ws.onerror = () => {
        setConnectionState("error");
        setError("WebSocket connection failed. Is the backend running?");
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    },
    [handleEvent]
  );

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setConnectionState("disconnected");
    setAgentStatuses(initialAgentStatuses());
    setEvents([]);
    setResult(null);
    setError(null);
  }, []);

  return {
    connectionState,
    agentStatuses,
    events,
    result,
    error,
    startAnalysis,
    reset,
  };
}
