"""
LangGraph Orchestrator - Coordinates all agents in a stateful workflow.

WHY LANGGRAPH instead of just asyncio.gather()?

asyncio.gather() is simple parallel execution:
    results = await asyncio.gather(agent1.analyze(), agent2.analyze())
    # That's it. No state, no conditions, no retry, no visualization.

LangGraph gives us a STATE MACHINE:
    1. State flows through the graph — each node can read/write shared state
    2. Conditional edges — skip agents that aren't relevant
    3. Built-in visualization — see the workflow as a diagram
    4. Error recovery — retry failed nodes
    5. Checkpointing — save/restore state mid-execution

HOW IT WORKS:

    A LangGraph workflow is a directed graph where:
    - NODES are functions that process state (our agents)
    - EDGES define execution order
    - STATE is a typed dictionary that flows through the graph

    Our graph looks like this:

        START
          |
          v
       fan_out (parallel)
       /    |    |    |    |
      v     v    v    v    v
    SEC   PERF  TEST  DOC  STD   <-- All run simultaneously
      |     |    |    |    |
       v    v    v    v    v
       aggregate (combine results)
          |
          v
         END

    The "fan out / fan in" pattern is the most common multi-agent pattern.
    Agents work independently on the same input, then results are combined.

DESIGN DECISIONS:
    - We use LangGraph's Send() API for parallel fan-out
    - State is a TypedDict so LangGraph can track it
    - Each agent node wraps our existing BaseAgent.analyze() method
    - The aggregate node combines all AgentResults into one AnalysisResult
"""

import operator
import time
import uuid
from typing import Annotated, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from backend.agents.security_agent import SecurityAgent
from backend.agents.performance_agent import PerformanceAgent
from backend.agents.testing_agent import TestingAgent
from backend.agents.documentation_agent import DocumentationAgent
from backend.agents.standards_agent import StandardsAgent
from backend.models.ollama_client import OllamaClient
from backend.models.schemas import (
    AgentResult,
    AnalysisResult,
    AnalysisStatus,
    Severity,
    PRData,
)


# ============================================================
# State Definition
# ============================================================

class PRReviewState(TypedDict):
    """
    The shared state that flows through the LangGraph workflow.

    Every node (agent) can read from and write to this state.
    LangGraph tracks changes automatically.

    The Annotated[list, operator.add] syntax tells LangGraph:
    "When multiple nodes write to agent_results, APPEND (don't overwrite)."
    This is critical for parallel execution — all 5 agents add their
    results to the same list without race conditions.
    """
    # Input
    diff_text: str
    pr_data: Optional[PRData]

    # Accumulated results from agents (append-only via operator.add)
    agent_results: Annotated[list[AgentResult], operator.add]

    # Output (set by aggregate node)
    final_result: Optional[AnalysisResult]


# ============================================================
# Agent Worker State (for parallel fan-out)
# ============================================================

class AgentWorkerState(TypedDict):
    """State passed to each individual agent worker."""
    diff_text: str
    agent_name: str


# ============================================================
# Orchestrator
# ============================================================

