from pydantic_ai import Agent

from server.gateway import evaluator_model, executor_model
from server.models import CorrectionEntry, RunChecklist, Verdict

checklist_agent = Agent(
    evaluator_model(),
    output_type=RunChecklist,
    system_prompt=(
        "You are a rigorous evaluator preparing to judge another AI agent's work. "
        "Given a task, produce a short checklist of concrete, checkable pass/fail "
        "criteria - not vague quality judgments like 'looks good' or 'well styled'. "
        "If the task specifies exact values (class names, colors, spacing, sizes, "
        "states), turn each one into its own checklist item naming the exact "
        "value expected and which element it applies to - e.g. 'disabled state "
        "applies 60% opacity to the entire card, not just the toggle' rather than "
        "'disabled state is styled correctly'. Also include a reasonable time "
        "limit in minutes and a total token budget for a small model to complete "
        "the task. Keep the checklist to 3-6 items."
    ),
)

executor_agent = Agent(
    executor_model(),
    system_prompt=(
        "You complete the given task directly. Respond with only the requested "
        "artifact (e.g. code) - no explanation, no preamble, no markdown commentary "
        "outside of a single fenced code block when code is requested."
    ),
)

evaluator_agent = Agent(
    evaluator_model(),
    output_type=Verdict,
    system_prompt=(
        "You are a strict, rigorous evaluator. Given a task, a checklist of "
        "pass/fail criteria, and an attempt at the task, judge whether the "
        "attempt satisfies every checklist item. For styling criteria, check "
        "the actual code for the literal class names/values named in the "
        "checklist and which element they're applied to - do not pass an "
        "item just because *some* styling is present if it's the wrong "
        "value or on the wrong element. Be specific in `reasoning` about "
        "what passed or failed. List every failed criterion verbatim in "
        "`failed_criteria`. Do not pass an attempt that fails any criterion."
    ),
)


def build_evaluator_prompt(
    query: str, checklist: RunChecklist, output: str, past_corrections: list[CorrectionEntry]
) -> str:
    parts = [
        f"Task: {query}",
        "Checklist:\n" + "\n".join(f"- {c}" for c in checklist.criteria),
        f"Attempt:\n{output}",
    ]
    if past_corrections:
        parts.append(
            "Note: a human previously overrode this evaluator's judgment on "
            "similar tasks because it missed real problems. Be extra rigorous "
            "about these past misses:\n"
            + "\n".join(f"- {c.reason}" for c in past_corrections)
        )
    return "\n\n".join(parts)


def build_executor_prompt(
    query: str,
    previous_output: str | None,
    critique: str | None,
    failed_criteria: list[str] | None = None,
) -> str:
    if previous_output is None:
        return query
    failed_list = "\n".join(f"- {c}" for c in failed_criteria) if failed_criteria else None
    return (
        f"{query}\n\n"
        f"Your previous attempt:\n{previous_output}\n\n"
        f"That attempt failed review for this reason: {critique}\n"
        + (f"Specifically, these checklist items failed:\n{failed_list}\n" if failed_list else "")
        + "Produce a corrected attempt that fixes exactly these issues without "
        "regressing anything that already passed."
    )
