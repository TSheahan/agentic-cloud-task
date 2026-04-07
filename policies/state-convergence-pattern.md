# State Convergence Pattern

A reusable methodology for ensuring a system converges to a specified state.
Agent-first: designed for an agent executor that can read intent, exercise
judgment, and recover from surprises — not just run commands in sequence.

Each profile mixes three modes in a single document:
- **Declarations** of wanted state
- **Agentic instructions** (natural language aimed at an agent)
- **Direct snippets** (shell commands, config fragments)

This is more robust than a classic imperative script because it gives the
executor the information needed to diagnose, adapt, and recover — not just
the happy path.

## The three sections

### Target State (declarative)

A description of what a correctly provisioned system looks like. Written as
observable properties: package installed at version X, config file present at
path Y, service responding on port Z, command returns expected output.

Target State serves multiple roles:

- **Completion test** — an agent reads this section and determines "am I
  already done?" without executing anything.
- **Contract** — if the target state holds, the system is correctly
  provisioned regardless of how it got there.
- **Backstop** — when Apply instructions are wrong, Audit checks fail, the
  system is partially profiled, or something unexpected happens, Target State
  gives the agent the information it needs to recover. The declaration of
  *what should be true* survives errors in *how to get there*.

Guidelines:
- State facts, not actions. "Python 3.11 venv exists at `/opt/env`" not
  "create a venv."
- Each property should be independently verifiable.
- Include version constraints where they matter.

### Apply (imperative + agentic)

The happy path: steps to reach the target state from a clean baseline. This
section provides shortcuts and repeatability — when things go as expected,
follow these steps and you're done.

Apply mixes two kinds of instruction:

**Direct snippets** — shell commands, copy-pasteable, with prerequisites
stated up front. Each step should be idempotent where possible (re-running
on an already-provisioned system is a no-op, not a breakage).

**Agentic instruction** — natural-language direction aimed at an agent
executor. Use this when the right action depends on context the agent can
observe at runtime, when judgment is needed, or when a plain-language
description is clearer than a brittle script. Examples:

- "If the base AMI already includes CUDA 12.x, skip this step."
- "Install the PyTorch version compatible with the CUDA version present."
- "Verify network connectivity before proceeding; diagnose and fix if
  unreachable."

The mix is the point. Deterministic steps get shell commands. Steps that
benefit from judgment get natural language. The boundary is practical, not
dogmatic — use whichever mode communicates the intent most clearly and
executes most reliably.

### Audit (observable)

Commands that confirm the target state was reached. Each audit step includes
the expected output. An agent can run these non-destructively at any time to
check current state against the profile.

Audit provides repeatability: run it after Apply to confirm success, run it
later to detect drift, run it on a system you didn't build to assess its
state.

Guidelines:
- Audit commands must be safe to re-run (read-only, no side effects).
- Include the expected output literally so automated comparison is possible.
- Cover every property in the Target State section.

## How the sections interact

**Happy path:** Apply gets you to Target State; Audit confirms you're there.

**Unhappy path:** When Apply fails, Audit fails, or the system was left in
an unexpected state, the agent falls back to Target State. The declaration of
wanted state is always available as ground truth — the agent can reason about
the gap between current state and target state and work toward convergence
even when the scripted path doesn't apply.

## Separation of concerns

Each profile file owns the wanted state of a system or subsystem. Profiles
are consumed by reference — linked from hub documents, other profiles, or
task definitions that need them.

## Minimum viable profile

Target State is the only non-negotiable section. A profile with only Target
State is useful — an agent can reason from the declared wanted state to
figure out how to get there and how to check it.

Apply and Audit are accelerators. They may be stubbed or omitted in a new
profile and filled in during or after first agentic execution against the
real system. The agent that actually runs the convergence is best positioned
to capture the working steps (Apply) and the checks that confirmed success
(Audit).

## Compliance and convergence

Profiles should conform to the three-section structure wherever practical.
Agents should converge toward proper structure when editing profiles.

When state information is stale, incoherent, or needs review against the
target environment, it may be included with annotation to that effect.
Agents should refine such material into the three-section structure as they
are able to validate it against the real system.

