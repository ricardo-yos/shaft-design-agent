"""
tools.py — Deterministic calculation tools for shaft-design-agent.

Follows the pattern from Episode 2 of the series (readytensor/building-agents):
a @tool decorator that builds each tool's JSON Schema from the Python
function signature, so agent.py doesn't need to maintain schemas by hand
alongside the code.

The four tools below implement the fatigue failure criteria from Shigley's
Mechanical Engineering Design (Ch. 7, Eq. 7-9 to 7-12, numbering may vary
±1 depending on edition): DE-Goodman, DE-Gerber, DE-ASME Elliptic, and
DE-Soderberg. These are closed-form equations, already solved for the
diameter `d` — the LLM never rewrites or algebraically manipulates them; it
only extracts Ma, Ta, Mm, Tm and the material properties from the problem
statement, and decides which criterion/criteria to call.

WARNING: validate these four formulas against a manual solution of the
problem before trusting the result — Gerber and ASME Elliptic in
particular have algebraic forms that are easier to transcribe incorrectly
than Goodman/Soderberg.
"""
import inspect
import json
import math
from typing import get_type_hints


# --- Tool-call telemetry: lets you audit later, via tool_calls.jsonl, the
# sequence of calls the agent made (which tools, with which parameters, in
# which round).
TOOL_CALLS = []  # list of {"round": n, "tool": name, "args": {...}}
CURRENT_ROUND = 0  # set by agent.py on each loop iteration


def write_tool_telemetry():
    """Write this run's tool calls to tool_calls.jsonl, one per line, in the
    order they occurred."""
    with open("tool_calls.jsonl", "w", encoding="utf-8") as f:
        for call in TOOL_CALLS:
            f.write(json.dumps(call) + "\n")


_PY_TO_JSON_TYPE = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
}


