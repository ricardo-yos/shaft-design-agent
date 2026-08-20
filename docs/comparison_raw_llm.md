# Comparison: fixed tools vs. a raw LLM doing the math

Same problem statement — Problem 7-1, Shigley's Mechanical Engineering
Design, 10th ed., Chapter 7 (see [example_run.md](example_run.md)) —
asked two different ways:

1. **This agent** — LLM extracts parameters, calls the four fixed formula
   tools in `tools.py`. Result: matches the official solutions manual
   exactly (see "Validation" in the main README).
2. **A raw LLM, no tools** — the same problem statement pasted directly
   into a chat interface, asking the model to solve it itself.

## Results

| Criterion | This agent (validated) | Raw LLM (no tools) | Difference |
|-----------|:----------------------:|:-------------------:|:----------:|
| DE-Gerber | 25.853 mm | 27.48 mm | +6.29% |
| DE-ASME Elliptic | 25.769 mm | 27.62 mm | +7.18% |
| DE-Goodman | 27.270 mm | 29.22 mm | +7.15% |
| DE-Soderberg | 27.696 mm | 29.68 mm | +7.16% |

## What's notable here

The raw LLM isn't randomly wrong — three of the four criteria (ASME
Elliptic, Goodman, Soderberg) diverge from the validated result by almost
exactly the same margin (+7.15% to +7.18%), while Gerber diverges by a
somewhat smaller +6.29%. That consistency points to a **systematic**
deviation somewhere in the raw LLM's calculation (a coefficient, an
intermediate rounding, or how it combined a shared term), not a one-off
misreading of the problem — but without seeing its step-by-step work,
there's no way to pin down exactly where the divergence happened.

That opacity is precisely the risk this project's architecture is built
to avoid (see "Architecture decision" in the main README). With the
fixed tools, every number is traceable to an audited formula. With free
computation, a plausible-looking result can be several percent off in a
way that isn't visible from the output alone — it takes an independent
source of truth (here, the solutions manual) to catch it.

## Caveat

This is a single comparison on a single problem, with a single raw-LLM
run — it demonstrates that the failure mode is real, not that it happens
at a fixed rate. A different model, prompt, or problem could do better or
worse. The point isn't "LLMs are bad at this arithmetic" as a general
claim; it's that **you can't tell from a plausible-looking result alone**
whether it's correct — which is exactly why this project doesn't let the
LLM do the arithmetic in the first place.
