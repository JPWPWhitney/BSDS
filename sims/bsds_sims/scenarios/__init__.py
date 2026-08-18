"""Scenario registry: id -> module implementing the scenario contract.

Contract per plan Task 3: module attributes ID, TITLE, KIND ("single"|"sweep"),
DESCRIPTION, and run(params) -> RunResult; sweep scenarios add AXES and
sweep_grid() -> list[param dicts].
"""

from . import basic_orbit

SCENARIOS = {
    basic_orbit.ID: basic_orbit,
}
