# agent-lenses
Watch AI agents stay on track.

## Overview
**agent-lenses** is a real-time AI agent monitoring and observability platform. It allows users to run multi-step agent loops (Checklist Creator → Executor → Evaluator) and observe thought processes, verification steps, and execution status live over Server-Sent Events (SSE) with Logfire tracing.


---

## Architecture & Services

The system connects UI task inputs, Pydantic AI agents, and real-time observability:

- **`apps/web/`** — Next.js UI application for user interaction, task input, and polling execution/evaluator progress.
- **`script.py` & Modal Cloud** — Python backend/agents (Executor and Evaluator) running via Modal and Pydantic AI Gateway, traced using Logfire.
- See [architecture.md](./architecture.md) for full details on system components, sequence flows, and loop mechanics.
- See [sources.md](./sources.md) for full details on data sources, references, and attribution.

---

## Prerequisites

- **Node.js**: `v20+` and `npm`
- **Python**: `>= 3.11`
- **Package & CLI Tools**:
  - `uv` (installed via Homebrew or official installer)
  - `modal` CLI (installed via Homebrew or `pip install modal`)
- **External Accounts**:
  - Modal account (with active GPU credits)
  - Logfire account with Pydantic AI Gateway enabled

---

## Quick Setup Instructions

### 1. Web Frontend (`apps/web`)

1. **Navigate to the web app directory**:
   ```bash
   cd apps/web
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### 2. Python Agent Demo (Modal & Pydantic AI Gateway)

1. **Authenticate Modal** (opens browser authentication):
   ```bash
   modal setup
   ```

2. **Create a Proxy Token**:
   ```bash
   modal workspace proxy-tokens create
   ```
   Save the displayed Token ID (`wk-…`) and Secret (`ws-…`). If environment-scoped:
   ```bash
   modal workspace proxy-tokens allow <token-id> main
   ```

3. **Deploy the Inference Endpoint**:
   Select a model repo ID from Hugging Face (e.g., `google/gemma-3-1b-it` or `google/gemma-4-31B-it`):
   ```bash
   modal endpoint create --name gateway --model <MODEL>
   ```
   Verify status with `modal endpoint list` (provisioning takes a few minutes).

4. **Copy Endpoint URL**:
   Retrieve the dedicated URL from your [Modal Endpoints Dashboard](https://modal.com/endpoints):
   `https://<workspace>--ep-<name>-server.<region>.modal.direct`

5. **Configure BYOK Provider in Logfire Gateway**:
   In Logfire Gateway → Add Provider:

   | Field | Value |
   |---|---|
   | Provider name | `agentlenses-provider` (must match `route` in `script.py`) |
   | Base URL | `<endpoint-url-from-step-4>/v1` |
   | Proxy token ID | `wk-…` (from step 2) |
   | Proxy token secret | `ws-…` (from step 2) |

6. **Environment Configuration**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Set the following variables:
   - `PYDANTIC_AI_GATEWAY_BASE_URL` — Gateway root URL without route suffix.
   - `PYDANTIC_AI_GATEWAY_API_KEY` — Your Logfire Gateway key.
   - `LOGFIRE_TOKEN` — Logfire project write token (Logfire → Settings → Write tokens).

7. **Run the Script**:
   Ensure `MODEL` inside `script.py` matches the model deployed in Step 3, then execute:
   ```bash
   uv run --env-file .env script.py
   ```
   First run prints the Logfire trace URL and agent output.

---

## Development Commands

### Web App Commands