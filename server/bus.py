import asyncio


class RunEventBus:
    """Per-run pub/sub so the SSE endpoint can stream state updates as the
    correction loop produces them, without polling."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(run_id, []).append(queue)
        return queue

    async def publish(self, run_id: str, event: dict) -> None:
        for queue in self._queues.get(run_id, []):
            await queue.put(event)

    def close(self, run_id: str) -> None:
        for queue in self._queues.get(run_id, []):
            queue.put_nowait(None)  # sentinel: end of stream
        self._queues.pop(run_id, None)


event_bus = RunEventBus()
