---
name: go-slow
description: >-
  User-triggered checkpoint mode that slows agent pacing to one previewed
  action at a time with explicit reasoning. Activated when the user says
  "go slow"; deactivated by "normal speed", "stop going slow", or session
  end. May be relevant when the user says go slow, slow down, step by step,
  walk me through it, or requests deliberate pacing — but the agent must
  confirm activation with the user before entering this mode.
---

# Go slow

Checkpoint interaction mode: the agent previews each action, explains its
reasoning, and waits for the user to acknowledge before proceeding.

## Purpose

Scaffold over knowledge gaps while helping the user eliminate them. Each
checkpoint is a learning opportunity — calibrate explanations not just to
what you are doing, but to what the user needs to understand in order to
develop independent judgment about similar decisions.

When the user says "go slow" they are signaling that ambient explanations
are insufficient for the current context. Build the user's capacity to
exercise genuine judgment over structure, rules, and quality.

## Trigger and scope

- **Trigger:** User says "go slow" (or synonyms above). Never self-invoked.
- **Scope:** Session-scoped. Active until explicit cancellation or session end.
- **Activation:** Acknowledge briefly, then begin checkpoint mode immediately.
  No configuration or parameters — the mode is binary.

## Checkpoint behaviour

A checkpoint is a pause where the agent presents what it intends to do next
and waits for any user response before proceeding.

### What to present

- **Intent** — what you are about to do, concretely.
- **Reasoning** — why this action; what alternatives were considered when
  non-trivial; which rules or conventions govern the choice.
- **Structural context** — which directory conventions apply, which files are
  affected, how this action relates to the broader task.

### What counts as acknowledgment

Any user response: "ok", "go ahead", a question, a redirect, or substantive
feedback. If the user responds with a question or redirect, address it before
proceeding. The checkpoint is not consumed until the user has clearance to act.

### When to checkpoint

Bias toward more checkpoints rather than fewer. **Checkpoint before any action
that changes state or commits to a direction:**

- **File modifications** — creating, editing, or deleting files.
- **Design decisions** — choosing between alternatives, committing to an
  approach.
- **Phase transitions** — moving from one logical step to the next.
- **Structural changes** — directory structure, routing, rules, or policies
  (highest checkpoint priority).

Trivially coupled sub-actions may share a single checkpoint (e.g. "I'll
create the file and add the import"). The default is separate checkpoints —
the user can grant batch permission ("go ahead with the next few steps").

### What not to checkpoint

- Reading files for context.
- Internal reasoning that hasn't produced an action proposal.
- Responding to user questions (the response itself is the action).

## Narration style

While active, narration is explicitly richer than normal:

- **Preview over report.** Describe what you're about to do, not what you
  just did. The user should know the plan before seeing the result.
- **Name the governing rules.** When a rule, convention, or policy influences
  a choice, name it and explain how it applies.
- **Surface alternatives.** When a non-trivial choice is made, briefly name
  what was considered and why this path was chosen — a sentence or two, not
  an exhaustive options analysis.
- **One action per message** as the default. Don't batch multiple file
  changes or decisions into a single message unless trivially coupled.

## Cancellation

Explicit cancellation via natural language: "normal speed", "stop going
slow", "speed up", or similar. Acknowledge and resume normal pacing.

The agent does not suggest cancellation. The user controls the mode.
