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

#### Item structure

Target State is an **enumeration of items**. An item is the atomic unit of
the profile — it is what gets audited, what gets tracked during execution,
and what an agent uses to answer "is this done?"

**Marker convention:** an item is a bold-prefixed bullet (`- **Claim...**`).
Everything else in Target State is structure or supporting detail:

- **H3 headings** within Target State are organizational groupers. They
  improve readability but are not items and do not affect the item count.
- **Sub-bullets and non-bold bullets** under an item are supporting detail
  (parameter values, reference data, config snippets). They elaborate the
  parent item but are not tracked separately.

Each item maps 1:1 to an Audit check: if an item has no corresponding Audit
check, that is a gap to fill. During execution each item also maps to one
tracking unit (e.g. a TODO), giving a concrete tally of convergence progress.

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

#### Relationship to items

Apply steps are not required to map 1:1 to Target State items. Apply
follows execution order, which is often many-to-many: one step may address
multiple items, and multiple steps may contribute to one item. Each Apply
step should make clear — via its heading or a brief note — which Target
State item(s) it addresses.

#### Atomicity and composition

An Apply step should be **atomic**: it does one thing that can succeed or
fail independently. If a step does two things that could fail independently
(e.g. create a security group *and* launch an instance), split it. Atomic
steps are easier to retry, easier to skip when already satisfied, and
easier for an agent to reason about during recovery.

When an action is **reusable across profiles** — "ensure a security group
exists", "launch a spot instance", "terminate tagged instances" — it should
be implemented as a shared tool in `tools/` and invoked from the profile's
Apply step. The profile supplies parameters; the tool supplies the
mechanism. This keeps profiles focused on *what* (declarative parameters,
agentic context) while `tools/` handles *how* (imperative implementation).
The profile should still describe the expected behavior so an agent can
understand the intent without reading the tool source.

**`tools/_env`** is the shared environment module. It loads `.env` on
import and exports project paths, AWS credential values, and ready-to-use
clients (e.g. `ec2_client`). Tools and ad-hoc snippets import from it
rather than loading credentials or constructing clients themselves. See
`tools/AGENTS.md` for the full inventory.

A complex Apply sequence (like "launch and provision a GPU instance")
decomposes into a chain of atomic steps, each backed by a shared tool or a
simple snippet. The profile expresses the sequence and the parameters; the
tools provide the atoms. New profiles compose existing tools rather than
reimplementing them.

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
- Cover every item in Target State — the 1:1 item-to-audit mapping defined
  above applies here. A missing audit check for an item is a profile gap —
  unless it is an explicit deferral with rationale (e.g. "check depends on
  runtime state the authoring agent cannot observe"). Intentional deferral
  is not a gap; it is a signal to the executing agent.
- When a check requires non-trivial logic that recurs across profiles
  (e.g. "confirm a running EC2 instance tagged X exists"), implement it as
  a shared tool in `tools/` with a `--check` or read-only mode, and invoke
  it from the Audit step. The same atomicity principle from Apply applies:
  one check, one item, independently runnable.

#### Check-to-item mapping

The 1:1 mapping between items and audit checks is structural:

- Each audit check corresponds to exactly one Target State item, and each
  item has exactly one audit check. This is a mapping rule, not a complexity
  constraint — a single check can be compound (multiple commands, sequential
  code blocks, multi-step verification) if the item requires it.
- Each check is introduced by a comment or heading that names the Target
  State item it verifies, making the mapping traceable.
- The boundary between checks is the item boundary. A profile with N items
  has N audit checks, regardless of how many code blocks each contains
  internally.

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

**Stub over speculation:** A stub or minimal derivation is often *preferable*
to a highly effortful one authored without runtime evidence. Speculative
Apply steps and Audit checks carry a hidden cost — they create false
confidence and noise that the executing agent must evaluate and possibly
discard. When the right answer depends on context only the executing agent
will have, say so explicitly and move on. An honest stub with rationale
("depends on CUDA version present at runtime") gives the executor better
signal than a guess.

## Compliance and convergence

Profiles should conform to the three-section structure wherever practical.
Agents should converge toward proper structure when editing profiles.

When state information is stale, incoherent, or needs review against the
target environment, it may be included with annotation to that effect.
Similarly, when a property or step is **indeterminate** — the correct value
depends on runtime context the authoring agent does not have — annotate the
indeterminacy and move on rather than guessing. Calling out what you don't
know is more useful than filling the gap speculatively.

Agents should refine such material into the three-section structure as they
are able to validate it against the real system.

