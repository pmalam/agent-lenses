import asyncio
import json
from pathlib import Path
from typing import TypeVar

import logfire
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from server.agents import (
    build_evaluator_prompt,
    build_executor_prompt,
    checklist_agent,
    evaluator_agent,
    executor_agent,
)
from server.bus import event_bus
from server.models import CorrectionEntry, Iteration, RunState, ThoughtEvent
from server.store import correction_log, run_store

MAX_ITERATIONS = 4
MODAL_COLD_START_RETRIES = 5
MODAL_COLD_START_DELAY_SECONDS = 20

T = TypeVar("T")


async def _run_with_retry(agent: Agent, prompt: str, *, state: RunState, label: str):
    """Modal endpoints scale to zero after ~5-15 min idle and return a 503
    (`modal_no_live_containers`) while cold-starting - this has been the
    single most common failure mode against these endpoints all along.
    Retry through it with visible status instead of failing the run."""
    last_error: Exception | None = None
    for attempt in range(1, MODAL_COLD_START_RETRIES + 1):
        try:
            return await agent.run(prompt)
        except ModelHTTPError as e:
            last_error = e
            if e.status_code != 503:
                raise
            await _emit(
                state,
                f"{label}: model endpoint is cold-starting (attempt {attempt}/"
                f"{MODAL_COLD_START_RETRIES}), retrying...",
            )
            await asyncio.sleep(MODAL_COLD_START_DELAY_SECONDS)
    assert last_error is not None
    raise last_error

_CREDENTIALS_PATH = Path(__file__).parent.parent / ".logfire" / "logfire_credentials.json"


def _project_url() -> str | None:
    try:
        data = json.loads(_CREDENTIALS_PATH.read_text())
        return data.get("project_url")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


async def _emit(state: RunState, message: str) -> None:
    state.thoughts.append(ThoughtEvent(message=message))
    run_store.update(state)
    await event_bus.publish(state.run_id, {"type": "state", "state": state.model_dump(mode="json")})


async def run_task(run_id: str, query: str) -> None:
    state = RunState(run_id=run_id, query=query)
    run_store.create(state)

    try:
        with logfire.span("agent-lenses run", run_id=run_id, query=query):
            await _emit(state, "Generating evaluation checklist...")
            checklist_result = await _run_with_retry(
                checklist_agent, query, state=state, label="Checklist"
            )
            state.checklist = checklist_result.output
            state.status = "running"
            await _emit(
                state,
                f"Checklist ready: {len(state.checklist.criteria)} criteria, "
                f"{state.checklist.time_limit_minutes}min budget.",
            )

            previous_output: str | None = None
            critique: str | None = None
            failed_criteria: list[str] | None = None
            past_corrections = correction_log.recent()

            for i in range(MAX_ITERATIONS):
                prompt = build_executor_prompt(query, previous_output, critique, failed_criteria)
                await _emit(state, f"Executor attempt {i + 1}: running...")
                exec_result = await _run_with_retry(
                    executor_agent, prompt, state=state, label=f"Executor attempt {i + 1}"
                )
                output = exec_result.output

                state.status = "evaluating"
                await _emit(state, f"Executor attempt {i + 1}: evaluating output...")
                eval_prompt = build_evaluator_prompt(
                    query, state.checklist, output, past_corrections
                )
                eval_result = await _run_with_retry(
                    evaluator_agent, eval_prompt, state=state, label=f"Evaluator (attempt {i + 1})"
                )
                verdict = eval_result.output

                state.iterations.append(
                    Iteration(index=i, prompt=prompt, output=output, verdict=verdict)
                )

                if verdict.passed:
                    state.status = "passed"
                    state.final_output = output
                    await _emit(state, f"Attempt {i + 1} passed: {verdict.reasoning}")
                    break

                critique = verdict.reasoning
                failed_criteria = verdict.failed_criteria
                previous_output = output
                await _emit(
                    state,
                    f"Attempt {i + 1} failed ({', '.join(verdict.failed_criteria) or 'unspecified'}): "
                    f"{verdict.reasoning}",
                )
            else:
                state.status = "max_iterations"
                state.final_output = previous_output
                await _emit(state, f"Gave up after {MAX_ITERATIONS} attempts without passing.")

            state.trace_url = _project_url()
    except Exception as e:
        state.status = "failed"
        await _emit(state, f"Run failed: {e}")
        logfire.exception("agent-lenses run failed", run_id=run_id)
    finally:
        run_store.update(state)
        await event_bus.publish(
            state.run_id, {"type": "state", "state": state.model_dump(mode="json")}
        )
        event_bus.close(state.run_id)


async def mark_false_negative(run_id: str, reason: str, new_run_id: str) -> None:
    """Human override: the evaluator wrongly passed a run. Persist the
    correction as future Evaluator context, then start a fresh run (under
    the caller-supplied new_run_id, so the caller can subscribe to it before
    this coroutine finishes) for the same query."""
    state = run_store.get(run_id)
    if state is None:
        raise ValueError(f"unknown run_id: {run_id}")

    correction_log.add(
        CorrectionEntry(
            run_id=run_id,
            query=state.query,
            output=state.final_output or "",
            reason=reason,
        )
    )

    await run_task(new_run_id, state.query)
