"""V10 Python data models — reproducible quantitative foundation.

Every model:
    1. Is fully runnable: ``python tools/data_models/<model>.py``
    2. Emits a JSON artifact under ``data/data_models/<model>.json``
    3. Renders a Markdown report under ``docs/data_models/<model>.md``
    4. Is covered by ``tests/v10/data_models/test_<model>.py``
    5. Runs in CI via ``.github/workflows/data_models.yml``

The six models are the single source of truth for every quantitative
decision in V10:
    - cost_model         · ¥ per minute / per episode / per project
    - throughput_model   · M/M/c queueing: latency, queue depth, SLA
    - quality_model      · Monte Carlo 7-dim score distributions
    - capacity_model     · veFaaS / TOS / NAS / SQLite→Postgres tipping
    - footprint_model    · container image size + cold start
    - validation_model   · 7-dim scoring calibration (regression)
"""
from __future__ import annotations

__all__ = [
    "cost_model",
    "throughput_model",
    "quality_model",
    "capacity_model",
    "footprint_model",
    "validation_model",
]
