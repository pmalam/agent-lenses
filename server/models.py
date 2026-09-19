from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Verdict(BaseModel):
    passed: bool
    reasoning: str
    issues: list[str] = Field(
        default_factory=list,
        description="Specific problems found in this attempt relative to the "
        "stated requirements - not references to a fixed checklist, there isn't one.",
    )
    confident: bool = Field(
        default=True,
        description="False when the criteria are genuinely ambiguous/subjective "
        "and a human should weigh in rather than trusting this verdict outright.",
    )
    question_for_human: str | None = Field(
        default=None,
        description="Set only when confident=False - the specific thing a human "
        "should confirm or decide.",
    )


class Iteration(BaseModel):
    index: int
    prompt: str
    output: str
    verdict: Verdict | None = None


class ThoughtEvent(BaseModel):
    at: datetime = Field(default_factory=_now)
    message: str


RunStatus = Literal[
    "running", "evaluating", "passed", "failed", "max_iterations", "needs_review"
]


class RunState(BaseModel):
    run_id: str
    query: str
    status: RunStatus = "running"
    iterations: list[Iteration] = Field(default_factory=list)
    thoughts: list[ThoughtEvent] = Field(default_factory=list)
    final_output: str | None = None
    trace_url: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CorrectionEntry(BaseModel):
    """A human-flagged false negative, persisted and fed into future
    Evaluator prompts as extra context."""

    run_id: str
    query: str
    output: str
    reason: str
    at: datetime = Field(default_factory=_now)
