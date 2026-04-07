---
name: cloud-stocktake
description: >-
  Reconciles local cloud catalog, AWS billable resources (tag-filtered), and
  SSH config hosts for this project. Produces a structured findings report and
  suggests refinements to project rules and workflows. Use when the user asks
  for a cloud inventory, stocktake, cost audit, resource reconciliation, what
  is running, or whether cloud-resources.md matches reality.
---

# Cloud stocktake (agentic-cloud-task)

Cross-check three views of cloud footprint: **local catalog**, **provider API**
(tag-filtered), and **SSH client config**. This skill is **project-scoped** and
aligned with [AGENTS.md](../../../AGENTS.md) and [tools/AGENTS.md](../../../tools/AGENTS.md).

**Rule status:** Treat inventory policy and tag coverage as **under active
refinement**. After each stocktake, propose concrete extensions to
`AGENTS.md`, `.cursor/rules/`, `cloud-resources.example.md`, or tooling — do
not assume the current tag set or service list is complete.

## Preconditions

- Activate project **venv** before running boto3 or `tools/` scripts.
- Credentials load from **`.env`** (`AWS_ACCESS_KEY_ID_CLOUD`, etc.) via
  [`tools/_env.py`](../../../tools/_env.py).

## 1. Local catalog — `cloud-resources.md`

- If **`cloud-resources.md`** exists at repo root, read it (gitignored live
  inventory). If missing, note that and use
  [`cloud-resources.example.md`](../../../cloud-resources.example.md) only as
  **shape reference**, not as live data.
- Extract documented **nodes** (instance id, IP, status, WORKDIR, SSH host),
  **AMIs**, and **SSH** rows for comparison in step 4.

## 2. Provider enumeration — tag filter (billable focus)

Project tooling tags resources with **`Project` = `agentic-cloud-task`** and
**`Name`** (e.g. instance/volume/AMI name). See
[`tools/launch-spot-instance.py`](../../../tools/launch-spot-instance.py) and
[`tools/create-ami.py`](../../../tools/create-ami.py).

**Default filter:** resources tagged `Project=agentic-cloud-task` in the
account/region(s) you audit.

**How to enumerate (pick what fits the environment):**

- **Broad sweep:** AWS Resource Groups Tagging API
  (`get-resources`) with tag filter `Project=agentic-cloud-task` — surfaces
  many resource types in one call (instances, volumes, AMIs, snapshots, ENIs,
  security groups, etc., depending on support).
- **EC2 detail:** `describe-instances`, `describe-volumes`,
  `describe-images` (owners `self`), `describe-snapshots` (owners `self`),
  `describe-addresses` (Elastic IPs), as needed for fields the tagging API
  does not return (attachment state, delete-on-termination, public IPs).

**Scope notes:**

- Use **`AWS_DEFAULT_REGION`** from `.env` as the primary region; call out
  **other regions** explicitly if the account might run workloads elsewhere.
- Include **stopped** instances and **unattached** volumes when they still
  carry project tags or incur storage cost.
- If the user names a **different** tag or prefix (e.g. only `Name` =
  `cloud-task-*`), apply that filter **in addition to or instead of** the
  default and state which you used.

**Cost-relevant categories to aim for (extend if the project adds services):**

| Category | Why it matters |
|----------|----------------|
| EC2 instances (all non-terminated states) | Compute |
| EBS volumes | Storage; orphans after instance terminate |
| AMIs (owned by account) | Storage |
| Snapshots (owned by account) | Storage |
| Elastic IPs (allocated / associated) | Charge when idle |
| ENIs, security groups | Supporting; usually low cost but operational clutter |

## 3. SSH config — profiled hosts

- Read the user’s **OpenSSH client config** (typically `~/.ssh/config` on the
  workstation running the agent).
- List **Host** entries that match this project’s convention (e.g.
  `cloud-task-*` or aliases written by `launch-spot-instance.py` — see
  [`cloud-resources.example.md`](../../../cloud-resources.example.md) Nodes /
  SSH sections).
- Capture **HostName**, **User**, **IdentityFile** (if set), and **ProxyJump**
  for each relevant block — enough to spot stale IPs or missing entries.

## 4. Analysis and presentation

Deliver a single report to the user with:

1. **Executive summary** — one short paragraph: catalog vs API vs SSH agreement,
   and any obvious cost or operational risk (orphan volumes, old AMIs, stale
   SSH rows).
2. **Local catalog snapshot** — what `cloud-resources.md` claims (or “absent”).
3. **API snapshot** — tables or bullet groups by resource type: id, Name/Tag,
   state, region, monthly-relevant notes (e.g. volume GiB, attached instance).
4. **SSH snapshot** — matching Host blocks and whether HostName aligns with
   current public IPs from the API when comparable.
5. **Reconciliation** — explicit **matches**, **drifts** (catalog says X, API
   says Y), and **unknowns** (untagged resources that might still be project
   related — flag with low confidence).
6. **Suggested actions** — teardown candidates, catalog updates, SSH edits
   (non-destructive suggestions unless the user asked to clean up).

## 5. Rule and workflow refinements (required closing section)

End every stocktake with a short subsection **“Suggested rule / workflow
refinements”** aimed at the human maintainer. Examples of what to propose when
gaps appear:

- **Tags:** Additional mandatory tags (e.g. `Owner`, `CostCenter`), or tagging
  resources the tagging API did not return under `Project=agentic-cloud-task`.
- **Catalog policy:** When to update `cloud-resources.md` (see
  [AGENTS.md](../../../AGENTS.md)); new columns or tables for volumes/snapshots
  if drift keeps recurring.
- **Tooling:** A dedicated `tools/cloud-stocktake.py`, CI check, or documented
  `aws`/`boto3` one-liners in `tools/AGENTS.md`.
- **Cursor rules:** New or updated `.cursor/rules/` snippets so future agents
  always run a tag filter or reconcile SSH after launch/teardown.
- **Multi-region / multi-account:** If resources span regions or accounts,
  document how the stocktake should expand.

Phrase these as **concrete, optional** improvements — the skill does not change
project policy by itself.

## Implementation hints

- Prefer **executing** queries (AWS CLI or a small script using
  `from _env import ec2_client, AWS_DEFAULT_REGION, PROJECT_ROOT`) over
  guessing counts.
- Do **not** paste secrets or full `.env` contents into the report.
- If API access fails, report the error and still deliver catalog + SSH
  sections with a clear “API unavailable” caveat.