class PRReviewOrchestrator:
    """
    LangGraph-based orchestrator that runs all agents in parallel.

    Usage:
        orchestrator = PRReviewOrchestrator()
        result = await orchestrator.run("def login(): ...")
    """

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.client = ollama_client or OllamaClient()

        # Initialize all agents with the shared client
        self.agents = {
            "security": SecurityAgent(ollama_client=self.client),
            "performance": PerformanceAgent(ollama_client=self.client),
            "testing": TestingAgent(ollama_client=self.client),
            "documentation": DocumentationAgent(ollama_client=self.client),
            "standards": StandardsAgent(ollama_client=self.client),
        }

        # Build the LangGraph workflow
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state machine.

        The graph structure:

            START --> fan_out --> [agent_worker] x5 (parallel) --> aggregate --> END

        fan_out: Reads the diff_text and sends it to all agent workers
        agent_worker: Runs a single agent and appends result to state
        aggregate: Combines all agent results into final AnalysisResult
        """
        # Create the graph with our state schema
        workflow = StateGraph(PRReviewState)

        # Add nodes
        workflow.add_node("fan_out", self._fan_out_node)
        workflow.add_node("agent_worker", self._agent_worker_node)
        workflow.add_node("aggregate", self._aggregate_node)

        # Define edges
        # START → fan_out: First thing that runs
        workflow.add_edge(START, "fan_out")

        # fan_out → agent_worker (conditional/parallel via Send)
        workflow.add_conditional_edges(
            "fan_out",
            self._route_to_agents,
            ["agent_worker"],
        )

        # agent_worker → aggregate: After all agents finish
        workflow.add_edge("agent_worker", "aggregate")

        # aggregate → END: Done
        workflow.add_edge("aggregate", END)

        return workflow.compile()

    # ============================================================
    # Graph Nodes
    # ============================================================

    async def _fan_out_node(self, state: PRReviewState) -> dict:
        """
        First node: Simply passes state through.

        The actual fan-out happens in _route_to_agents() which uses
        LangGraph's Send() API to dispatch parallel workers.
        """
        return {}

    def _route_to_agents(self, state: PRReviewState) -> list[Send]:
        """
        Conditional edge: Decides which agents to run and dispatches them.

        Uses LangGraph's Send() to create parallel worker tasks.
        Each Send() creates an independent execution of the agent_worker node
        with its own state — this is how we get parallelism.

        FUTURE ENHANCEMENT:
        This is where you'd add triage logic:
        - Small README change? Only run documentation + standards
        - SQL file changed? Prioritize security
        - Test file changed? Skip testing agent
        """
        diff_text = state["diff_text"]

        # Send to ALL agents (Phase 2 - no triage yet)
        return [
            Send("agent_worker", {"diff_text": diff_text, "agent_name": name})
            for name in self.agents.keys()
        ]

    async def _agent_worker_node(self, state: AgentWorkerState) -> dict:
        """
        Worker node: Runs a single agent and returns its result.

        This node runs in PARALLEL — LangGraph executes one instance
        per Send() from the fan_out, all at the same time.

        Returns dict with agent_results list (will be appended to state
        via the operator.add annotation).
        """
        agent_name = state["agent_name"]
        diff_text = state["diff_text"]

        agent = self.agents[agent_name]
        result = await agent.analyze(diff_text)

        # Return as a list — operator.add will append to state.agent_results
        return {"agent_results": [result]}

    async def _aggregate_node(self, state: PRReviewState) -> dict:
        """
        Final node: Combines all agent results into one AnalysisResult.

        By this point, state["agent_results"] contains results from
        all 5 agents (appended by operator.add during parallel execution).
        """
        agent_results = state.get("agent_results", [])
        pr_data = state.get("pr_data") or PRData(
            owner="local", repo="paste", pr_number=0,
            title="Direct diff analysis", raw_diff=state["diff_text"],
        )

        # Collect all findings across all agents
        all_findings = []
        for ar in agent_results:
            all_findings.extend(ar.findings)

        # Calculate total execution time (max of agents, since they run in parallel)
        max_time = max((ar.execution_time for ar in agent_results), default=0)

        final_result = AnalysisResult(
            id=str(uuid.uuid4())[:8],
            pr_data=pr_data,
            agent_results=agent_results,
            total_findings=len(all_findings),
            critical_count=sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
            high_count=sum(1 for f in all_findings if f.severity == Severity.HIGH),
            medium_count=sum(1 for f in all_findings if f.severity == Severity.MEDIUM),
            low_count=sum(1 for f in all_findings if f.severity == Severity.LOW),
            total_execution_time=round(max_time, 2),
            status=AnalysisStatus.COMPLETED,
        )

        return {"final_result": final_result}

    # ============================================================
    # Public API
    # ============================================================

    async def run(self, diff_text: str, pr_data: Optional[PRData] = None) -> AnalysisResult:
        """
        Run the full multi-agent analysis.

        This is the main entry point. It:
        1. Creates the initial state
        2. Executes the LangGraph workflow
        3. Returns the combined AnalysisResult

        Under the hood, LangGraph:
        - Sends diff_text to all 5 agents in parallel
        - Waits for all to complete
        - Aggregates results
        - Returns final state
        """
        initial_state: PRReviewState = {
            "diff_text": diff_text,
            "pr_data": pr_data,
            "agent_results": [],
            "final_result": None,
        }

        # Execute the graph
        final_state = await self.graph.ainvoke(initial_state)

        return final_state["final_result"]
