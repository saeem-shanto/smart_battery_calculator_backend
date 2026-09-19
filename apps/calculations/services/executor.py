from __future__ import annotations

import time
from dataclasses import dataclass, field

from .interfaces import EngineInput
from .octave_engine import OctaveEngine
from .result_contract import validate_result_contract


@dataclass(frozen=True)
class EngineExecution:
    engine_version: str
    result: dict
    runtime_ms: int
    artifacts: dict[str, bytes] = field(default_factory=dict)


def execute_calculation(data: EngineInput) -> EngineExecution:
    engine = OctaveEngine()
    started = time.perf_counter()
    result, artifacts = engine.calculate(data)
    result = validate_result_contract(result, data)
    runtime_ms = max(0, int((time.perf_counter() - started) * 1000))
    return EngineExecution(engine.version, result, runtime_ms, artifacts)
