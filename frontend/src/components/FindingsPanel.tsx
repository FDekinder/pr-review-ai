/**
 * FindingsPanel - Displays analysis results grouped by severity.
 *
 * Shows a summary bar (critical/high/medium/low counts)
 * followed by expandable finding cards with details and suggestions.
 */

import { useState } from "react";
import type { AnalysisResult, Finding, Severity } from "../types";

interface FindingsPanelProps {
  result: AnalysisResult;
}

const SEVERITY_CONFIG: Record<
  Severity,
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  critical: {
    label: "Critical",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
  },
  high: {
    label: "High",
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
  },
  medium: {
    label: "Medium",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
  },
  low: {
    label: "Low",
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
  },
};

function SeverityBadge({ severity }: { severity: Severity }) {
  const config = SEVERITY_CONFIG[severity];
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${config.color} ${config.bgColor} border ${config.borderColor}`}
    >
      {config.label}
    </span>
  );
}

function FindingCard({ finding, index }: { finding: Finding; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity];

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-all ${config.borderColor}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-800/50 transition-colors"
      >
        <span className="text-xs text-gray-500 w-6">#{index + 1}</span>
        <SeverityBadge severity={finding.severity} />
        <span className="flex-1 text-sm text-white">{finding.title}</span>
        <span className="text-gray-500 text-sm">{expanded ? "-" : "+"}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-800">
          <div className="pt-3">
            <p className="text-sm text-gray-300">{finding.description}</p>
          </div>

          {finding.file_path && (
            <div className="text-xs text-gray-500">
              File: <span className="text-gray-300">{finding.file_path}</span>
              {finding.line_number && (
                <span>
                  {" "}
                  : Line{" "}
                  <span className="text-gray-300">{finding.line_number}</span>
                </span>
              )}
            </div>
          )}

          {finding.suggestion && (
            <div className="bg-gray-950 rounded-lg p-3">
              <div className="text-xs text-green-400 font-medium mb-1">
                Suggestion
              </div>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">
                {finding.suggestion}
              </p>
            </div>
          )}

          <div className="text-xs text-gray-500">
            Confidence: {Math.round(finding.confidence * 100)}%
          </div>
        </div>
      )}
    </div>
  );
}

export function FindingsPanel({ result }: FindingsPanelProps) {
  const [filterSeverity, setFilterSeverity] = useState<Severity | "all">("all");

  // Collect all findings from all agent results
  const allFindings = result.agent_results.flatMap((ar) => ar.findings);

  const filteredFindings =
    filterSeverity === "all"
      ? allFindings
      : allFindings.filter((f) => f.severity === filterSeverity);

  // Sort by severity priority: critical -> high -> medium -> low
  const severityOrder: Record<Severity, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
  };
  filteredFindings.sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
  );

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="text-lg font-semibold text-white mb-4">
        Analysis Results
      </h2>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {(
          [
            {
              severity: "critical" as Severity,
              count: result.critical_count,
              label: "Critical",
            },
            {
              severity: "high" as Severity,
              count: result.high_count,
              label: "High",
            },
            {
              severity: "medium" as Severity,
              count: result.medium_count,
              label: "Medium",
            },
            {
              severity: "low" as Severity,
              count: result.low_count,
              label: "Low",
            },
          ] as const
        ).map(({ severity, count, label }) => {
          const config = SEVERITY_CONFIG[severity];
          return (
            <button
              key={severity}
              onClick={() =>
                setFilterSeverity(
                  filterSeverity === severity ? "all" : severity
                )
              }
              className={`p-3 rounded-lg text-center border transition-all ${
                filterSeverity === severity
                  ? `${config.bgColor} ${config.borderColor}`
                  : "bg-gray-800/50 border-gray-700 hover:border-gray-600"
              }`}
            >
              <div className={`text-2xl font-bold ${config.color}`}>
                {count}
              </div>
              <div className="text-xs text-gray-400">{label}</div>
            </button>
          );
        })}
      </div>

      {/* Meta info */}
      <div className="flex gap-4 mb-4 text-xs text-gray-500">
        <span>Total: {result.total_findings} findings</span>
        <span>Time: {result.total_execution_time}s</span>
        <span>Agents: {result.agent_results.length}</span>
      </div>

      {/* Findings list */}
      <div className="space-y-2">
        {filteredFindings.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            {filterSeverity === "all"
              ? "No findings - code looks clean!"
              : `No ${filterSeverity} severity findings`}
          </div>
        ) : (
          filteredFindings.map((finding, i) => (
            <FindingCard key={i} finding={finding} index={i} />
          ))
        )}
      </div>
    </div>
  );
}
