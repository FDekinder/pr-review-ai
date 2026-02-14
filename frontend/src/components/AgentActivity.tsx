/**
 * AgentActivity - Real-time display of agent execution status.
 *
 * Shows each of the 5 agents with their current state:
 *   - waiting (gray, not started)
 *   - running (blue, pulsing)
 *   - completed (green, with findings count)
 *   - error (red)
 *
 * This is what makes the demo impressive: you see agents
 * light up one by one as they finish analyzing.
 */

import type { AgentStatus, ConnectionState } from "../types";

interface AgentActivityProps {
  agentStatuses: AgentStatus[];
  connectionState: ConnectionState;
}

const AGENT_LABELS: Record<string, { label: string; icon: string }> = {
  security: { label: "Security", icon: "S" },
  performance: { label: "Performance", icon: "P" },
  testing: { label: "Testing", icon: "T" },
  documentation: { label: "Documentation", icon: "D" },
  standards: { label: "Standards", icon: "Q" },
};

function StatusDot({ status }: { status: AgentStatus["status"] }) {
  const styles = {
    waiting: "bg-gray-600",
    running: "bg-blue-500 animate-pulse",
    completed: "bg-green-500",
    error: "bg-red-500",
  };

  return <span className={`w-2.5 h-2.5 rounded-full ${styles[status]}`} />;
}

export function AgentActivity({
  agentStatuses,
  connectionState,
}: AgentActivityProps) {
  if (connectionState === "disconnected") return null;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Agent Activity</h2>

      <div className="space-y-3">
        {agentStatuses.map((agent) => {
          const meta = AGENT_LABELS[agent.name] || {
            label: agent.name,
            icon: "?",
          };
          return (
            <div
              key={agent.name}
              className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                agent.status === "running"
                  ? "bg-blue-500/10 border border-blue-500/30"
                  : agent.status === "completed"
                    ? "bg-green-500/10 border border-green-500/30"
                    : "bg-gray-800/50 border border-transparent"
              }`}
            >
              {/* Agent icon */}
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                  agent.status === "completed"
                    ? "bg-green-600 text-white"
                    : agent.status === "running"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-400"
                }`}
              >
                {meta.icon}
              </div>

              {/* Agent name + status */}
              <div className="flex-1">
                <div className="text-sm font-medium text-white">
                  {meta.label} Agent
                </div>
                <div className="text-xs text-gray-400">
                  {agent.status === "waiting" && "Waiting..."}
                  {agent.status === "running" && "Analyzing..."}
                  {agent.status === "completed" &&
                    `Found ${agent.findingsCount ?? 0} issues in ${(agent.executionTime ?? 0).toFixed(1)}s`}
                  {agent.status === "error" && "Failed"}
                </div>
              </div>

              {/* Status indicator */}
              <StatusDot status={agent.status} />
            </div>
          );
        })}
      </div>

      {/* Overall status */}
      {connectionState === "analyzing" && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="flex items-center gap-2 text-sm text-blue-400">
            <span className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
            Analysis in progress...
          </div>
        </div>
      )}

      {connectionState === "completed" && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="text-sm text-green-400">All agents completed</div>
        </div>
      )}
    </div>
  );
}
