---
name: create-convergence-profile
description: >-
  Create a state convergence profile (Target State / Apply / Audit) for a
  system or subsystem. Use when the user wants to profile a system's wanted
  state, create a new provisioning profile, or capture how a system should
  be configured.
---

# Create a State Convergence Profile

Guide the user through creating a profile that declares a system's wanted
state. The pattern is defined in
[policies/state-convergence-pattern.md](../../../policies/state-convergence-pattern.md) —
read that file first for the full methodology. This skill focuses on the
creation workflow.

## Workflow

### 1. Gather starting material

Before asking questions, ask the user if they have existing material that
describes the system or the state the profile should produce — notes, docs,
conversation dumps, config files, scripts, READMEs, etc. Starting from
source material is faster and more accurate than interviewing from scratch.

If material is provided, extract and refine it into Target State properties.
Then confirm with the user and fill gaps. If no material exists, proceed to
elicitation.

### 2. Offer brain dump

If the user has substantial domain knowledge about the system — more than
a few notes, enough that structured Q&A would fragment their thinking —
offer a brain dump. See
[policies/brain-dump.md](../../../policies/brain-dump.md) for the full
dump-accumulate-recompose sequence.

In this context, the **capture objective** is always **Target State**: the
recompose phase should produce draft Target State properties (observable
facts about the correctly-configured system).

Skip this step if the user already provided source material that covers
the system adequately, or if the scope is narrow enough for direct
elicitation.

### 3. Identify the target

Establish what is being profiled:

- What system or subsystem? (e.g. "Python environment on GPU instance",
  "SSH access config", "OCR pipeline dependencies")
- Is this a new profile or extending an existing one?
- Where does it belong in the project tree? Check `profiling/AGENTS.md` for
  existing cases and the case table.

### 4. Draft Target State

This is the core of the skill. Target State is the only non-negotiable
section — a profile with only this is useful.

**Elicitation is adaptive:**

- **User has source material** — extract observable properties from it,
  draft Target State, then confirm with the user and fill gaps.
- **User knows the wanted state** — interview: ask structured questions
  about what properties the correctly-configured system exhibits. Work
  through one concern at a time.
- **System is accessible** — inspect: observe the current system state
  (SSH in, run commands, read configs) and present findings to the user
  for confirmation or correction.
- **Combination** — use whatever inputs are available. Source material
  first, inspection second, interview to fill gaps.

**Writing good Target State properties:**

- State facts, not actions. "Python 3.11 venv exists at `/opt/env`" —
  not "create a venv."
- Each property should be independently verifiable. If you can't imagine
  a command that checks it, it's too vague.
- Include version constraints where they matter for correctness.
- Group related properties under sub-headings when the profile covers
  multiple aspects of one concern.
- Ask: "If an agent read only this section, could it determine whether
  the system is correctly configured?" If not, a property is missing.

**Elicitation prompts that help surface properties:**

- "What packages / tools must be present?"
- "What config files must exist, and what must they contain?"
- "What services must be running / reachable?"
- "What should a smoke test look like?"
- "What's the most common way this breaks?"
- "What would you check first to confirm it's working?"

### 5. Stub Apply and Audit

Apply and Audit are accelerators — they may be left as stubs in a new
profile. If the user already knows the steps or checks, capture them. If
not, stub explicitly:

```markdown
## Apply

_To be filled in during first execution against the target system._

## Audit

_To be filled in during first execution against the target system._
```

Do not invent Apply steps or Audit checks that haven't been validated
against the real system. Unverified instructions are worse than a stub —
they create false confidence.

### 6. File and route

- Place the profile in the appropriate directory under `profiling/`.
- If a new case directory is needed, create it with an `AGENTS.md` hub.
- Update the parent `AGENTS.md` case table (co-committed update per
  project convention).
- Use a durable filename with the **`.profile.md`** extension
  (e.g. `base-gpu-node.profile.md`). This convention identifies
  convergence profiles regardless of directory location and triggers
  the profile refinement rule in root `AGENTS.md`.
