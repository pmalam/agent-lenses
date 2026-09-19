import json
import uuid

import logfire
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.bus import event_bus
from server.loop import mark_false_negative, run_task
from server.store import run_store

logfire.configure()
logfire.instrument_pydantic_ai()

app = FastAPI(title="agent-lenses backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon demo only - tighten before anything real
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRunRequest(BaseModel):
    query: str


class StartRunResponse(BaseModel):
    run_id: str


@app.post("/run", response_model=StartRunResponse)
async def start_run(req: StartRunRequest, background_tasks: BackgroundTasks) -> StartRunResponse:
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_task, run_id, req.query)
    return StartRunResponse(run_id=run_id)


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    state = run_store.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return state.model_dump(mode="json")


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_generator():
        # Subscribe before reading the snapshot, so an update published in
        # between can't be missed (better a duplicate initial message than
        # a silently dropped one).
        queue = event_bus.subscribe(run_id)

        state = run_store.get(run_id)
        if state is not None:
            yield f"data: {state.model_dump_json()}\n\n"
            if state.status in ("passed", "failed", "max_iterations"):
                return

        while True:
            event = await queue.get()
            if event is None:  # sentinel: run finished
                break
            yield f"data: {json.dumps(event['state'])}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class MarkFailureRequest(BaseModel):
    reason: str


class MarkFailureResponse(BaseModel):
    new_run_id: str


@app.post("/runs/{run_id}/mark-failure", response_model=MarkFailureResponse)
async def mark_failure(
    run_id: str, req: MarkFailureRequest, background_tasks: BackgroundTasks
) -> MarkFailureResponse:
    if run_store.get(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run_id")

    new_run_id = str(uuid.uuid4())
    background_tasks.add_task(mark_false_negative, run_id, req.reason, new_run_id)
    return MarkFailureResponse(new_run_id=new_run_id)
