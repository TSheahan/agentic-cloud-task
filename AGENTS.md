# agentic-cloud-task

This project supports easy dispatch and completion of cloud tasks.

## Motivation

Correctly scripting a cloud training task is error-prone. This project uses a
mixed imperative-command and agentic plain-language instruction approach: the
user cooperates to authenticate an agent on the cloud node, then the agent
assists with workflow execution.

## Local runtime

- **Project venv** at `venv/` (Python, boto3, paramiko, etc.). Activate
  before running any `tools/` script or boto3 snippet.
- **AWS credentials** in `.env` at project root (`AWS_ACCESS_KEY_ID_CLOUD`,
  `AWS_SECRET_ACCESS_KEY_CLOUD`, `AWS_DEFAULT_REGION`). Loaded
  automatically by tools via `python-dotenv`.
- Full setup details:
  [local dev workstation profile](profiling/local-dev-env/dev-workstation.profile.md).

## Cloud resources catalog

Two files at the repo root; roles are inverted on purpose:

- **Committed template (unfilled):** [cloud-resources.example.md](cloud-resources.example.md)
  — checked in, git-tracked. Keeps **layout and placeholder values only** (fictional
  **node** rows, instance IDs, IPs, AMI IDs, SSH examples). Do **not** paste real
  inventory here; that would leak operational data into git.

- **Local catalog (filled):** **`cloud-resources.md`** — **gitignored**. Copy from
  the example when missing, then maintain it with **real** AMIs, nodes, and current
  SSH lines. Clones do not ship this file until someone creates it (do not invent a
  parallel location).

**What it is for:** Operational source of truth for this repo’s AWS
inventory — AMIs, **active base/task nodes** (instance id, public IP,
status, **WORKDIR**), and **current usable** `ssh` / `scp` / `rsync` lines. Committed
profiles do **not** carry AMI or instance identifiers; resolve them here.

**Agent maintenance (non-optional):** After any workflow that changes that
inventory or which `Host` entries are valid — e.g. `tools/launch-spot-instance.py`,
`tools/teardown-instance.py`, `tools/create-ami.py`, manual EC2/AMI changes,
or edits to `~/.ssh/config` for `cloud-task-*` — update `cloud-resources.md`
**in the same session** (Nodes table including **WORKDIR**, AMIs table, SSH section) so the next
agent or human does not rely on stale IDs or dead SSH commands.

## Design intentions

- File transfer to/from cloud nodes uses SSH + rsync.
- Primary development target is AWS; other cloud platforms are not ruled out.
- Cloud node provisioning follows the **state convergence pattern** defined
  in `policies/state-convergence-pattern.md`. Profiles are accumulated in
  `profiling/`.
- AWS configuration (IAM policies, etc.) is tracked as config-as-code in
  `cloud/` and applied with CLI tooling, not console actions.
- Live AMI/instance access commands: **`cloud-resources.md`** (see section
  above); not duplicated in committed profiles.

## Profile refinement rule

When an agent reads or edits any `*.profile.md` file, it should load the
[state convergence pattern](policies/state-convergence-pattern.md) if it
hasn't already. Profile refinement is **inline with the work, not trailing.**
When a step reveals a new constraint, corrects a wrong assumption, or
confirms an expected state, fold that into the profile as part of the same
action — don't defer it to a cleanup pass. The profile is the living record;
session logs and ad-hoc notes are overflow, not primary.

## Navigation

**On session start:** Load this file for orientation. This is the single entry
point for understanding the project. If work may touch EC2, AMIs, or SSH to
`cloud-task-*` hosts, read **`cloud-resources.md`** when it exists (see
[Cloud resources catalog](#cloud-resources-catalog)); do not assume AMI IDs
or live instance details from profiles alone.

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
- **Profiles:** `*.profile.md` (`base-gpu-node.profile.md`,
  `dev-workstation.profile.md`) — state convergence profiles following the
  three-section pattern. The `.profile.md` suffix is the machine-readable
  marker; it triggers the profile refinement rule above regardless of
  where the file lives.
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
