# agent-lenses backend

FastAPI service running the checklist → executor → evaluator correction loop.
Everything here is Python (`pydantic_ai`); the frontend is a separate app that
talks to this over HTTP.

## Running it

```bash
# from repo root
uv sync
uv run --env-file .env uvicorn server.main:app --port 8000 --reload
```

Needs `.env` at the repo root with `PYDANTIC_AI_GATEWAY_BASE_URL`,
`PYDANTIC_AI_GATEWAY_API_KEY`, and a `.logfire/logfire_credentials.json`
(from `logfire auth` / `init use`) for tracing. CORS is wide open
(`allow_origins=["*"]`) for local dev — tighten before deploying anywhere
real.

Interactive Swagger UI for the plain JSON endpoints: `http://localhost:8000/docs`.
(The SSE stream endpoint won't render meaningfully there — see below.)

## Endpoints

### `POST /run`
Starts a run in the background, returns immediately.

```json
// request
{ "query": "Edit this FeatureCard component to..." }

// response
{ "run_id": "e6206590-5937-46f5-9434-5444a4b863aa" }
```

### `GET /runs/{run_id}`
One-shot snapshot of current state. Returns a `RunState` (see below), or
`404` if the run_id is unknown.

### `GET /runs/{run_id}/stream`
Server-Sent Events. Each event is a full `RunState` snapshot (not a diff) —
just replace your local copy on every message:

```
data: {"run_id": "...", "status": "running", "checklist": {...}, "iterations": [...], "thoughts": [...], ...}

data: {"run_id": "...", "status": "evaluating", ...}

data: {"run_id": "...", "status": "passed", "final_output": "```jsx\n...\n```", ...}
```

The stream ends (connection closes) once `status` reaches a terminal value:
`"passed"`, `"failed"`, or `"max_iterations"`. If you connect after the run
already finished, you'll get exactly one event (the final snapshot) and then
the stream closes immediately.

### `POST /runs/{run_id}/mark-failure`
Human override for a false negative (the evaluator wrongly passed something).
Persists the reason as future Evaluator context and starts a **new** run for
the same query.

```json
// request
{ "reason": "The badge color is actually blue, not green - evaluator missed it" }

// response
{ "new_run_id": "..." }
```

Subscribe to `/runs/{new_run_id}/stream` to watch the re-run.

## `RunState` shape

```ts
type RunState = {
  run_id: string;
  query: string;
  status: "checklisting" | "running" | "evaluating" | "passed" | "failed" | "max_iterations";
  checklist: {
    criteria: string[];
    time_limit_minutes: number;
    token_budget: number;
  } | null;
  iterations: {
    index: number;
    prompt: string;
    output: string;
    verdict: {
      passed: boolean;
      reasoning: string;
      failed_criteria: string[];
    } | null;
  }[];
  thoughts: { at: string /* ISO datetime */; message: string }[];
  final_output: string | null;  // set only on "passed" or "max_iterations"
  trace_url: string | null;     // Logfire project URL, set at the end of a run
  created_at: string;
  updated_at: string;
};
```

`final_output` (when set) is the executor's raw response text - typically a
fenced code block (```jsx ... ```) since that's what the executor is
prompted to produce. Strip the fence before handing it to Sandpack/whatever
renders it.

## Notes on behavior worth knowing before building against this

- **Modal cold starts are the most common failure mode you'll see.** Both
  models are Modal endpoints that scale to zero after idle. The backend
  retries automatically (up to 5x, 20s apart) and emits a thought each retry
  (`"...model endpoint is cold-starting (attempt N/5), retrying..."`) so the
  frontend can surface that rather than looking stuck. If it exhausts
  retries, `status` becomes `"failed"` with the error in the last `thought`.
- **`max_iterations` is a legitimate terminal state, not a bug** - it means
  the loop capped out (currently 4 attempts) without the evaluator passing
  the output. `final_output` is still set (the last attempt), so you can
  still show it, just clearly marked as not-passed.
- Runs are **in-memory only** - a server restart loses all run state. Fine
  for a hackathon demo, not for anything real.
