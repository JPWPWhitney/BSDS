"""Scenario registry: id -> module implementing the scenario contract.

Contract per plan Task 3: module attributes ID, TITLE, KIND ("single"|"sweep"),
DESCRIPTION, and run(params) -> RunResult; sweep scenarios add AXES and
sweep_grid() -> list[param dicts].
"""

from . import asteroid_arrival, basic_orbit, drag_deorbit, hohmann

SCENARIOS = {
    basic_orbit.ID: basic_orbit,
    hohmann.ID: hohmann,
    drag_deorbit.ID: drag_deorbit,
    asteroid_arrival.ID: asteroid_arrival,
}
