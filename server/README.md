# agent-lenses backend

FastAPI service running the executor → evaluator correction loop.
Everything here is Python (`pydantic_ai`); the frontend is a separate app that
talks to this over HTTP.

**No per-task checklist.** The Evaluator doesn't generate a fresh rubric for
each run - it judges directly against the task's stated requirements, guided
by (1) a fixed, general system prompt (applies to any task/user/app, not one
checklist) and (2) an accumulating log of human corrections learned across
*all* runs over time (see `/corrections`). This is deliberate: real criteria
should generalize across different users building different things, not be
reinvented per task by an LLM.

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
data: {"run_id": "...", "status": "running", "iterations": [...], "thoughts": [...], ...}

data: {"run_id": "...", "status": "evaluating", ...}

data: {"run_id": "...", "status": "passed", "final_output": "```jsx\n...\n```", ...}
```

The stream ends (connection closes) once `status` reaches a terminal value:
`"passed"`, `"failed"`, `"max_iterations"`, or `"needs_review"`. If you
connect after the run already finished, you'll get exactly one event (the
final snapshot) and then the stream closes immediately.

### `POST /runs/{run_id}/mark-failure`
Human override for a false negative (the evaluator wrongly passed something,
or you disagree with a `needs_review` verdict). Persists the reason as future
Evaluator context and starts a **new** run for the same query.

```json
// request
{ "reason": "The badge color is actually blue, not green - evaluator missed it" }

// response
{ "new_run_id": "..." }
```

Subscribe to `/runs/{new_run_id}/stream` to watch the re-run. The `reason`
is also persisted into the evaluator's standing context (see `/corrections`)
so it informs every future run, for every task, not just this one.

### `POST /runs/{run_id}/approve`
The other resolution for a `"needs_review"` run - human confirms the output
is actually fine despite the evaluator's uncertainty. Flips `status` to
`"passed"` in place (no new run). `400` if the run isn't currently
`"needs_review"`.

```json
// response: the updated RunState, status now "passed"
```

### `GET /corrections`
The evaluator's accumulated standing context - every human correction ever
recorded via `/mark-failure`, across all runs and tasks, newest first
(`?limit=` to control how many, default 20). This is what makes the
evaluator *general* rather than task-specific: it grows over time as users
correct it, and every future run - for any task - gets the accumulated list.

```json
// response
[{ "run_id": "...", "query": "...", "output": "...", "reason": "...", "at": "..." }]
```

### On `"needs_review"` - the evaluator can ask for human input directly
The evaluator is instructed to flag genuine ambiguity (`confident: false`
on its verdict, with a `question_for_human`) rather than forcing a pass/fail
it doesn't actually believe - e.g. a subjective styling call reasonable
people could disagree on. When that happens, the loop stops immediately
(no more retries) with `status: "needs_review"` and the question surfaces as
the last `thought`. This is a **prompt for a human**, not a bug report -
resolve it with `/approve` (agree, keep the output) or `/mark-failure`
(disagree, rerun with your correction as context). This is distinct from
`/mark-failure` used after a `"passed"` result - that's catching a false
negative the evaluator was (wrongly) confident about; `needs_review` is the
evaluator proactively saying it *isn't* confident.

## `RunState` shape

```ts
type RunState = {
  run_id: string;
  query: string;
  status: "running" | "evaluating" | "passed" | "failed" | "max_iterations" | "needs_review";
  iterations: {
    index: number;
    prompt: string;
    output: string;
    verdict: {
      passed: boolean;
      reasoning: string;
      issues: string[];                 // specific problems found in THIS attempt - not a checklist
      confident: boolean;               // false -> this triggered "needs_review"
      question_for_human: string | null; // set only when confident is false
    } | null;
  }[];
  thoughts: { at: string /* ISO datetime */; message: string }[];
  final_output: string | null;  // set on "passed", "max_iterations", or "needs_review"
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
- **`needs_review` means the evaluator is asking you something, not that
  anything broke.** Show `question_for_human` from the last iteration's
  verdict (or the last `thought`, same text) as an actual prompt with two
  actions: approve (`/approve`) or reject with a reason (`/mark-failure`).
  This should be rare - the evaluator is told to only use it for genuine
  ambiguity, not routine failures.
- Runs are **in-memory only** - a server restart loses all run state. Fine
  for a hackathon demo, not for anything real.
