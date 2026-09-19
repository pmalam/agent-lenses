# agent-lenses
Watch AI agents stay on track.

## Services

- `apps/web/` — Next.js frontend (see [apps/web/README.md](apps/web/README.md))
- repo root — Python Modal/Pydantic AI Gateway demo (below)

## Demo: inference on Modal, piped through the Pydantic AI Gateway

Runs an open-weight model on your own Modal GPU, routes the request through the
Pydantic AI Gateway, and traces it in Logfire.

```
script.py  ──>  Pydantic AI Gateway  ──>  Modal endpoint (vLLM)  ──>  your model
                        │
                        └──>  Logfire trace
```

`<MODEL>` = the Hugging Face repo ID of whichever model you pick (e.g.
`google/gemma-4-31B-it`). Same string goes in the `modal endpoint create` command
and in `script.py`.

### Prereqs (already installed in this environment)
- `uv` — installed via Homebrew
- `modal` CLI — installed via Homebrew

You still need your own **Modal account (with credits)** and a **Logfire account
with a Pydantic AI Gateway** — these are account/billing steps only you can do.

### Setup

1. **Authenticate Modal** (opens a browser):
   ```bash
   modal setup
   ```

2. **Create a proxy token** — the gateway uses this to call Modal on your behalf:
   ```bash
   modal workspace proxy-tokens create
   ```
   Copy the token ID (`wk-…`) and secret (`ws-…`), shown once. If it's
   environment-scoped:
   ```bash
   modal workspace proxy-tokens allow <token-id> main
   ```

3. **Create the endpoint** (pick a model from the Modal Library, start with a
   dense single-GPU model — MoE models can sit unscheduled if capacity is tight):
   ```bash
   modal endpoint create --name gateway --model <MODEL>
   ```
   Check readiness: `modal endpoint list` (provisioning takes several minutes).

4. **Copy the endpoint URL** from the endpoint's dashboard page at
   [modal.com/endpoints](https://modal.com/endpoints) — it's only there, not in
   the CLI output. Looks like:
   `https://<workspace>--ep-<name>-server.<region>.modal.direct`

5. **Add Modal as a BYOK provider in the Logfire gateway** — Gateway → Add
   provider:
   | Field | Value |
   |---|---|
   | Provider name | `modal` |
   | Base URL | `<endpoint-url from step 4>/v1` (replace the prefilled `api.modal.com/v1` — that's the gRPC control plane, not inference) |
   | Proxy token ID | `wk-…` from step 2 |
   | Proxy token secret | `ws-…` from step 2 |

   Credentials live in the gateway, not in this repo — that's what BYOK means
   here, and it's what lets the gateway meter/trace every call while Modal
   bills your account.

6. **Fill in `.env`** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   - `PYDANTIC_AI_GATEWAY_BASE_URL` — the gateway **root**, no route suffix
     (script.py appends it via `route='modal'`)
   - `PYDANTIC_AI_GATEWAY_API_KEY` — your Logfire gateway key
   - `LOGFIRE_TOKEN` — a project **write token** (Logfire → project settings →
     Write tokens)

7. **Set the model** in `script.py` (`MODEL = "<MODEL>"`) to the same repo ID
   deployed in step 3, then run:
   ```bash
   uv run --env-file .env script.py
   ```
   First run prints the Logfire trace URL and an email-drafting response — this
   is the *before* baseline, no optimization installed yet.

### The hackathon challenge

Everything past this point happens in the **gateway**, not in `script.py` —
that file does not change again. Enable the flags on your Logfire project URL:
`#enableFlags=gateway_optimizations,gateway_guardrails_beta`

- **Optimizations** (Gateway → Optimizations) inject directives that shape
  model behavior on every call through a route. Start with the built-in
  *Caveman mode (terse)* rule targeted at the `modal` route to prove the wiring
  works, then swap in something that solves a real problem (cut tokens, force
  an output shape, change tool-calling behavior).
- **Guardrails** (Gateway → Guardrails) detect and redact/block sensitive data
  *before* it reaches the model — e.g. a custom regex protection for UK phone
  numbers, applied to the `modal` endpoint with action `Redact`. Prove it with
  an echo-back prompt: a working redaction returns `[REDACTED]`, not the digits.

To submit: the rule's injected instruction, before/after outputs on the same
prompt, Logfire trace links for both runs, and (bonus) the guardrail + an echo
test showing the model never saw the raw value.

### Troubleshooting

| Symptom | Cause |
|---|---|
| `503 modal_no_live_containers` | Endpoint scaled to zero (~15 min idle). Retry, cold start ~2 min. |
| `'str' object has no attribute 'output'` / expected JSON data | Gateway base URL still points at `api.modal.com`. |
| `404 unknown inference model` | Wrong host — dedicated endpoints have their own URL (step 4), not the shared endpoint host. |
| `UnexpectedModelBehavior: 1 validation error` | The `metadata` widening block is missing from `script.py`. |
| `UserError: Unknown upstream provider` | First arg to `gateway_provider` must be an API flavor (`openai-chat`), not a provider name. |
| `Route not found` | `route=` name doesn't match what you named the provider in step 5. |
| Protection fires in the trace but the model still saw the value | Action is `Observe`/`Flag response` — switch to `Redact`/`Block`. |
| Trace shows `[Scrubbed due to 'session']` | Logfire's default scrubbing caught a word like "session"/"token"/"secret" in the output. Pass a scrubbing callback to `logfire.configure()` if you need it verbatim. |
