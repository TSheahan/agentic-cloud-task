# agentic-cloud-task

This project supports easy dispatch and completion of cloud tasks.

## Motivation

Correctly scripting a cloud training task is error-prone. This project uses a
mixed imperative-command and agentic plain-language instruction approach: the
user cooperates to authenticate an agent on the cloud node, then the agent
assists with workflow execution.

## Design intentions

- File transfer to/from cloud nodes uses SSH + rsync.
- Primary development target is AWS; other cloud platforms are not ruled out.
- Cloud node provisioning follows the **state convergence pattern** defined
  in `policies/state-convergence-pattern.md`. Profiles are accumulated in
  `profiling/`.
- AWS configuration (IAM policies, etc.) is tracked as config-as-code in
  `cloud/` and applied with CLI tooling, not console actions.

## Navigation

**On session start:** Load this file for orientation. This is the single entry
point for understanding the project.

**Routing:** Consult [INDEX.md](INDEX.md) for the project area roster. Load the
target area's AGENTS.md for detail. Each step loads a single, bounded file — do
not browse the file tree; use the routing spine.

**Layered AGENTS.md routing:** Every directory that carries project-meaningful
content has an AGENTS.md. These form a spine: root → INDEX.md → area AGENTS.md
→ nested AGENTS.md. Agents navigate by following links down the spine, not by
listing directories or globbing for files.

**Co-committed updates:** When creating, moving, or removing files, update the
relevant AGENTS.md routing (and INDEX.md if a top-level area changes) in the
same commit.

## Naming conventions

- **Directories:** lowercase hyphenated slugs (`sara-wakeword`, `ocr-batch`)
- **Durable files:** descriptive names (`iam-policy-ec2-basic.json`,
  `account-structure.md`) — reference material that evolves but persists.
- **Temporal files:** `YYYY-MM-DD_slug.md` (`2026-04-07_training-run-log.md`)
  — time-bound observations, captures, logs.
- **Scratch:** `scratch/` is gitignored. Session-scoped working memory — never
  committed.

No active lifecycle management is required. The naming convention _is_ the
signal.

## Open questions

- Can agent auth be cloned from the user's local system instead of requiring
  manual cloud-side authentication?
