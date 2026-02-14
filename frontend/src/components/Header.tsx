/**
 * Header - App title bar with branding.
 */
export function Header() {
  return (
    <header className="bg-gray-900 border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center gap-3">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
          PR
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white">PR Review AI</h1>
          <p className="text-xs text-gray-400">
            Multi-agent code analysis powered by local LLMs
          </p>
        </div>
      </div>
    </header>
  );
}
