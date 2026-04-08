---
name: execute-convergence-profile
description: >-
  Execute a state convergence profile against a target system. Runs the
  Audit/Apply/Audit cycle with per-item todo tracking and a trailing
  refinement check. Use when the user wants to work with a profile that
  has a Target State section — including applying, executing, converging,
  picking up, setting up from, or verifying compliance with a convergence
  profile. Also use when the user references a profiling/ markdown file
  and the intent is to act on it rather than just read it.
---

# Execute a State Convergence Profile

Drive a system toward the state declared in a convergence profile. The
pattern is defined in
[policies/state-convergence-pattern.md](../../../policies/state-convergence-pattern.md) —
load that file at the start of execution for the full methodology.

Companion to [create-convergence-profile](../create-convergence-profile/SKILL.md),
which handles authoring. This skill handles runtime.

## Workflow

### 1. Load context

- Read the profile the user identified.
- Read the [state convergence pattern](../../../policies/state-convergence-pattern.md)
  if not already loaded.
- Skim the profile's Target State to understand scope before acting.

### 2. Build the todo list from Target State

Parse the profile's Target State section and create **one todo per item**.
Items are bold-prefixed bullets in Target State — see the item structure
convention in the
[convergence pattern policy](../../../policies/state-convergence-pattern.md).
Use a short slug id (e.g. `ts-python-venv`, `ts-keypair-aws`) and the item
text as the content.

After the per-item todos, add the workflow-phase todos:

```
 1. [pending] ts-python-available — Python 3.x on PATH
 2. [pending] ts-venv-exists — venv/ at project root
 3. [pending] ts-packages-installed — requirements.txt deps in venv
    ...one per Target State item...
 N. [pending] apply — close gaps found by audit
N+1. [pending] re-audit — confirm convergence
N+2. [pending] refinement-check — review execution for profile updates
```

The refinement-check todo **must** be present from the start — this is the
point of the skill. It stays even if everything else is trivial.

### 3. Audit first

Run every Audit check in the profile before touching anything.

**Mark each per-item todo** as it is audited:
- Check passes → mark **completed**
- Check fails → leave **pending** (will be addressed in Apply)
- No audit check exists for an item → mark **in_progress** with a note;
  improvise a check if possible, and flag the gap as a refinement candidate

This gives a concrete, visible tally of what's done vs. what remains.

If the profile has no Audit section at all (stub), note this as a refinement
candidate: the execution will generate audit checks to backfill.

### 4. Apply

Execute only the Apply steps needed to close gaps — the still-pending
per-item todos from step 3 tell you exactly which ones.

Mark each per-item todo **completed** as its corresponding Apply step
succeeds. Skip steps whose todos are already completed from audit.

During Apply, watch for:
- Steps that fail or need adaptation (→ refinement candidate)
- Assumptions in the profile that turn out wrong (→ refinement candidate)
- New constraints discovered at runtime (→ refinement candidate)

Don't stop to refine yet — finish the convergence loop first.

### 5. Re-audit

Run all Audit checks again. Every per-item todo should now be
**completed**. If any fail, diagnose and loop back to Apply for those items.

### 6. Refinement check

This is the step that justifies the skill. Mark the refinement todo as
in-progress and systematically review:

**Coverage gaps** — Compare the per-item todo list against the Audit
section. Any item that required an improvised check (marked in_progress
during step 3) is a missing audit check. Add it to the profile.

**Stale or wrong instructions** — Did any Apply step need adaptation at
runtime? Update the profile to match what actually worked. If a step was
speculative and the correct version depends on context that varies across
systems or runs, consider replacing it with a stub and rationale rather
than hardcoding what happened to work this time.

**New constraints** — Did the execution reveal facts not captured in Target
State? Fold them in.

**Confirmed assumptions** — Did anything marked tentative or with a
question get confirmed? Solidify it.

Write the refinements directly into the profile. Per project convention,
profile refinement is inline with the work, not trailing — but using the
todo to guarantee the review pass happens is the improvement this skill
provides.

### 7. Report

Summarize to the user:
- Audit scorecard (what passed, what was fixed)
- What Apply work was done
- What refinements were made to the profile and why
