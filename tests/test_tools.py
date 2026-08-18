"""
Regression test: verifies the four fatigue-criterion tools against the
official solutions-manual values for the test problem documented in
README.md ("Validation" section).

This turns the validation claim in the README into something anyone who
clones the repo can actually re-check, instead of just taking it on faith.

Run with: pytest tests/test_tools.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools

# Problem parameters (see README.md "Validation" and agent.py TASK):
# Ma = 70 N·m, Ta = 45 N·m, Mm = 55 N·m, Tm = 35 N·m
# Su = 700 MPa, Sy = 560 MPa, Se = 210 MPa, Kf = 2.2, Kfs = 1.8, n = 2.0
COMMON = dict(Ma=70, Ta=45, Mm=55, Tm=35, Kf=2.2, Kfs=1.8, n=2.0)

# Expected minimum diameters (mm), confirmed against the official solutions
# manual for this problem.
EXPECTED = {
    "goodman": 27.27,
    "gerber": 25.853,
    "asme_elliptic": 25.769,
    "soderberg": 27.696,
}

TOLERANCE_MM = 0.01  # allows for rounding differences vs. the manual


def _extract_diameter(json_result: str) -> float:
    import json
    return json.loads(json_result)["min_diameter_mm"]


def test_goodman():
    d = _extract_diameter(tools.calculate_diameter_goodman(**COMMON, Se=210, Sut=700))
    assert math.isclose(d, EXPECTED["goodman"], abs_tol=TOLERANCE_MM)


def test_gerber():
    d = _extract_diameter(tools.calculate_diameter_gerber(**COMMON, Se=210, Sut=700))
    assert math.isclose(d, EXPECTED["gerber"], abs_tol=TOLERANCE_MM)


def test_asme_elliptic():
    d = _extract_diameter(tools.calculate_diameter_asme_elliptic(**COMMON, Se=210, Sy=560))
    assert math.isclose(d, EXPECTED["asme_elliptic"], abs_tol=TOLERANCE_MM)


def test_soderberg():
    d = _extract_diameter(tools.calculate_diameter_soderberg(**COMMON, Se=210, Sy=560))
    assert math.isclose(d, EXPECTED["soderberg"], abs_tol=TOLERANCE_MM)


def test_conservatism_order():
    """Sanity check independent of the manual: Soderberg should be the most
    conservative criterion, Goodman next, then Gerber/ASME Elliptic closer
    together and less conservative — this is a property of the criteria
    themselves, not specific to this problem's numbers."""
    d_goodman = _extract_diameter(tools.calculate_diameter_goodman(**COMMON, Se=210, Sut=700))
    d_soderberg = _extract_diameter(tools.calculate_diameter_soderberg(**COMMON, Se=210, Sy=560))
    d_gerber = _extract_diameter(tools.calculate_diameter_gerber(**COMMON, Se=210, Sut=700))
    d_asme = _extract_diameter(tools.calculate_diameter_asme_elliptic(**COMMON, Se=210, Sy=560))

    assert d_soderberg > d_goodman > d_gerber
    assert d_soderberg > d_goodman > d_asme


def test_gerber_rejects_zero_alternating_component():
    """Gerber's closed form divides by the alternating term (A); Ma=Ta=0
    should raise, not silently return a nonsense value."""
    import pytest
    with pytest.raises(ValueError):
        tools.calculate_diameter_gerber(Ma=0, Ta=0, Mm=55, Tm=35, Kf=2.2, Kfs=1.8, Se=210, Sut=700, n=2.0)
