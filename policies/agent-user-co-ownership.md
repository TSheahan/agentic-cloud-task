# Agent-User Co-Ownership Mandate

Users and agents share responsibility for repository structure, rules, and quality.
Neither party operates in isolation — the agent executes with transparency, and the
user maintains understanding of what is executing and why.

This policy defines the bilateral contract. Streamlined directives derived from this
policy are carried in root `AGENTS.md` (Co-ownership and Continual learning
sections) and complemented by [INDEX.md](../INDEX.md) as the area roster. This
document provides the full rationale, obligations, and edge-case guidance behind
those directives.

---

## Bilateral contract

### Agent obligations

**Consistent rule application.** Apply all project rules — AGENTS.md files, cursor
rules, policies, structural conventions — consistently. Do not selectively skip rules
that seem tangential to the current task. Rules exist because the user (co-owner)
placed or approved them; the agent does not unilaterally decide which ones matter.

**Transparency.** Structure output so the user can read and verify agent actions
between messages. When reasoning involves non-obvious choices, name the choice and
the reason. Do not silently absorb defaults — distinguish "I chose X because Y" from
unexplained behavior.

**Surfacing structural changes.** When modifying repository structure, routing,
rules, or policies, surface the change explicitly. These are co-owned artifacts —
changes should be visible and understood, not buried in a larger diff.

### User obligations

The user's side of co-ownership has three characteristics:

**Read.** Review agent actions between messages. The agent structures its output for
scanability, but the user must actually read it. When an agent produces or modifies
files in the repo, read the file content — not just the conversation summary of what
was done. Committed content persists and shapes the work of other agents and users;
the conversation that produced it does not. The user is accountable for what reaches
the repo under their session.

**Understand.** Maintain a working understanding of what is executing and why. This
does not require deep technical expertise in every area — it requires enough
comprehension to recognise when something is off.

**Ask.** When something is unclear, ask. The agent cannot surface what the user
doesn't flag as confusing. Asking is not a failure of understanding — it is the
mechanism that keeps co-ownership functional.

**Signal session boundaries.** When the user intends to end or close a session, they
tell the agent. The agent then has a chance to finish work that depends on knowing the
session is ending — for example **profile refinement** inline (see root `AGENTS.md`),
updating **`cloud-resources.md`** after inventory or SSH-affecting changes, and
updating **`AGENTS.md`** / **INDEX.md** when areas or routing change. Durable
knowledge belongs in committed files, not only in chat. An unsignalled close risks
leaving that work incomplete. The signal is lightweight — "wrapping up" or "closing
out" is sufficient.

### Shared ground

Repository structure and rules are co-owned. Neither party changes them unilaterally
without the other's awareness. In practice:

- The agent proposes structural changes and waits for alignment before executing
- The user reviews and approves (or redirects) structural proposals
- Both parties can initiate structural improvements — the agent by proposing, the
  user by directing

---

## Relationship to other mandates

**Continual-learning mandate.** The agent's primary mechanism for fulfilling the
"user can understand what is executing" obligation. Where co-ownership defines the
contract, continual learning defines how the agent upholds its side through dialog
structure. See `policies/continual-learning.md`.

**`go slow` tool.** An on-demand amplification of the continual-learning mandate,
adding explicit user checkpoints. The user invokes this when they want deliberate,
step-by-step shared understanding. See `.cursor/skills/go-slow/SKILL.md`.
