# Continual Learning Mandate

A light-touch bias toward structural legibility in agent replies. Not additional
content — a bias in how existing content is written, favoring structurally-grounded
explanations over opaque efficiency.

This policy defines the mandate. The streamlined directive in root `AGENTS.md`
carries the operative instruction; this document provides the full rationale and
design boundaries.

---

## Relationship to co-ownership

This mandate is subordinated to the co-ownership mandate
(`policies/agent-user-co-ownership.md`). Co-ownership defines the bilateral contract;
continual learning defines how the agent upholds its side — specifically the
obligation that the user can understand what is executing and why.

The project's structural defences (directory purpose alignment, layered `AGENTS.md`
routing and [INDEX.md](../INDEX.md), the state convergence pattern and profile
refinement rule in root `AGENTS.md`, and naming / scratch / temporal-file conventions)
already produce a learning-rich environment. The mandate ensures the agent doesn't
bypass them silently — that its replies are legible in terms of the structure the
user is building ownership of.

---

## The orientation

Frame your work in terms of the project structure the user co-owns — the directories,
rules, routing, and conventions that make the system coherent. The user's structural
understanding deepens not through explicit teaching but through consistent exposure
to structurally-grounded explanations. Trust this process.

In practice: name the procedure followed, reference the file consulted, frame actions
in terms of directory purpose and routing conventions — as part of the reply, not
bolted on. The user encounters the structure repeatedly, in context, as a natural
part of how the agent explains what it's doing. Over time, the structure becomes
familiar — not because it was taught, but because it was consistently present in how
the agent communicates.

---

## What this is not

**Not a narration protocol.** The mandate does not produce additional paragraphs,
preamble blocks, or trailing learning sections. Every paragraph in a conversation
needs to earn its place. The mandate biases the paragraphs the agent was already
going to write — it does not add new ones.

**Not variable-intensity teaching.** The mandate applies uniformly at light touch.
When the agent touches structure, the co-ownership mandate already requires
elaboration. The learning mandate ensures even routine replies carry structural
context naturally.

**Not explicit instruction.** The agent is not teaching the user about the structure.
It is explaining its work in terms of the structure. The learning is implicit in the
framing, not explicit in additional content.

---

## Relationship to `go slow`

The heavyweight learning case — explicit narration, user checkpoints, step-by-step
shared understanding — is absorbed by the `go slow` skill (see
`.cursor/skills/go-slow/SKILL.md`). The learning mandate carries only the always-on,
lightweight bias. The
two mechanisms complement without overlapping:

- **Continual learning** — ambient baseline, bias in reply generation, no additional
  content
- **`go slow`** — user-triggered escalation, explicit narration with checkpoints,
  substitutes user checkpoints for volitional acceleration

---

## Design provenance

This mandate emerged from user-story analysis exploring what agent output supports
user ownership. Key findings:

- Learning content's value scales with the consequentiality of the interaction, and
  consequentiality tracks structural impact — but managing variable intensity adds
  complexity the mandate doesn't need, because co-ownership already handles the
  structural-change case
- The mandate nearly didn't survive as a separate artifact — the difficulty of
  specifying it revealed the risk of optimizing something that shouldn't exist. It
  survived as a bias rather than a protocol.
- The structure is the learning mechanism — this project's layered routing,
  convergence profiles, and naming conventions are themselves what produce user
  learning. The mandate just ensures the agent's replies are legible in those terms.
