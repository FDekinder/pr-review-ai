/**
 * App - Root component for PR Review AI frontend.
 *
 * Layout:
 *   - Header (always visible)
 *   - Left column: PR input form + Event log
 *   - Right column: Agent activity + Findings panel
 *
 * State management:
 *   All analysis state lives in the useAnalysis hook.
 *   This component just wires the hook's state to the UI components.
 */

import { AgentActivity } from "./components/AgentActivity";
import { EventLog } from "./components/EventLog";
import { FindingsPanel } from "./components/FindingsPanel";
import { Header } from "./components/Header";
import { PRInput } from "./components/PRInput";
import { useAnalysis } from "./hooks/useAnalysis";

function App() {
  const {
    connectionState,
    agentStatuses,
    events,
    result,
    error,
    startAnalysis,
    reset,
  } = useAnalysis();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Error banner */}
        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center justify-between">
            <span className="text-sm text-red-400">{error}</span>
            <button
              onClick={reset}
              className="text-xs text-red-300 hover:text-white px-3 py-1 rounded bg-red-500/20 hover:bg-red-500/30 transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left column: Input + Event log */}
          <div className="space-y-6">
            <PRInput
              onSubmit={startAnalysis}
              connectionState={connectionState}
            />
            <EventLog events={events} />
          </div>

          {/* Right column: Agent activity + Results */}
          <div className="space-y-6">
            <AgentActivity
              agentStatuses={agentStatuses}
              connectionState={connectionState}
            />

            {result && <FindingsPanel result={result} />}

            {/* New analysis button */}
            {connectionState === "completed" && (
              <button
                onClick={reset}
                className="w-full py-3 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium transition-colors"
              >
                New Analysis
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
