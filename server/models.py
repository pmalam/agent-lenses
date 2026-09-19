from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunChecklist(BaseModel):
    criteria: list[str] = Field(description="Concrete, checkable pass/fail criteria for the task")
    time_limit_minutes: int = Field(description="Wall-clock budget for the whole run")
    token_budget: int = Field(description="Approximate total token budget across all iterations")


class Verdict(BaseModel):
    passed: bool
    reasoning: str
    failed_criteria: list[str] = Field(default_factory=list)


class Iteration(BaseModel):
    index: int
    prompt: str
    output: str
    verdict: Verdict | None = None


class ThoughtEvent(BaseModel):
    at: datetime = Field(default_factory=_now)
    message: str


RunStatus = Literal[
    "checklisting", "running", "evaluating", "passed", "failed", "max_iterations"
]


class RunState(BaseModel):
    run_id: str
    query: str
    status: RunStatus = "checklisting"
    checklist: RunChecklist | None = None
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
