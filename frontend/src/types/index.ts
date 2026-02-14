/**
 * TypeScript types matching the backend Pydantic schemas.
 *
 * These mirror backend/models/schemas.py so the frontend
 * gets full type safety when working with API responses.
 */

export type Severity = "critical" | "high" | "medium" | "low";

export type AgentType =
  | "security"
  | "performance"
  | "testing"
  | "documentation"
  | "standards";

export type AnalysisStatus = "pending" | "running" | "completed" | "failed";

export interface Finding {
  title: string;
  severity: Severity;
  description: string;
  file_path: string | null;
  line_number: number | null;
  suggestion: string;
  confidence: number;
}

export interface AgentResult {
  agent: AgentType;
  status: AnalysisStatus;
  findings: Finding[];
  execution_time: number;
  model_used: string;
  error: string | null;
}

export interface PRData {
  owner: string;
  repo: string;
  pr_number: number;
  title: string;
  author?: string;
  raw_diff: string;
  files?: FileChange[];
}

export interface FileChange {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  patch: string;
}

export interface AnalysisResult {
  id: string;
  pr_data: PRData;
  agent_results: AgentResult[];
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  total_execution_time: number;
  status: AnalysisStatus;
  created_at: string;
}

/** WebSocket event from the backend */
export interface WSEvent {
  event_type: string;
  agent: AgentType | null;
  message: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

/** State of each agent during real-time analysis */
export interface AgentStatus {
  name: AgentType;
  status: "waiting" | "running" | "completed" | "error";
  findingsCount?: number;
  executionTime?: number;
}

/** Overall connection state */
export type ConnectionState = "disconnected" | "connecting" | "connected" | "analyzing" | "completed" | "error";
