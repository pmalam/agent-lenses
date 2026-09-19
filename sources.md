Here is a detailed document covering all the **APIs, Frameworks, and Tools** used in the `agent-lenses` project:

---

# System Architecture & Tech Stack Documentation


## 1. Frontend Frameworks & Libraries (`apps/web/`)

| Technology / Library | Version | Purpose & Usage |
| :--- | :--- | :--- |
| **Next.js** | `16.3.5` | React framework using the App Router for server rendering, routing, and UI presentation. |
| **React** & **React DOM** | `19.2.8` | Component library for building interactive user interfaces. |
| **Tailwind CSS** | `^4.0` | Utility-first CSS framework (with `@tailwindcss/postcss`) for styling UI elements. |
| **Vercel AI SDK (`ai`)** | `^7.0.107` | Framework for integrating AI models into JavaScript/TypeScript applications. |
| **`@ai-sdk/openai`** & **`openai`** | `^4.0.71` / `^7.19.0` | OpenAI provider compatibility layer for interacting with OpenAI-compliant gateway endpoints. |
| **`@pydantic/logfire-node`** | `^0.18.25` | Node.js integration for Logfire tracing and observability. |
| **Zod** | `^4.6.5` | TypeScript-first schema validation library. |
| **TypeScript** | `^5.0` | Static type checker for modern JavaScript development. |

---

## 2. Backend Frameworks & Libraries (`server/`)

| Technology / Library | Version | Purpose & Usage |
| :--- | :--- | :--- |
| **Python** | `>= 3.11` | Programming language powering the backend agents and server. |
| **FastAPI** | `>= 0.115.0` | Modern Python web framework used for serving REST APIs and Server-Sent Events (SSE). |
| **Uvicorn** | `>= 0.30.0` | ASGI server implementation used to run the FastAPI backend application. |
| **Pydantic AI (`pydantic-ai`)**| `>= 2.45.0` | Agentic AI framework used to construct structured prompt loops, agent roles, and typed outputs. |
| **Pydantic Evals (`pydantic-evals`)**| `>= 2.4.0` | Evaluation suite for assessing LLM outputs against criteria. |
| **Logfire (`logfire`)** | `>= 5.1.0` | Observability and instrumentation framework for logging, tracing agent runs, and monitoring latency. |

---

## 3. External Services & Cloud Tools

| Tool / Platform | Purpose |
| :--- | :--- |
| **Modal Cloud** | Serverless GPU execution platform hosting open-weights model inference endpoints (e.g. Hugging Face models like Gemma). |
| **Pydantic AI Gateway** | Proxy and routing layer managing Bring-Your-Own-Key (BYOK) providers, model endpoints, and rate limits. |
| **Logfire Cloud** | Observability workspace displaying trace timelines, span trees, and agent execution graphs. |

---

## 4. Development & Quality Assurance Tools

| Tool | Purpose |
| :--- | :--- |
| **`uv`** | Fast Python package installer and virtual environment manager (`uv sync`, `uv run`). |
| **`npm`** | Package manager for Node.js dependencies. |
| **ESLint** | Linter enforcing JS/TS syntax rules and code consistency. |
| **Prettier** | Code formatter for consistent code formatting across `.ts`, `.tsx`, `.json`, and `.md` files. |
| **Husky** & **lint-staged** | Git pre-commit hooks enforcing formatting and linting prior to code commits. |
| **`tsx`** | TypeScript execute CLI for running node scripts directly during development. |

---

## 5. Backend API Reference (`server/main.py`)

The backend exposes HTTP endpoints for control and real-time streaming:

### Endpoints

#### 1. `POST /run`
Starts a new background agent execution loop.
- **Request Body**:
```json
{
    "query": "Create a React component for a user settings card."
  }
```

- **Response**:
```json
{
    "run_id": "e6206590-5937-46f5-9434-5444a4b863aa"
  }
```


#### 2. `GET /runs/{run_id}`
Retrieves a snapshot of the current state of a run.
- **Response**: Returns `RunState` JSON object or `404` if not found.

#### 3. `GET /runs/{run_id}/stream`
Opens a Server-Sent Events (SSE) stream delivering real-time `RunState` state updates until terminal state (`passed`, `failed`, or `max_iterations`).
- **Response Format**: `text/event-stream` delivering JSON snapshots.

#### 4. `POST /runs/{run_id}/mark-failure`
Records user feedback on a false positive evaluation and triggers a re-run incorporating the failure reason.
- **Request Body**:
```json
{
    "reason": "Evaluator marked output passed, but button padding was missing."
  }
```

- **Response**:
```json
{
    "new_run_id": "8a32b110-3321-4f11-9210-213421bb4021"
  }
```
