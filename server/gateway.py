"""Shared Pydantic AI Gateway wiring for both the executor and evaluator models.

Both models are Modal vLLM endpoints reached through the Pydantic AI Gateway
(BYOK providers configured in the Logfire gateway UI). See ../script.py for
the original single-model reference version this was consolidated from.
"""

from typing import Any

from openai.types.chat import ChatCompletion
from pydantic_ai.models.openai import OpenAIChatModel, _ChatCompletion
from pydantic_ai.providers.gateway import gateway_provider

# Modal returns `metadata.weight_versions` as a list, but the OpenAI schema types
# `metadata` as `dict[str, str]`. Widen it on both models that see the payload:
# the SDK's (which serializes it) and pydantic-ai's (which validates it).
# Applied once at import time, shared by every model built through this module.
for _model in (ChatCompletion, _ChatCompletion):
    _model.model_fields["metadata"].annotation = dict[str, Any] | None
    _model.model_rebuild(force=True)

MODEL_NAME = "google/gemma-4-31B-it"
ROUTE = "evaluator-configuration"

# Executor and Evaluator deliberately share one model - a same-model
# self-critique loop is a more realistic setup than an artificial
# strong/weak split. (The gemma-3-1b-it / agentlenses-provider endpoint
# is still deployed but no longer used by either role.)
EXECUTOR_MODEL_NAME = MODEL_NAME
EXECUTOR_ROUTE = ROUTE

EVALUATOR_MODEL_NAME = MODEL_NAME
EVALUATOR_ROUTE = ROUTE


def build_model(model_name: str, route: str) -> OpenAIChatModel:
    provider = gateway_provider("openai-chat", route=route)
    return OpenAIChatModel(model_name, provider=provider)


def executor_model() -> OpenAIChatModel:
    return build_model(EXECUTOR_MODEL_NAME, EXECUTOR_ROUTE)


def evaluator_model() -> OpenAIChatModel:
    return build_model(EVALUATOR_MODEL_NAME, EVALUATOR_ROUTE)