def tool(func):
    """Decorator that turns a plain Python function into a tool: derives the
    JSON Schema from the signature (types + docstring) and records every
    call in TOOL_CALLS for telemetry/auditing.

    Convention: every parameter must have a type hint (int/float/str/bool)
    and a "name: description" line in the docstring. The function must
    return a string (what the model will "see" as the result).
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc = inspect.getdoc(func) or ""

    doc_lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
    description = doc_lines[0] if doc_lines else func.__name__

    param_docs = {}
    for ln in doc_lines[1:]:
        if ":" in ln:
            name, _, desc = ln.partition(":")
            param_docs[name.strip()] = desc.strip()

    properties = {}
    required = []
    for name, param in sig.parameters.items():
        py_type = hints.get(name, str)
        properties[name] = {
            "type": _PY_TO_JSON_TYPE.get(py_type, "string"),
            "description": param_docs.get(name, ""),
        }
        if param.default is inspect.Parameter.empty:
            required.append(name)

    func.tool_definition = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }

    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        TOOL_CALLS.append({"round": CURRENT_ROUND, "tool": func.__name__, "args": kwargs})
        return result

    wrapper.__name__ = func.__name__
    wrapper.tool_definition = func.tool_definition
    return wrapper


# --- Terms shared by all four criteria --------------------------------------
#
# A = von Mises combination of the ALTERNATING component (Ma, Ta), already
#     including Kf/Kfs.
# B = von Mises combination of the MEAN component (Mm, Tm), already
#     including Kf/Kfs.
# Both are computed in N·mm internally (the problem gives N·m; we convert
# by multiplying by 1000 before applying the formula, so dividing by
# Se/Sut/Sy in MPa = N/mm² closes dimensionally in mm).

def _term_A(Ma_Nm: float, Ta_Nm: float, Kf: float, Kfs: float) -> float:
    Ma, Ta = Ma_Nm * 1000, Ta_Nm * 1000  # N·m -> N·mm
    return math.sqrt(4 * (Kf * Ma) ** 2 + 3 * (Kfs * Ta) ** 2)


def _term_B(Mm_Nm: float, Tm_Nm: float, Kf: float, Kfs: float) -> float:
    Mm, Tm = Mm_Nm * 1000, Tm_Nm * 1000  # N·m -> N·mm
    return math.sqrt(4 * (Kf * Mm) ** 2 + 3 * (Kfs * Tm) ** 2)


# --- The four fatigue-criterion tools ---------------------------------------


@tool
def calculate_diameter_goodman(Ma: float, Ta: float, Mm: float, Tm: float, Kf: float, Kfs: float, Se: float, Sut: float, n: float) -> str:
    """Calculate the minimum shaft diameter using the DE-Goodman fatigue criterion.
    Ma: alternating bending moment, in N·m
    Ta: alternating torque, in N·m
    Mm: mean bending moment, in N·m
    Tm: mean torque, in N·m
    Kf: fatigue stress-concentration factor for bending (dimensionless)
    Kfs: fatigue stress-concentration factor for torsion (dimensionless)
    Se: corrected endurance limit of the material, in MPa
    Sut: ultimate tensile strength of the material, in MPa
    n: desired design factor (factor of safety), dimensionless
    """
    A = _term_A(Ma, Ta, Kf, Kfs)
    B = _term_B(Mm, Tm, Kf, Kfs)
    d = ((16 * n / math.pi) * (A / Se + B / Sut)) ** (1 / 3)
    return json.dumps({
        "criterion": "DE-Goodman",
        "min_diameter_mm": round(d, 3),
        "inputs": {"Ma_Nm": Ma, "Ta_Nm": Ta, "Mm_Nm": Mm, "Tm_Nm": Tm,
                    "Kf": Kf, "Kfs": Kfs, "Se_MPa": Se, "Sut_MPa": Sut, "n": n},
    })


@tool
def calculate_diameter_soderberg(Ma: float, Ta: float, Mm: float, Tm: float, Kf: float, Kfs: float, Se: float, Sy: float, n: float) -> str:
    """Calculate the minimum shaft diameter using the DE-Soderberg fatigue criterion.
    Ma: alternating bending moment, in N·m
    Ta: alternating torque, in N·m
    Mm: mean bending moment, in N·m
    Tm: mean torque, in N·m
    Kf: fatigue stress-concentration factor for bending (dimensionless)
    Kfs: fatigue stress-concentration factor for torsion (dimensionless)
    Se: corrected endurance limit of the material, in MPa
    Sy: yield strength of the material, in MPa
    n: desired design factor (factor of safety), dimensionless
    """
    A = _term_A(Ma, Ta, Kf, Kfs)
    B = _term_B(Mm, Tm, Kf, Kfs)
    d = ((16 * n / math.pi) * (A / Se + B / Sy)) ** (1 / 3)
    return json.dumps({
        "criterion": "DE-Soderberg",
        "min_diameter_mm": round(d, 3),
        "inputs": {"Ma_Nm": Ma, "Ta_Nm": Ta, "Mm_Nm": Mm, "Tm_Nm": Tm,
                    "Kf": Kf, "Kfs": Kfs, "Se_MPa": Se, "Sy_MPa": Sy, "n": n},
    })


@tool
def calculate_diameter_asme_elliptic(Ma: float, Ta: float, Mm: float, Tm: float, Kf: float, Kfs: float, Se: float, Sy: float, n: float) -> str:
    """Calculate the minimum shaft diameter using the DE-ASME Elliptic fatigue criterion.
    Ma: alternating bending moment, in N·m
    Ta: alternating torque, in N·m
    Mm: mean bending moment, in N·m
    Tm: mean torque, in N·m
    Kf: fatigue stress-concentration factor for bending (dimensionless)
    Kfs: fatigue stress-concentration factor for torsion (dimensionless)
    Se: corrected endurance limit of the material, in MPa
    Sy: yield strength of the material, in MPa
    n: desired design factor (factor of safety), dimensionless
    """
    A = _term_A(Ma, Ta, Kf, Kfs)
    B = _term_B(Mm, Tm, Kf, Kfs)
    d = ((16 * n / math.pi) * math.sqrt((A / Se) ** 2 + (B / Sy) ** 2)) ** (1 / 3)
    return json.dumps({
        "criterion": "DE-ASME Elliptic",
        "min_diameter_mm": round(d, 3),
        "inputs": {"Ma_Nm": Ma, "Ta_Nm": Ta, "Mm_Nm": Mm, "Tm_Nm": Tm,
                    "Kf": Kf, "Kfs": Kfs, "Se_MPa": Se, "Sy_MPa": Sy, "n": n},
    })


@tool
def calculate_diameter_gerber(Ma: float, Ta: float, Mm: float, Tm: float, Kf: float, Kfs: float, Se: float, Sut: float, n: float) -> str:
    """Calculate the minimum shaft diameter using the DE-Gerber fatigue criterion.
    Ma: alternating bending moment, in N·m
    Ta: alternating torque, in N·m
    Mm: mean bending moment, in N·m
    Tm: mean torque, in N·m
    Kf: fatigue stress-concentration factor for bending (dimensionless)
    Kfs: fatigue stress-concentration factor for torsion (dimensionless)
    Se: corrected endurance limit of the material, in MPa
    Sut: ultimate tensile strength of the material, in MPa
    n: desired design factor (factor of safety), dimensionless
    """
    A = _term_A(Ma, Ta, Kf, Kfs)
    B = _term_B(Mm, Tm, Kf, Kfs)
    if A == 0:
        # No alternating component: Gerber degenerates (division by A). This
        # edge case isn't covered by the standard closed form.
        raise ValueError("Gerber requires a nonzero alternating component (A); Ma and Ta cannot both be zero.")
    d = ((8 * n * A) / (math.pi * Se) * (1 + math.sqrt(1 + (2 * B * Se / (A * Sut)) ** 2))) ** (1 / 3)
    return json.dumps({
        "criterion": "DE-Gerber",
        "min_diameter_mm": round(d, 3),
        "inputs": {"Ma_Nm": Ma, "Ta_Nm": Ta, "Mm_Nm": Mm, "Tm_Nm": Tm,
                    "Kf": Kf, "Kfs": Kfs, "Se_MPa": Se, "Sut_MPa": Sut, "n": n},
    })


TOOLS = [calculate_diameter_goodman, calculate_diameter_gerber,
         calculate_diameter_asme_elliptic, calculate_diameter_soderberg]
