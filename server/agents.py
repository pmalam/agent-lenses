from pydantic_ai import Agent

from server.gateway import evaluator_model, executor_model
from server.models import CorrectionEntry, Verdict

executor_agent = Agent(
    executor_model(),
    system_prompt=(
        "You complete the given task directly. Respond with only the requested "
        "artifact (e.g. code) - no explanation, no preamble, no markdown commentary "
        "outside of a single fenced code block when code is requested."
    ),
)

# This is the general, standing evaluator prompt - not regenerated per task. It's
# deliberately generic (applies across any user's task/app, not one checklist),
# and gets supplemented per-run only with accumulated corrections (see
# build_evaluator_prompt) - real, specific criteria come from what's actually
# been learned over time, not from an LLM inventing a fresh rubric each run.
evaluator_agent = Agent(
    evaluator_model(),
    output_type=Verdict,
    system_prompt=(
        "You are a strict, rigorous code reviewer. Given a task description "
        "(the requirements) and an attempt at that task, judge whether the "
        "attempt genuinely fulfills every requirement actually stated - not "
        "just plausible-looking code. General things worth checking on every "
        "review, regardless of what the specific task is:\n"
        "- The code is syntactically valid and complete (no missing closing "
        "tags/braces, no truncated statements) - this is a hard requirement "
        "before anything else matters.\n"
        "- Every concrete detail named in the requirements (exact values, "
        "colors, spacing, states, behavior) is implemented literally, on the "
        "right element - not just 'something similar' or 'the general idea'.\n"
        "- Nothing required is silently dropped, and nothing broken is "
        "introduced in something that already worked.\n\n"
        "List every specific problem you find in `issues` (plain descriptions, "
        "not references to a checklist - there is no checklist, only the "
        "stated requirements). `passed` must be consistent with `issues`: "
        "zero issues means passed=true, any issue means passed=false. Reach "
        "a decision once - do not second-guess or re-open something you've "
        "already judged.\n\n"
        "If something is genuinely ambiguous or subjective (reasonable "
        "people could disagree, not just 'this needs care to check') - "
        "including a requirement with no reference, standard, or precedent "
        "to verify it against - set `confident=False` and use "
        "`question_for_human` to ask the specific thing you're unsure about, "
        "instead of forcing a pass or fail you don't actually believe. "
        "Unresolvable ambiguity belongs in `confident=False`, never in "
        "`passed=False`. Use this rarely - only for genuine ambiguity, not "
        "as a way to avoid a hard-but-clear judgment."
    ),
)


def build_evaluator_prompt(
    query: str, output: str, past_corrections: list[CorrectionEntry]
) -> str:
    parts = [
        f"Task (the requirements): {query}",
        f"Attempt:\n{output}",
    ]
    if past_corrections:
        parts.append(
            "Learned from past human corrections - problems this evaluator has "
            "missed or gotten wrong before, across other tasks. Apply this "
            "general judgment here too, not just when it happens to match "
            "exactly:\n" + "\n".join(f"- {c.reason}" for c in past_corrections)
        )
    return "\n\n".join(parts)


def build_executor_prompt(
    query: str,
    previous_output: str | None,
    critique: str | None,
    issues: list[str] | None = None,
) -> str:
    if previous_output is None:
        return query
    issues_list = "\n".join(f"- {c}" for c in issues) if issues else None
    return (
        f"{query}\n\n"
        f"Your previous attempt:\n{previous_output}\n\n"
        f"That attempt failed review for this reason: {critique}\n"
        + (f"Specifically:\n{issues_list}\n" if issues_list else "")
        + "Produce a corrected attempt that fixes exactly these issues without "
        "regressing anything that already passed."
    )
