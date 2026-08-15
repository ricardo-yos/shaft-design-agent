"""
shaft-design-agent — adapted from Episode 2 (Tools) of
readytensor/building-agents.

The loop is identical to Episode 2: a while loop that dispatches tool calls
by name. What's different is the domain, not the mechanism:

  - No `bash`: the agent never generates or runs calculation code. It only
    calls the fixed tools in tools.py (formulas already solved and
    audited).
  - No `initial/`/`sandbox/`: there's no codebase to explore — the input is
    an engineering problem statement, not a code repository.
  - The model's only real "decision" is: extract Ma, Ta, Mm, Tm, Kf, Kfs,
    and the material properties from the problem statement, and choose
    which fatigue criterion (or criteria) applies.

See ../README.md for the full rationale behind these architecture
decisions and the validation process against a manual solution.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tiktoken import get_encoding

import tools as tools_module  # aliased: we set tools_module.CURRENT_ROUND each iteration
from tools import TOOLS, write_tool_telemetry

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def make_client(base_url: str) -> OpenAI:
    """Connect to the LLM provider behind `base_url` — any OpenAI-compatible
    endpoint. The API key is picked by the provider detected in base_url,
    so switching providers means changing only LLM_BASE_URL, never moving
    keys around."""
    by_provider = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
        "googleapis": "GOOGLE_API_KEY",
        "manus": "MANUS_API_KEY",
    }
    key_var = "OPENAI_API_KEY"
    for fragment, provider_key_var in by_provider.items():
        if fragment in base_url:
            key_var = provider_key_var
            break
    return OpenAI(api_key=os.environ.get(key_var), base_url=base_url or None)


# The system prompt lives in system_prompt.md next to this file: prompt
# text is configuration, not loop logic.
SYSTEM = (Path(__file__).parent / "system_prompt.md").read_text(encoding="utf-8")

# TASK = the raw problem statement (prose, exactly as written in the
# textbook). The agent extracts Ma, Ta, Mm, Tm and the material properties
# itself, and decides which fatigue criteria apply based on what the
# statement asks for.
#
# Source: Problem 7-1, Shigley's Mechanical Engineering Design, 10th ed.,
# Chapter 7. Used here for validation against the official solutions
# manual — see "Validation" in README.md.
TASK = (
    "A shaft is loaded in bending and torsion such that Ma = 70 N.m, "
    "Ta = 45 N.m, Mm = 55 N.m, and Tm = 35 N.m. For the shaft, Su = 700 MPa "
    "and Sy = 560 MPa, and a fully corrected endurance limit of Se = 210 MPa "
    "is assumed. Let Kf = 2.2 and Kfs = 1.8. With a design factor of 2.0 "
    "determine the minimum acceptable diameter of the shaft using the "
    "(a) DE-Gerber criterion. "
    "(b) DE-ASME Elliptic criterion. "
    "(c) DE-Soderberg criterion. "
    "(d) DE-Goodman criterion. "
    "Discuss and compare the results."
)

# --- Usage telemetry: token counts per run, recorded by run_agent as it
# goes. The agent only RECORDS (to metrics.json); rendering a summary is up
# to whatever reads the file (e.g. the run.py harness, if you use it).
USAGE = {
    "iterations": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "per_iter": [],
}


def write_metrics(model: str, system: str, task: str):
    """Write this run's token usage to metrics.json."""
    metrics = {
        "agents": [{"label": "agent", **USAGE}],
        "inputs": {"system": system, "task": task},
        "config": {"MODEL": model},
    }
    with open("metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


_TOKENIZER = get_encoding("cl100k_base")


def _count_tokens(messages):
    """Real token count (tiktoken) of these messages' content — used to
    record each round's tool-result token total."""
    return len(_TOKENIZER.encode("\n".join(str(m.get("content") or "") for m in messages)))


# Descriptive label + unit for each tool parameter, used only to render
# section 1 readably. Keep this in sync with the parameter docstrings in
# tools.py — it's presentation only, doesn't affect what's passed to the
# tools themselves.
_PARAM_LABELS = {
    "Ma": ("Alternating bending moment", "N·m"),
    "Ta": ("Alternating torque", "N·m"),
    "Mm": ("Mean bending moment", "N·m"),
    "Tm": ("Mean torque", "N·m"),
    "Kf": ("Fatigue stress-concentration factor for bending", ""),
    "Kfs": ("Fatigue stress-concentration factor for torsion", ""),
    "Se": ("Corrected endurance limit", "MPa"),
    "Sut": ("Ultimate tensile strength", "MPa"),
    "Sy": ("Yield strength", "MPa"),
    "n": ("Design factor", ""),
}


def _render_deterministic_sections(executed_calls: list) -> str:
    """Build sections 1-4 of the final answer directly from the tool calls
    that actually ran — no LLM involved. These sections are pure
    restatement of tool inputs/outputs (extracted parameters, which
    criteria were applied, each tool's result, and a sorted comparison),
    so there's no reasoning step to delegate to the model. This exists
    because asking the model to restate this in prose proved unreliable
    in practice: it repeatedly treated "I already called the tool" as
    equivalent to "I already told the user", and skipped straight to the
    discussion — even with explicit instructions not to. See system_prompt.md
    for what the model is still responsible for (sections 5-6)."""
    if not executed_calls:
        return "### 1. Parameters Extracted from the Statement\n\n(No tool calls were made.)\n"

    # Section 1: union of all parameters seen across calls (a given
    # problem's Ma/Ta/Mm/Tm/Kf/Kfs/n are shared across criteria — only
    # Se/Sut/Sy vary by which criterion needs which).
    params = {}
    for call in executed_calls:
        params.update(call["args"])
    param_lines = "\n".join(
        f"* **{_PARAM_LABELS.get(k, (k, ''))[0]} ({k}):** {v}"
        + (f" {_PARAM_LABELS[k][1]}" if k in _PARAM_LABELS and _PARAM_LABELS[k][1] else "")
        for k, v in params.items()
    )
    section1 = f"### 1. Parameters Extracted from the Statement\n{param_lines}\n"

    # Section 2 + 3: criteria applied and each tool's result, parsed from
    # the tool's own JSON output (so the label comes from the tool, not a
    # separately hardcoded mapping that could drift out of sync).
    parsed = []
    for call in executed_calls:
        try:
            parsed.append(json.loads(call["result"]))
        except (json.JSONDecodeError, TypeError):
            continue  # a failed tool call's error string isn't JSON; skip it here

    letters = "abcdefgh"
    criteria_list = "\n".join(f"({letters[i]}) {p['criterion']} criterion" for i, p in enumerate(parsed))
    section2 = f"### 2. Criteria Applied\nIn the order requested by the problem statement:\n{criteria_list}\n"

    results_list = "\n".join(f"* **{p['criterion']}:** {p['min_diameter_mm']} mm" for p in parsed)
    section3 = f"### 3. Tool Results (Minimum Diameter per Criterion)\n{results_list}\n"

    if len(parsed) > 1:
        ranked = sorted(parsed, key=lambda p: p["min_diameter_mm"], reverse=True)
        rows = "\n".join(
            f"| {i + 1} | {p['criterion']} | {p['min_diameter_mm']} |"
            for i, p in enumerate(ranked)
        )
        section4 = (
            "### 4. Comparison Table (Largest to Smallest Diameter)\n"
            "| Rank | Criterion | Minimum Diameter (mm) |\n"
            "|:----:|:----------|:----------------------:|\n"
            f"{rows}\n"
        )
    else:
        section4 = ""  # single criterion: nothing to compare

    return "\n".join(s for s in [section1, section2, section3, section4] if s)


def run_agent(client, model: str, system: str, tools: list, task: str) -> str:
    """Run the agent loop on `task` until the model stops requesting tool
    calls; return the final answer. Sections 1-4 (extracted parameters,
    criteria applied, tool results, comparison) are generated
    deterministically from the executed tool calls — see
    _render_deterministic_sections. The model is only responsible for
    sections 5-6 (discussion, assumptions), per system_prompt.md."""
    tools_by_name = {t.__name__: t for t in tools}
    tool_defs = [t.tool_definition for t in tools]
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task},
    ]
    executed_calls = []  # [{"name": ..., "args": {...}, "result": "..."}] — successful calls only
    iteration = 0

    while True:
        iteration += 1
        tools_module.CURRENT_ROUND = iteration
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=tool_defs,
            max_tokens=2048,  # balances two failure modes on Groq's free/on-demand
                               # tier: too low truncates the final answer (finish_reason
                               # = "length"); too high (e.g. 4096) can push a request
                               # over the tier's tokens-per-minute limit once the
                               # conversation has grown from prior tool calls (HTTP 413
                               # rate_limit_exceeded). Raise this only if you also have
                               # headroom on TPM (paid tier), or shorten the requested
                               # final-answer format in system_prompt.md instead.
            extra_body={"reasoning_effort": "none"},
            # Groq-specific, only applies to reasoning models like qwen/qwen3.6-27b.
            # Without this, the model can spend its ENTIRE max_tokens budget on
            # hidden chain-of-thought before writing any visible text — producing
            # an empty final response even though finish_reason="length" says it
            # ran out of room. If you switch to a non-reasoning model or a
            # different provider, remove this line.
        )
        usage = resp.usage
        finish_reason = resp.choices[0].finish_reason
        if finish_reason == "length":
            print(f"  ! WARNING: response cut off by max_tokens (finish_reason=length) on round {iteration}")
        USAGE["iterations"] = iteration
        USAGE["input_tokens"] += usage.prompt_tokens
        USAGE["output_tokens"] += usage.completion_tokens
        USAGE["per_iter"].append({"model_in": usage.prompt_tokens, "model_out": usage.completion_tokens, "tools": 0, "tools_out": 0})

        msg = resp.choices[0].message
        USAGE["per_iter"][-1]["tools"] = len(msg.tool_calls or [])
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            deterministic = _render_deterministic_sections(executed_calls)
            return f"{deterministic}\n{msg.content or ''}"

        round_tool_msgs = []
        for tc in msg.tool_calls:
            try:
                fn = tools_by_name[tc.function.name]
                args = json.loads(tc.function.arguments)
                arg_preview = ", ".join(f"{k}={v!r}" for k, v in args.items())
                print(f"> {tc.function.name}({arg_preview})")
                result = fn(**args)
                executed_calls.append({"name": tc.function.name, "args": args, "result": result})
            except (TypeError, KeyError, json.JSONDecodeError, ValueError) as e:
                # Tool errors come back to the model as the tool result, not as
                # an agent crash — the model can self-correct next iteration.
                result = f"Error executing {tc.function.name}: {type(e).__name__}: {e}"
                print(f"  ! {result}")
            preview = result if len(result) < 5000 else result[:5000] + "...[truncated]"
            print(f"  {preview}\n")
            tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result}
            round_tool_msgs.append(tool_msg)
            messages.append(tool_msg)

        USAGE["per_iter"][-1]["tools_out"] = _count_tokens(round_tool_msgs)


def write_response(task: str, final: str):
    """Save this run's problem statement and final answer to response.md —
    same rationale as write_tool_telemetry/write_metrics: without this, the
    result only lives in the terminal and is lost once the session closes."""
    with open("response.md", "w", encoding="utf-8") as f:
        f.write(f"# Problem statement\n\n{task}\n\n# Agent response\n\n{final}\n")


def main():
    # No sandbox/initial: there's no codebase to copy/isolate — the only
    # input is the problem statement defined in TASK.
    # Resolved relative to this file (not the current working directory),
    # so it works regardless of where you run `python agent.py` from.
    # Adjust if your .env lives somewhere else in your project structure.
    load_dotenv(Path(__file__).parent / ".env")
    base_url = os.environ.get("LLM_BASE_URL") or ""
    model = os.environ.get("LLM_AGENT_MODEL", "qwen/qwen3-32b")
    client = make_client(base_url)

    print(f"USER: {TASK}\n")
    final = run_agent(client, model, SYSTEM, TOOLS, TASK)
    print(f"\n=== FINAL RESPONSE ===\n\n{final}")
    write_tool_telemetry()
    write_metrics(model, SYSTEM, TASK)
    write_response(TASK, final)


if __name__ == "__main__":
    main()
