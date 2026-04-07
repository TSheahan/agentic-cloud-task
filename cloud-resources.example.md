# Cloud Resources Catalog (committed template)

**This file is tracked in git.** It shows **layout only**: table shape, column
meanings, and **fabricated** example cells (fake instance IDs, documentation-block
IPs, illustrative host names). Do **not** replace those fabrications with real
nodes, AMIs, public IPs, or live SSH status here — that belongs only in
gitignored **`cloud-resources.md`**.

Copy this file to `cloud-resources.md`, then edit the private copy as resources
are created or destroyed.

**Policy:** live **nodes** (instance id, IP, status, **WORKDIR**, SSH rows) and **AMIs** belong
in `cloud-resources.md`, not in committed profiles — see
[`profiling/AGENTS.md`](profiling/AGENTS.md).

**After copy:** replace every placeholder row in your private file with real
values. **Keep in sync with reality:** when you launch or tear down a node, update
**Nodes** and **SSH (current)** in `cloud-resources.md` so listed commands stay
usable.

---

## Nodes

EC2 instances. The **Name** tag follows `cloud-task-<slug>` from the
[base GPU node profile](profiling/aws-deep-learning-base/base-gpu-node.profile.md).
Unless you pass `--ssh-host-alias`, `tools/launch-spot-instance.py` writes
`~/.ssh/config` **Host** with the same string as **Name**.

**WORKDIR** is the primary project checkout on the node (where agents and humans
run commands, and the usual `rsync` / `scp` target). Use the path you actually use
(e.g. `~/agentic-cloud-task`).

Track the **current base / task instance** in your private `cloud-resources.md`
(one row per live or recent node you care about). Rows below are **not** real
inventory.

| Name | SSH Host | Instance ID | Public IP | Region | Type | Status | WORKDIR | Notes |
|------|----------|-------------|-----------|--------|------|--------|---------|-------|
| `cloud-task-example-a` | `cloud-task-example-a` | `i-0123456789abcdef0` | `203.0.113.10` | ap-southeast-2 | g4dn.xlarge | fictional | `~/agentic-cloud-task` | TEST-NET-3 IP; not a real instance |
| `cloud-task-example-b` | `cloud-task-example-b` | `i-0fedcba9876543210` | — | ap-southeast-2 | g4dn.xlarge | fictional | `~/agentic-cloud-task` | not a real instance |

## AMIs

Custom and reference images used by this project. Use the **Notes** column
for stable logical names (`raw-dl-base-gpu`, `baked-core-gpu`, etc.) so
profiles and tools can refer to roles without embedding IDs in git.

| AMI ID | Region | Based On | Created | Status | Notes |
|--------|--------|----------|---------|--------|-------|
| `ami-0aaaaaaaaaaaaaaaa` | ap-southeast-2 | — | — | available | `raw-dl-base-gpu` — public AWS Deep Learning Base GPU; resolve ID in EC2 / AWS docs |
| `ami-0bbbbbbbbbbbbbbbb` | ap-southeast-2 | raw DL Base | 2026-04-08 | available | `baked-core-gpu` — golden base after Apply §2–4 + purge (Apply §5) |
| `ami-0cccccccccccccccc` | ap-southeast-2 | raw DL Base | 2026-04-07 | deregistered | example: prior bake deregistered (e.g. secrets in image) |

## SSH (current)

Commands below assume the `cloud-task-*` wildcard block from the
[local dev workstation profile](profiling/local-dev-env/dev-workstation.profile.md)
(`User ubuntu`, `IdentityFile` → project `.keys/cloud-task.pem`, etc.).

**Only rows for instances that are `running` and still have a matching
`Host` entry in `~/.ssh/config` are usable.** After `teardown-instance.py`,
remove or strike the row until you launch again.

| SSH host | Status | Usable commands |
|----------|--------|-----------------|
| `cloud-task-example-a` | fictional (template) | `ssh cloud-task-example-a` — interactive shell |
| | | `ssh cloud-task-example-a 'command'` — remote command |
| | | `scp ./local.file cloud-task-example-a:` — copy up to home dir |
| | | `scp cloud-task-example-a:~/remote.file ./` — copy down |
| | | `rsync -e ssh -av ./src/ cloud-task-example-a:~/agentic-cloud-task/src/` — tree sync |

When nothing is running:

| SSH host | Status | Notes |
|----------|--------|-------|
| — | no active hosts | Launch with `tools/launch-spot-instance.py`, then add a row above with the printed `public_ip` and `instance_id`. |
