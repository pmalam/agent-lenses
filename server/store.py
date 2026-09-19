import json
from pathlib import Path
from threading import Lock

from server.models import CorrectionEntry, RunState

_CORRECTIONS_PATH = Path(__file__).parent / "corrections.json"


class RunStore:
    """In-memory run state, keyed by run_id. Fine for a single-process
    hackathon demo; would need a real DB to survive a restart or scale
    past one process."""

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = Lock()

    def create(self, state: RunState) -> None:
        with self._lock:
            self._runs[state.run_id] = state

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)

    def update(self, state: RunState) -> None:
        with self._lock:
            self._runs[state.run_id] = state


class CorrectionLog:
    """Persisted false-negative corrections (JSON file), fed into future
    Evaluator prompts as extra context."""

    def __init__(self, path: Path = _CORRECTIONS_PATH) -> None:
        self._path = path
        self._lock = Lock()
        if not self._path.exists():
            self._path.write_text("[]")

    def add(self, entry: CorrectionEntry) -> None:
        with self._lock:
            entries = self._read()
            entries.append(entry.model_dump(mode="json"))
            self._path.write_text(json.dumps(entries, indent=2))

    def recent(self, limit: int = 5) -> list[CorrectionEntry]:
        with self._lock:
            entries = self._read()
        return [CorrectionEntry.model_validate(e) for e in entries[-limit:]]

    def _read(self) -> list[dict]:
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []


run_store = RunStore()
correction_log = CorrectionLog()
