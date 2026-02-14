/**
 * PRInput - Input form for submitting code or PR URLs for analysis.
 *
 * Two modes:
 *   1. Paste a code diff directly
 *   2. Enter a GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
 */

import { useState } from "react";
import type { ConnectionState } from "../types";

interface PRInputProps {
  onSubmit: (input: { diff_text?: string; pr_url?: string }) => void;
  connectionState: ConnectionState;
}

const SAMPLE_CODE = `import os
import pickle

# Security: SQL injection + hardcoded secret
API_KEY = "sk-secret-12345"

def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)

# Performance: O(n^2) nested loop
def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates

# No docstrings, magic numbers, mixed naming
def calcTotal(x, y, z):
    return x * 1.08 + y * 0.95 - z * 0.1`;

export function PRInput({ onSubmit, connectionState }: PRInputProps) {
  const [mode, setMode] = useState<"diff" | "url">("diff");
  const [diffText, setDiffText] = useState("");
  const [prUrl, setPrUrl] = useState("");

  const isAnalyzing =
    connectionState === "connecting" ||
    connectionState === "connected" ||
    connectionState === "analyzing";

  const handleSubmit = () => {
    if (mode === "url" && prUrl.trim()) {
      onSubmit({ pr_url: prUrl.trim() });
    } else if (mode === "diff" && diffText.trim()) {
      onSubmit({ diff_text: diffText.trim() });
    }
  };

  const loadSample = () => {
    setMode("diff");
    setDiffText(SAMPLE_CODE);
  };

  const canSubmit =
    !isAnalyzing &&
    ((mode === "diff" && diffText.trim().length > 0) ||
      (mode === "url" && prUrl.trim().length > 0));

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Analyze Code</h2>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode("diff")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "diff"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          Paste Code
        </button>
        <button
          onClick={() => setMode("url")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "url"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          GitHub PR URL
        </button>
      </div>

      {/* Input area */}
      {mode === "diff" ? (
        <div>
          <textarea
            value={diffText}
            onChange={(e) => setDiffText(e.target.value)}
            placeholder="Paste your code or diff here..."
            className="w-full h-48 bg-gray-950 text-gray-300 border border-gray-700 rounded-lg p-3 font-mono text-sm resize-y focus:outline-none focus:border-blue-500 placeholder-gray-600"
            disabled={isAnalyzing}
          />
          <button
            onClick={loadSample}
            className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            disabled={isAnalyzing}
          >
            Load sample code with known issues
          </button>
        </div>
      ) : (
        <input
          type="text"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/pull/123"
          className="w-full bg-gray-950 text-gray-300 border border-gray-700 rounded-lg p-3 text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600"
          disabled={isAnalyzing}
        />
      )}

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className={`mt-4 w-full py-3 rounded-lg font-medium text-sm transition-all ${
          canSubmit
            ? "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer"
            : "bg-gray-800 text-gray-500 cursor-not-allowed"
        }`}
      >
        {isAnalyzing ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Analyzing...
          </span>
        ) : (
          "Start Analysis"
        )}
      </button>
    </div>
  );
}
