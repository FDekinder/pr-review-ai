/**
 * EventLog - Scrolling log of real-time WebSocket events.
 *
 * Shows each event from the backend as it arrives,
 * like a terminal/console output. Useful for debugging
 * and for showing the "behind the scenes" of the analysis.
 */

import { useEffect, useRef } from "react";
import type { WSEvent } from "../types";

interface EventLogProps {
  events: WSEvent[];
}

function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

const EVENT_COLORS: Record<string, string> = {
  fetch_started: "text-yellow-400",
  fetch_completed: "text-green-400",
  analysis_started: "text-blue-400",
  agent_started: "text-cyan-400",
  agent_completed: "text-green-400",
  analysis_completed: "text-green-300",
  error: "text-red-400",
};

export function EventLog({ events }: EventLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom as new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  if (events.length === 0) return null;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Event Log</h2>

      <div
        ref={scrollRef}
        className="bg-gray-950 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs space-y-1"
      >
        {events.map((event, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-gray-600 flex-shrink-0">
              {formatTime(event.timestamp)}
            </span>
            <span
              className={`flex-shrink-0 ${EVENT_COLORS[event.event_type] || "text-gray-400"}`}
            >
              [{event.event_type}]
            </span>
            <span className="text-gray-300">{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
