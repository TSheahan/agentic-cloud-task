---
name: develop-convergence-profile
description: >-
  Interactive, checkpoint-based authoring of state convergence profiles:
  grow Target State turn-by-turn, back-fill items from agreed atomic advances,
  extend an existing profile or scaffold a new one from the pattern layout.
  Use when the user wants to iteratively develop, co-author, or refine a
  profile with conversational elicitation; when building wanted state before
  Apply/Audit are known; or when pairing profile design with execution feedback.
---

# Develop a Convergence Profile (Interactive)

Companion to [create-convergence-profile](../create-convergence-profile/SKILL.md)
(one-shot / material-driven authoring) and
[execute-convergence-profile](../execute-convergence-profile/SKILL.md)
(Audit/Apply execution). This skill covers **iterative, user-in-the-loop**
development: the profile grows in **checkpoints** while **Target State items**
are **back-filled** as each atomic slice of wanted state becomes clear.

Load [policies/state-convergence-pattern.md](../../../policies/state-convergence-pattern.md)
for item structure, section roles, and stub-vs-speculation rules.

## When to use this skill

- The user wants to **develop** or **refine** a profile over multiple turns,
  not dump everything in one pass.
- Wanted state is still emerging; **Apply** and **Audit** may stay stubbed
  until execution or a later pass.
- The user references an **existing** profile to extend, or asks for a **new**
  profile without a fixed path yet.

## Entry: existing vs new profile

**User references a profile path** — read it, treat it as the working document,
and continue from current Target State. Confirm scope (whole profile vs one
section) if ambiguous.

**User wants a new profile** — run **path elicitation** before writing files:

1. **System / case** — what subsystem or provisioning case? (one sentence)
2. **Location** — which directory under `profiling/`? Follow existing
   [profiling/AGENTS.md](../../../profiling/AGENTS.md) cases; if new case,
   agree on a **lowercase-hyphenated** directory name and that a case
   `AGENTS.md` + parent case table update will be co-committed when the file
   is added (per root `AGENTS.md` routing rules).
3. **Filename** — `*.profile.md` (e.g. `my-subsystem.profile.md`).
4. **Title** — H1 matches the pattern: `# {Name} — State Convergence Profile`.

Do not create the file until path and name are agreed (or the user explicitly
asks the agent to choose defaults).

## Preferred skeleton (consistency)

Derive the file from this layout — it matches existing profiles (e.g.
`headless-auth`, `ocr-batch`, `container`): title, context paragraphs,
pattern link, horizontal rules between major sections, optional **H3 groupers**
inside Target State only.

**Replace `{…}` placeholders. Adjust the pattern link depth** (`../` vs
`../../` vs `../../../`) from the profile file to `policies/state-convergence-pattern.md`.

```markdown
# {Title} — State Convergence Profile

{1–3 sentences: what this profile governs, primary runtime or machine.}

{Optional: prerequisite/layer profiles — linked. Reference AGENTS.md or hub
docs when helpful.}

Follows the [state convergence pattern]({relative}/policies/state-convergence-pattern.md).

---

## Target State

### {Optional H3 grouper — not an item}

- **{Bold item — one auditable claim.}** Supporting detail in sub-bullets,
  code fences, or tables. Not separate tracked items.

---

## Apply

_To be filled when steps are validated, or stub with one line per pattern policy._

---

## Audit

_To be filled when checks are validated, or stub with one line per pattern policy._
```

**Minimum viable new file:** Target State can start with one item plus stubs
for Apply/Audit. **Appendices** (reference matrices, optional fragments) are
optional — add when a mature profile needs them; see `ocr-batch.profile.md`.

## Checkpoint workflow (core loop)

Work in **turns**. Each turn advances understanding; **checkpoints** persist
progress into the markdown file.

### 1. Explore wanted state (turn-based)

- Ask **one focused question** or propose **one draft slice** of behavior —
  avoid long questionnaires in a single message unless the user prefers a
  batch brain dump (then consider
  [brain-dump policy](../../../policies/brain-dump.md) via create-convergence-profile).
- Prefer **observable facts** (what a correct system exhibits), not actions,
  per the convergence pattern.

### 2. Detect an atomic advance

When the conversation nails **one independently verifiable claim** (one future
audit unit), that is a **Target State item** candidate — one **bold bullet**
`- **...**`.

### 3. Balance: next question vs lock item

- If the slice is **not** ready — continue exploration (refine constraints,
  versions, paths, failure modes).
- If the slice **is** ready — **pause for deposit**: either
  - **User deposits** — user supplies wording, pastes bullets, or says “add what
    we just agreed”; or
  - **Agent drafts** — propose a single `- **...**` line (and optional
    sub-bullets); user confirms or edits.

**Rule of thumb:** do not accumulate five items in chat without offering to
write at least one into the profile once the first item is stable.

### 4. Back-fill Target State

- Insert the new item under the right **H3** (create a grouper if it helps
  readability; H3s are not items).
- Keep **one item = one bold bullet**; supporting detail stays non-bold under
  that bullet.
- After substantive edits, remind that [execute-convergence-profile](../execute-convergence-profile/SKILL.md)
  maps each item to an Audit check when the user is ready to execute.

### 5. Apply / Audit (later passes)

- Leave **stub** sections honest (`_To be filled…_`) until validated on a real
  system — same rule as create-convergence-profile.
- When execution yields commands or checks, fold them in during the same
  session when possible (profile refinement inline with work).

### 6. Checkpoint close

End a development session with a short summary: **items added or changed**,
**open questions**, **next checkpoint focus** (e.g. “next: network ports”).

## Relationship to other skills

| Skill | Role |
|-------|------|
| [create-convergence-profile](../create-convergence-profile/SKILL.md) | Brain dump, material-first draft, initial file/route |
| **develop-convergence-profile** (this) | Iterative Target State growth, checkpoints |
| [execute-convergence-profile](../execute-convergence-profile/SKILL.md) | Audit/Apply/re-audit against live system |

Use **develop** when the user is co-designing wanted state over multiple
messages; use **create** when source material or a single structured pass is
enough; use **execute** when converging a host to an existing profile.
