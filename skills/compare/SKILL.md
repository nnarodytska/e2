---
name: compare
description: Use when the user asks about differences between two or more metrics ('what's the difference between X and Y', 'compare', 'vs', 'versus', 'differ'). Produces a side-by-side comparison table plus key differences and gotchas.
---

### Skill: Compare Metrics

**When to activate:** Automatically when the user asks about differences between two or more metrics, asks "what's the difference between X and Y", or uses words like "compare", "vs", "versus", "differ", "distinction".

Produce a structured comparison:

1. **Comparison Table** with these rows:
   - Full name
   - Formula / How it's calculated
   - Unit
   - Available at (VM / vCPU / ESXi / Cluster)
   - What it measures (one line)
   - Includes HT penalty?
   - Includes CPU frequency (Turbo/power-saving) impact?
   - Capacity signal strength (Low / Medium / High — how well it signals resource exhaustion)
   - Threshold / When to worry
   - Best used for (Performance / Capacity / Throughput)

2. **Key Differences** — 2-3 bullet points on the most important distinctions, with the reasoning from the book

3. **When to use which** — practical guidance

4. **Common confusion** — gotchas the book calls out about these metrics

---

#### Built-in reference: ESXi CPU utilization metrics (Usage vs Core Utilization vs Thread Utilization)

This is the most common ESXi metric comparison. Activate this reference when the user compares any two or all three of these metrics, or asks which one is "correct" or "true".

| | **Usage (%)** | **Core Utilization (%)** | **Thread Utilization (%)** |
|---|---|---|---|
| What it measures | Cycles completed vs nominal frequency (NHCC counter) | Whether a core is active (100% if either thread runs) | Fraction of threads unhalted — binary per thread |
| HT penalty? | Yes — 62.5% per thread when both share a core | Partial — both threads = 100%, same as one thread | No — each thread counts independently as full 100% |
| Turbo / power-saving? | Yes — inflates above 100% with Turbo; deflates with power-saving | No | No |
| Capacity signal | **High** — saturates first; 100% = nominal budget exhausted | Medium — 100% = all cores active | **Low** — 50% can mean host is heavily loaded |
| Best used for | Knowing when nominal capacity is consumed; **capacity signal** | Physical core activity; planning HT contention risk | Granular physical thread counting; pair with Core Util |
| Sensitivity order | Highest — always ≥ Core Util ≥ Thread Util | Middle | Lowest |

**Key rule from the book:**
- *"If Core Utilization is not yet 100% or Thread Utilization is not yet 50%, there is still physical capacity available."*
- Usage = 100% (old cap) = no more nominal capacity. Usage > 100% (new) = Turbo in use, still running strong.
- For capacity questions: Usage is the "true utilization" signal. For physical analysis: use Core Util + Thread Util together.
