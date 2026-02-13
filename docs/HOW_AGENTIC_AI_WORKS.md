# How Agentic AI Works — A Complete Guide

## Written for developers who have never built an AI agent before

This document explains what Agentic AI is, why it matters, and exactly how our
PR Review system works — line by line, concept by concept. By the end, you'll
understand how to design, build, and reason about multi-agent AI systems.

---

## Table of Contents

1. [What is "Agentic AI"?](#1-what-is-agentic-ai)
2. [Regular LLM Call vs Agent — The Core Difference](#2-regular-llm-call-vs-agent--the-core-difference)
3. [The 5 Properties That Make Something an "Agent"](#3-the-5-properties-that-make-something-an-agent)
4. [Our System Architecture — The Full Picture](#4-our-system-architecture--the-full-picture)
5. [Layer by Layer Breakdown](#5-layer-by-layer-breakdown)
6. [The Life of a Request — Following Code Through the System](#6-the-life-of-a-request--following-code-through-the-system)
7. [Prompt Engineering — The Secret Sauce](#7-prompt-engineering--the-secret-sauce)
8. [Design Patterns Used (and Why)](#8-design-patterns-used-and-why)
9. [The Hard Problem — LLMs Are Unpredictable](#9-the-hard-problem--llms-are-unpredictable)
10. [Multi-Agent Orchestration (What Comes Next)](#10-multi-agent-orchestration-what-comes-next)
11. [Key Takeaways](#11-key-takeaways)
12. [Glossary](#12-glossary)

---

## 1. What is "Agentic AI"?

**Agentic AI** is a design pattern where you give an LLM (Large Language Model) a
specific role, structured inputs, and expect structured outputs — turning it from
a generic chatbot into a specialized worker that can be part of a larger system.

Think of it like this:

```
ChatGPT (non-agentic):
    Human: "Review this code"
    AI: "Here are some thoughts..." (free-form text, unpredictable format)
    Human: *manually reads and interprets the response*

Our PR Review System (agentic):
    System → SecurityAgent: "Analyze this diff for vulnerabilities"
    SecurityAgent → System: {findings: [{title: "SQL Injection", severity: "critical", ...}]}
    System → automatically categorizes, counts, stores, and displays results
```

The key shift: **the AI isn't talking to a human anymore — it's a component in a
software pipeline.** Its output gets parsed by code, not read by eyes.

---

## 2. Regular LLM Call vs Agent — The Core Difference

### Regular LLM Call

```python
# This is NOT an agent. This is just calling an API.
response = ollama.generate(
    model="qwen2.5-coder:7b",
    prompt="Review this code for security issues: " + code
)
print(response)  # Raw text. Hope it's useful.
```

Problems with this approach:
- You get back raw text — could be any format, any length
- No error handling — if the LLM hallucinates, you get garbage
- No structure — you can't programmatically extract "3 critical issues found"
- No metadata — you don't know how long it took, how confident it is
- Not testable — you can't write unit tests against unpredictable output

### Agent

```python
# This IS an agent. It's a self-contained analysis unit.
agent = SecurityAgent(ollama_client=client)
result = await agent.analyze(code)

# result is a typed object, not raw text
print(result.status)           # "completed"
print(result.findings[0].title) # "SQL Injection"
print(result.findings[0].severity) # "critical"
print(result.execution_time)    # 8.92
```

What the agent does internally:
1. Wraps the code in a carefully engineered prompt
2. Tells the LLM to respond in JSON (not free-form text)
3. Parses and validates the JSON response
4. Normalizes messy data (e.g., "HIGH" → "high" → Severity.HIGH)
5. Handles errors gracefully (returns FAILED status, doesn't crash)
6. Reports metadata (timing, model used, confidence)

**The agent is a bridge between the unpredictable world of LLMs and the
structured world of software engineering.**

---

## 3. The 5 Properties That Make Something an "Agent"

Not every LLM call is an agent. Here are the 5 properties that distinguish
an agent from a simple API call:

### Property 1: Identity (System Prompt)

An agent has a defined role. This is set via the "system prompt" — instructions
that tell the LLM who it is and how to behave.

```python
# From our SecurityAgent (security_agent.py)
system_prompt = """You are an expert code security auditor. Your job is to
analyze code changes (diffs) and identify security vulnerabilities.

You have deep knowledge of:
- OWASP Top 10 vulnerabilities
- Language-specific security pitfalls
- Secure coding best practices
- Common attack vectors and exploitation techniques

IMPORTANT RULES:
- Only report REAL vulnerabilities you can see in the code.
- Focus on code that was ADDED or MODIFIED.
- Rate severity accurately based on exploitability and impact.

Always respond with valid JSON."""
```

Without a system prompt, the LLM is a generalist. With one, it becomes a
specialist. The quality of this prompt is the #1 factor in agent performance.

### Property 2: Structured Input

An agent doesn't just receive raw text. It receives data in a defined format
and wraps it in a carefully constructed prompt.

```python
# From SecurityAgent.build_prompt()
def build_prompt(self, diff_text: str) -> str:
    return f"""Analyze the following code for security vulnerabilities.

CHECK FOR THESE SPECIFIC ISSUES:
1. SQL Injection: String formatting in SQL queries
2. Command Injection: User input passed to os.system()
3. Hardcoded Secrets: API keys, passwords in source code
...

SEVERITY GUIDELINES:
- critical: Directly exploitable, leads to data breach
- high: Serious flaw, exploitable with some effort
- medium: Could be exploited in specific conditions
- low: Minor concern or best practice violation

CODE TO ANALYZE:
```
{diff_text}
```

Respond with JSON in this EXACT format:
{{"findings": [{{"title": "...", "severity": "...", ...}}]}}"""
```

Notice: the prompt tells the LLM EXACTLY what to look for, how to rate it,
and what format to respond in. This isn't a conversation — it's a specification.

### Property 3: Structured Output

An agent returns typed, validated data — not raw text.

```python
# From schemas.py — what the agent returns
class Finding(BaseModel):
    agent: AgentType          # Which agent found this
    severity: Severity        # critical, high, medium, low (enum, not string)
    title: str                # "SQL Injection Risk"
    description: str          # Detailed explanation
    file_path: Optional[str]  # Which file
    line_number: Optional[int]# Which line
    suggestion: Optional[str] # How to fix it
    confidence: float         # 0.0 to 1.0

class AgentResult(BaseModel):
    agent: AgentType
    status: AnalysisStatus    # completed, failed
    findings: list[Finding]
    execution_time: float
    model_used: str
    error: Optional[str]
```

Because the output is typed (Pydantic models), the rest of the system can
reliably work with it: count findings, filter by severity, store in a database,
display in a UI. No guessing, no parsing, no "I hope the AI formatted it right."

### Property 4: Error Handling

An agent handles its own failures. If the LLM returns garbage, if the connection
drops, if the model hallucinates invalid JSON — the agent doesn't crash. It
returns a structured error.

```python
# From BaseAgent.analyze()
async def analyze(self, diff_text: str) -> AgentResult:
    try:
        prompt = self.build_prompt(diff_text)
        result = await self.client.generate_json(...)
        findings = self.parse_response(result["data"])
        return AgentResult(status=AnalysisStatus.COMPLETED, findings=findings)

    except Exception as e:
        # NEVER crash. Return a structured failure instead.
        return AgentResult(
            status=AnalysisStatus.FAILED,
            findings=[],
            error=str(e),
        )
```

This is critical for multi-agent systems. If one agent fails, the others
still complete their work. A system that crashes when any one component
fails is useless in production.

### Property 5: Self-Awareness (Metadata)

An agent reports what it did: how long it took, which model it used, how
confident it is. This metadata is essential for:

- **Debugging**: "Why did this take 30 seconds?" → model was loading
- **Optimization**: "Which agent is the bottleneck?" → look at execution_time
- **Trust**: "Should I believe this finding?" → check confidence score
- **Monitoring**: "Is the system healthy?" → track success/failure rates

```python
return AgentResult(
    agent=self.agent_type,        # "security"
    status=AnalysisStatus.COMPLETED,
    findings=findings,
    execution_time=round(elapsed, 2),  # 8.92 seconds
    model_used=self.model,             # "qwen2.5-coder:7b"
)
```

---

## 4. Our System Architecture — The Full Picture

Here's how every piece connects, from the user's HTTP request down to the
GPU running inference:

```
                           ┌─────────────────────────────────┐
                           │        User / Frontend          │
                           │  POST /api/analyze              │
                           │  {"diff_text": "def login..."}  │
                           └──────────────┬──────────────────┘
                                          │ HTTP
                                          ▼
                           ┌──────────────────────────────────┐
                           │  FastAPI App  (main.py)          │
                           │  - CORS middleware               │
                           │  - Request validation            │
                           │  - Route dispatching             │
                           └──────────────┬───────────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────────┐
                           │  API Routes  (routes.py)         │
                           │  - POST /api/analyze             │
                           │  - GET  /api/analysis/{id}       │
                           │  - GET  /api/history             │
                           │  - GET  /api/health              │
                           └──────────────┬───────────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────────┐
                           │  Analysis Service                │
                           │  (analysis_service.py)           │
                           │  - Coordinates agents            │
                           │  - Combines results              │
                           │  - Stores history                │
                           └──────────────┬───────────────────┘
                                          │
                        ┌─────────────────┼─────────────────┐
                        │ (Phase 2: parallel)               │
                        ▼                 ▼                 ▼
                ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                │  Security    │ │ Performance  │ │  Testing     │
                │  Agent       │ │ Agent        │ │  Agent       │
                │  (7B model)  │ │ (7B model)   │ │ (3B model)   │
                └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                       │                │                 │
                       └────────────────┼─────────────────┘
                                        │
                                        ▼
                           ┌──────────────────────────────────┐
                           │  Ollama Client                   │
                           │  (ollama_client.py)              │
                           │  - HTTP to localhost:11434       │
                           │  - JSON mode enforcement         │
                           │  - Timeout handling              │
                           └──────────────┬───────────────────┘
                                          │ HTTP
                                          ▼
                           ┌──────────────────────────────────┐
                           │  Ollama Service                  │
                           │  - Loads model into GPU VRAM     │
                           │  - Runs inference                │
                           │  - Returns generated text        │
                           │                                  │
                           │  Hardware: RTX 5080 (16GB VRAM)  │
                           └──────────────────────────────────┘
```

### The Key Insight: Layers of Abstraction

Each layer only knows about the layer directly below it:

| Layer | Knows About | Doesn't Know About |
|-------|------------|-------------------|
| API Routes | HTTP, request formats | How agents work |
| Analysis Service | Which agents to run | HTTP, request parsing |
| Agents | Their specialty, prompt building | Other agents, HTTP |
| OllamaClient | How to call Ollama's API | What agents do with responses |
| Ollama | How to run model inference | What the application is |

This separation means you can change any layer without breaking the others.
Want to swap Ollama for OpenAI? Only change OllamaClient. Want to add a new
agent? Only change the agent folder and analysis_service. Want to switch from
FastAPI to Django? Only change the api folder.

---

## 5. Layer by Layer Breakdown

### Layer 1: Configuration (config.py)

Every application needs settings. Instead of hardcoding values like
`"http://localhost:11434"` everywhere, we centralize them:

```python
class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    fast_model: str = "llama3.2:3b"
    balanced_model: str = "qwen2.5-coder:7b"
    github_token: str = ""
    max_agent_timeout: int = 120
```

`BaseSettings` from Pydantic automatically reads environment variables.
Set `OLLAMA_BASE_URL=http://other-host:11434` and it overrides the default.
This means zero code changes between development and production.

### Layer 2: Data Models (schemas.py)

These Pydantic models define the "shape" of data flowing through the system.
Think of them as contracts:

- **Finding**: "A security issue looks like this: title, severity, description..."
- **AgentResult**: "An agent's output looks like this: status, findings, timing..."
- **AnalysisResult**: "A complete analysis looks like this: all agent results combined..."

Why this matters: if any code tries to create a Finding with `severity="banana"`,
Pydantic raises a validation error immediately. Without these schemas, that bug
would silently propagate and crash something downstream an hour later.

### Layer 3: OllamaClient (ollama_client.py)

This is the bridge between Python and the local LLM. Two critical methods:

**`generate()`** — calls the LLM and gets raw text back:
```python
async def generate(self, model, prompt, system_prompt=None, temperature=0.1):
    payload = {
        "model": model,         # "qwen2.5-coder:7b"
        "prompt": prompt,       # The analysis question
        "system": system_prompt, # The agent's identity
        "stream": False,        # Get complete response at once
        "options": {"temperature": temperature},  # 0.1 = deterministic
    }
    response = await self.client.post("/api/generate", json=payload)
    return response.json()
```

**`generate_json()`** — same thing but forces JSON output:
```python
async def generate_json(self, model, prompt, ...):
    # Tell Ollama to constrain output to valid JSON
    payload["format"] = "json"
    result = await self.generate(...)
    # Parse the string into a Python dict
    return json.loads(result["response"])
```

The `format: "json"` flag is crucial. Without it, the LLM might return:
```
Here are the issues I found:
1. SQL Injection - the query uses f-strings...
```

With it, you reliably get:
```json
{"findings": [{"title": "SQL Injection", "severity": "critical", ...}]}
```

### Layer 4: BaseAgent (base_agent.py)

This is the "template" that all agents follow. It implements the **Template
Method Pattern** — it defines the workflow, and subclasses fill in the blanks:

```
BaseAgent defines:
    analyze()         → the full pipeline (timing, error handling, calling LLM)
    parse_response()  → converting JSON to Finding objects

Subclasses define:
    system_prompt     → "You are a security expert..." / "You are a performance expert..."
    build_prompt()    → what specific questions to ask about the code
    model             → which LLM to use (3B for simple, 7B for complex)
```

The `analyze()` method is the heart of every agent:

```python
async def analyze(self, diff_text: str) -> AgentResult:
    start_time = time.time()
    try:
        # Step 1: Build the prompt (subclass-specific)
        prompt = self.build_prompt(diff_text)

        # Step 2: Call the LLM
        result = await self.client.generate_json(
            model=self.model,
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

        # Step 3: Parse LLM response into typed Finding objects
        findings = self.parse_response(result["data"])

        # Step 4: Return structured result with metadata
        return AgentResult(
            status=AnalysisStatus.COMPLETED,
            findings=findings,
            execution_time=time.time() - start_time,
            model_used=self.model,
        )
    except Exception as e:
        # Step 5: Handle failure gracefully
        return AgentResult(status=AnalysisStatus.FAILED, error=str(e))
```

### Layer 5: SecurityAgent (security_agent.py)

This is surprisingly small — only ~50 lines of unique code. Everything else
is inherited from BaseAgent. The agent only defines:

1. **What it is**: `agent_type = AgentType.SECURITY`
2. **Which model to use**: `model = "qwen2.5-coder:7b"` (needs reasoning ability)
3. **Its identity**: system_prompt saying "You are a security expert..."
4. **What to look for**: build_prompt() listing SQL injection, XSS, etc.

This is the power of the BaseAgent pattern. Adding a new agent (Performance,
Testing, etc.) is just defining these 4 things. The pipeline, error handling,
parsing, timing — all inherited for free.

### Layer 6: AnalysisService (analysis_service.py)

This coordinates everything. It's the "manager" that:

1. Creates an OllamaClient (shared across all agents)
2. Initializes agents
3. Runs them on the code
4. Combines their results
5. Stores results for retrieval

```python
async def analyze_diff(self, diff_text):
    analysis_id = str(uuid.uuid4())[:8]  # Unique ID like "2b227e77"

    # Run agent(s)
    security_result = await self.security_agent.analyze(diff_text)

    # Combine and count findings
    result = AnalysisResult(
        id=analysis_id,
        agent_results=[security_result],
        total_findings=len(all_findings),
        critical_count=...,
        high_count=...,
    )
    self._results[analysis_id] = result  # Store for later retrieval
    return result
```

In Phase 2, the single sequential call becomes parallel:
```python
# Phase 2: All agents at once
results = await asyncio.gather(
    self.security_agent.analyze(diff_text),
    self.performance_agent.analyze(diff_text),
    self.testing_agent.analyze(diff_text),
)
```

### Layer 7: API Routes (routes.py)

Maps HTTP endpoints to service calls. FastAPI does most of the work:

```python
@router.post("/api/analyze", response_model=AnalysisResult)
async def analyze_pr(pr_input: PRInput):
    result = await analysis_service.analyze_diff(pr_input.diff_text)
    return result
```

That's it. FastAPI automatically:
- Parses the JSON request body into a PRInput object
- Validates all fields (types, required, constraints)
- Returns 422 with details if validation fails
- Serializes the AnalysisResult back to JSON
- Sets the right Content-Type headers

### Layer 8: FastAPI App (main.py)

The entry point that ties everything together:

```python
app = FastAPI(title="PR Review AI")
app.add_middleware(CORSMiddleware, ...)  # Allow frontend to call us
app.include_router(router)              # Register all /api/* routes
```

Run with: `uvicorn backend.api.main:app --reload`

---

## 6. The Life of a Request — Following Code Through the System

Let's trace exactly what happens when you send this request:

```bash
POST http://localhost:8000/api/analyze
{
    "diff_text": "def login(username, password):\n    query = f\"SELECT * FROM users WHERE username='{username}'\"\n    cursor.execute(query)"
}
```

### Step 1: FastAPI receives the request
FastAPI parses the JSON body and validates it against `PRInput`:
```python
class PRInput(BaseModel):
    pr_url: Optional[str] = None
    diff_text: Optional[str] = None
```
Validation passes — `diff_text` is a string. The `analyze_pr()` route handler
is called.

### Step 2: Route handler validates business logic
```python
if not pr_input.diff_text and not pr_input.pr_url:
    raise HTTPException(status_code=400, detail="Provide either 'diff_text' or 'pr_url'")
```
We have `diff_text`, so we proceed to the service.

### Step 3: AnalysisService creates an analysis
```python
analysis_id = "2b227e77"  # Random unique ID
result = AnalysisResult(id=analysis_id, status=AnalysisStatus.IN_PROGRESS)
```

### Step 4: SecurityAgent.analyze() is called
The agent calls `self.build_prompt(diff_text)`, which produces:
```
Analyze the following code for security vulnerabilities.

CHECK FOR THESE SPECIFIC ISSUES:
1. SQL Injection: String formatting in SQL queries
2. Command Injection: ...
...

CODE TO ANALYZE:
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}'"
    cursor.execute(query)

Respond with JSON in this EXACT format:
{"findings": [{"title": "...", "severity": "...", ...}]}
```

### Step 5: OllamaClient sends the prompt to Ollama
```python
POST http://localhost:11434/api/generate
{
    "model": "qwen2.5-coder:7b",
    "prompt": "Analyze the following code...",
    "system": "You are an expert code security auditor...",
    "format": "json",
    "options": {"temperature": 0.1}
}
```

### Step 6: Ollama runs inference on the RTX 5080
The model processes the prompt token by token:
1. Loads weights into 16GB VRAM (or reuses from cache)
2. Tokenizes the prompt (~200 tokens)
3. Generates response tokens (~150 tokens) at ~78 tokens/second
4. Returns the complete JSON string

### Step 7: OllamaClient parses the JSON
```python
response_text = '{"findings": [{"title": "SQL Injection", "severity": "critical", ...}]}'
parsed = json.loads(response_text)
```

### Step 8: BaseAgent.parse_response() creates Finding objects
```python
for item in parsed["findings"]:
    finding = Finding(
        agent=AgentType.SECURITY,
        severity=Severity.CRITICAL,        # Normalized from "critical"
        title="SQL Injection",
        description="User input in SQL query...",
        suggestion="Use parameterized queries",
        confidence=0.95,
    )
```

### Step 9: AgentResult is created with metadata
```python
AgentResult(
    agent=AgentType.SECURITY,
    status=AnalysisStatus.COMPLETED,
    findings=[finding1],
    execution_time=8.92,
    model_used="qwen2.5-coder:7b",
)
```

### Step 10: AnalysisService combines results
```python
result.agent_results = [security_result]
result.total_findings = 1
result.critical_count = 1
result.status = AnalysisStatus.COMPLETED
```

### Step 11: JSON response sent back
```json
{
    "id": "2b227e77",
    "status": "completed",
    "total_findings": 1,
    "critical_count": 1,
    "total_execution_time": 8.92,
    "agent_results": [
        {
            "agent": "security",
            "status": "completed",
            "model_used": "qwen2.5-coder:7b",
            "execution_time": 8.92,
            "findings": [
                {
                    "title": "SQL Injection",
                    "severity": "critical",
                    "description": "User input in SQL query...",
                    "suggestion": "Use parameterized queries",
                    "confidence": 0.95
                }
            ]
        }
    ]
}
```

Total time: ~9 seconds. The user gets a structured, actionable security report.

---

## 7. Prompt Engineering — The Secret Sauce

The difference between a useful agent and a useless one is almost entirely
in the prompts. Here's what makes a good agent prompt:

### Bad Prompt
```
Review this code.
```
Problems: vague, no format specified, no focus area, LLM will ramble.

### Good Prompt (what we actually use)
```
Analyze the following code for security vulnerabilities.

CHECK FOR THESE SPECIFIC ISSUES:
1. SQL Injection: String formatting in SQL queries
2. Command Injection: User input passed to os.system()
3. Hardcoded Secrets: API keys, passwords in source code
...

SEVERITY GUIDELINES:
- critical: Directly exploitable, leads to data breach
- high: Serious flaw, exploitable with some effort
...

CODE TO ANALYZE:
{code}

Respond with JSON in this EXACT format:
{"findings": [{"title": "...", "severity": "...", ...}]}
```

### Why This Works — 5 Principles

1. **Specific categories**: "Check for SQL injection, XSS, ..." reduces
   hallucination. The LLM knows exactly what to look for instead of guessing.

2. **Severity guidelines**: Without these, the LLM rates everything as
   "high" or rates nothing consistently. The guidelines create a shared
   vocabulary.

3. **Output format**: "Respond with JSON in this EXACT format" with an
   example. Without this, the LLM might return markdown, bullet points,
   prose, or anything else.

4. **Negative instructions**: "Only report REAL vulnerabilities. Do NOT
   hallucinate issues." LLMs tend to people-please — they'll invent problems
   to seem helpful. Telling them not to reduces false positives.

5. **Role definition** (system prompt): "You are an expert code security
   auditor" primes the model to think like a security expert, not a
   general assistant.

### Temperature: Why 0.1?

Temperature controls randomness:
- **0.0**: Completely deterministic (same input = same output every time)
- **0.1**: Almost deterministic, tiny variation (what we use)
- **0.7**: Creative, varied responses (good for writing, bad for analysis)
- **1.0**: Maximum randomness (chaotic)

For code analysis, we want consistency. If the same code has a SQL injection
today, it should find it tomorrow too. That's why we use 0.1.

---

## 8. Design Patterns Used (and Why)

### Pattern 1: Template Method (BaseAgent)

```
BaseAgent (abstract)
    ├── analyze()           ← defined here (the "template")
    │   ├── build_prompt()  ← abstract, filled by subclass
    │   ├── generate_json() ← defined here
    │   ├── parse_response()← defined here (overridable)
    │   └── error handling  ← defined here
    │
    ├── SecurityAgent       ← fills in build_prompt() + system_prompt
    ├── PerformanceAgent    ← fills in build_prompt() + system_prompt
    └── TestingAgent        ← fills in build_prompt() + system_prompt
```

**Why?** Every agent follows the same workflow (build prompt → call LLM →
parse response → handle errors). Only the prompt content differs. Without
this pattern, you'd copy-paste 80 lines of pipeline code into every agent.

### Pattern 2: Dependency Injection (OllamaClient)

```python
class SecurityAgent(BaseAgent):
    def __init__(self, ollama_client=None):
        self.client = ollama_client or OllamaClient()
```

**Why?** In production, you pass a real OllamaClient. In tests, you pass a
MockOllamaClient. The agent doesn't know or care which one it gets. This
makes testing possible without a running LLM.

```python
# Production
agent = SecurityAgent(ollama_client=OllamaClient())

# Tests
agent = SecurityAgent(ollama_client=MockOllamaClient(mock_response={...}))
```

### Pattern 3: Separation of Concerns (3-Layer Architecture)

```
API Layer (routes.py)        → "How do I receive/send HTTP?"
Service Layer (analysis_service.py) → "What agents do I run and how?"
Domain Layer (agents/*.py)   → "How do I analyze code?"
```

**Why?** Each layer changes for different reasons:
- API changes when you add a new endpoint
- Service changes when you add a new agent
- Agents change when you improve prompts

If these were all in one file, every change risks breaking everything.

### Pattern 4: Graceful Degradation

```python
# In parse_response(): skip bad findings, keep good ones
for item in raw_findings:
    try:
        finding = Finding(...)
        findings.append(finding)
    except Exception:
        continue  # Skip this one, keep going

# In analyze(): never crash
try:
    ... do analysis ...
except Exception as e:
    return AgentResult(status=FAILED, error=str(e))
```

**Why?** LLMs are unpredictable. A single malformed response shouldn't crash
the entire system. The agent degrades gracefully — returns partial results
or a structured error instead of an exception.

---

## 9. The Hard Problem — LLMs Are Unpredictable

The biggest challenge in agentic AI is that LLMs are not regular functions.
`f(x)` doesn't always return the same `y`. Here's what can go wrong and
how we handle it:

### Problem 1: Invalid JSON

Even with `format: "json"`, models sometimes produce:
```json
{"findings": [{"title": "SQL Injection", "severity": "critical",}]}
                                                               ^ trailing comma = invalid JSON
```

**Our solution**: `generate_json()` catches `json.JSONDecodeError` and raises
a clear error. The agent's `analyze()` method catches this and returns FAILED.

### Problem 2: Wrong Key Names

You ask for `"findings"` but the LLM returns `"issues"` or `"vulnerabilities"`:

**Our solution**: `parse_response()` checks multiple key names:
```python
raw_findings = data.get("findings", data.get("issues", []))
```

### Problem 3: Inconsistent Severity

You ask for `"high"` but get `"HIGH"`, `"High"`, or `"high!"`:

**Our solution**: Normalize before creating the enum:
```python
severity_str = item.get("severity", "medium").lower().strip()
```

### Problem 4: Hallucinated Findings

The LLM invents a vulnerability that doesn't exist in the code.

**Our solution** (partial):
- Low temperature (0.1) reduces creativity
- "Only report REAL vulnerabilities" in the prompt
- Confidence scores let users filter low-confidence findings
- (Future: cross-validate with multiple agents)

### Problem 5: Model Takes Too Long

First model load can take 30+ seconds. Or the model might hang.

**Our solution**: 120-second timeout on the HTTP client:
```python
self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
```

---

## 10. Multi-Agent Orchestration (What Comes Next)

Right now we have 1 agent. In Phase 2, we'll have 5 agents running in
parallel. Here's how that changes the architecture:

### Single Agent (Phase 1 — current)
```
Code → SecurityAgent → Results
Time: ~9 seconds
```

### Multi-Agent Sequential (naive approach)
```
Code → SecurityAgent → PerformanceAgent → TestingAgent → DocAgent → StandardsAgent → Results
Time: ~45 seconds (9 * 5)
```

### Multi-Agent Parallel (Phase 2 — with asyncio)
```
         ┌→ SecurityAgent ────→┐
         ├→ PerformanceAgent ──→┤
Code ────┼→ TestingAgent ──────→┼── Aggregate → Results
         ├→ DocAgent ──────────→┤
         └→ StandardsAgent ────→┘
Time: ~10 seconds (all run simultaneously)
```

```python
# The magic of asyncio.gather()
results = await asyncio.gather(
    security_agent.analyze(diff),     # starts immediately
    performance_agent.analyze(diff),  # starts immediately
    testing_agent.analyze(diff),      # starts immediately
    documentation_agent.analyze(diff),# starts immediately
    standards_agent.analyze(diff),    # starts immediately
)
# All 5 run at the same time. Total time = slowest agent, not sum of all.
```

### With LangGraph (Phase 2 — advanced orchestration)
```
                    ┌→ SecurityAgent ─────→┐
Code → Triage ──────┤                      ├→ Aggregator → Results
  (decides which    ├→ PerformanceAgent ──→┤
   agents to run)   └→ TestingAgent ──────→┘
                    (skips Doc + Standards
                     for small changes)
```

LangGraph adds:
- **Conditional routing**: Don't run all agents on every PR. A 2-line README
  change doesn't need a performance agent.
- **State management**: Agents can share context (e.g., SecurityAgent found
  user input handling — tell PerformanceAgent to check those same functions)
- **Retry logic**: If an agent fails, retry with a different model
- **Visualization**: See the workflow as a graph

---

## 11. Key Takeaways

1. **An agent = LLM + structured I/O + error handling + metadata.**
   It turns an unpredictable AI into a reliable software component.

2. **Prompt engineering is the most important skill.**
   The same model can be useless or excellent depending on the prompt.

3. **Always use structured output (JSON mode).**
   Never parse free-form LLM text if you can avoid it.

4. **Design for failure.**
   LLMs will return garbage sometimes. Your system must handle it gracefully.

5. **Use the smallest model that works.**
   3B for simple tasks, 7B for reasoning, 16B only when needed. Faster is
   better — your users don't want to wait 60 seconds.

6. **Separate concerns aggressively.**
   API, Service, Agent, LLM Client — each layer has one job. This makes
   the system testable, maintainable, and extensible.

7. **Test with mocks, verify with integration tests.**
   Mock tests are fast and deterministic (for CI/CD). Integration tests
   are slow but verify the real pipeline works.

8. **Local LLMs are viable for production.**
   With an RTX 5080, our 7B model runs at 78 tokens/second. That's fast
   enough for real-time analysis.

---

## 12. Glossary

**Agent**: A self-contained AI component with a defined role, structured
input/output, and error handling. Not just an LLM call.

**LLM (Large Language Model)**: A neural network trained on text that can
generate human-like responses. Examples: GPT-4, Llama, Qwen.

**Ollama**: Software that runs LLMs locally on your machine. Handles model
downloading, GPU management, and inference.

**Inference**: The process of running a trained model on new input to
generate output. This is what happens when the LLM "thinks."

**VRAM**: Video RAM on your GPU. Models must fit in VRAM to run on GPU.
A 7B model needs ~5GB VRAM. Your RTX 5080 has 16GB.

**Token**: The basic unit LLMs work with. Roughly 1 token = 0.75 words.
"SQL injection vulnerability" ≈ 3 tokens.

**Temperature**: Controls randomness in LLM output. 0.0 = deterministic,
1.0 = maximum randomness. Use low temperature for factual tasks.

**System Prompt**: Instructions given to the LLM before the user's message.
Defines the AI's role, personality, and constraints.

**Prompt Engineering**: The art of writing prompts that get reliable, useful
responses from LLMs. The most impactful skill in AI development.

**Pydantic**: Python library for data validation using type hints. Ensures
data flowing through the system has the correct shape and types.

**FastAPI**: Modern Python web framework. Auto-generates API documentation,
validates requests/responses, and supports async/await.

**async/await**: Python pattern for non-blocking code. Lets you run multiple
operations concurrently (like 5 agents analyzing code simultaneously).

**CORS (Cross-Origin Resource Sharing)**: Browser security feature that
blocks requests between different domains. We configure CORS to allow our
React frontend (port 5173) to call our API (port 8000).

**Dependency Injection**: Passing dependencies (like OllamaClient) into a
class from outside instead of creating them internally. Makes testing easy.

**Template Method Pattern**: Define a workflow in a base class, let subclasses
fill in specific steps. Our BaseAgent.analyze() is the template; each agent
provides its own build_prompt().

**LangGraph**: Framework for building stateful, multi-step AI workflows.
Lets you define agents as nodes and execution flow as edges in a graph.

---

*This document reflects the system as built through Phase 1.3. It will be
updated as we add more agents (Phase 2), GitHub integration (Phase 3), and
the database layer (Phase 4).*
