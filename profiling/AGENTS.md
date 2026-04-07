# profiling/ — Agent Context

## What This Is

Accumulated provisioning profiles — local dev environment, cloud node
setup, and task-specific cases. Each case directory contains profiles,
and may also contain scripts, configs, and other supporting artifacts.
Profiles follow the state convergence pattern; everything else is
referenced from a profile or from the case's AGENTS.md.

## Pattern

Profiles follow the **state convergence pattern** — a three-section mixed
agentic-imperative-declarative methodology (Target State / Apply / Audit).
See [policies/state-convergence-pattern.md](../policies/state-convergence-pattern.md)
for the full pattern definition. Load that policy before writing or reviewing
any profile.

## Case Structure

Each subdirectory is a provisioning case. Dependency order:
`local-dev-env` → `aws-deep-learning-base` → task-specific cases.

| Directory | Domain |
|-----------|--------|
| [`local-dev-env/`](local-dev-env/AGENTS.md) | Developer workstation: project venv, AWS CLI, credentials, SSH keypair and config |
| [`aws-deep-learning-base/`](aws-deep-learning-base/AGENTS.md) | Common cloud node provisioning: AWS Deep Learning Base GPU AMI, SSH access, agent auth, rsync tooling |
| [`headless-auth/`](headless-auth/AGENTS.md) | Cooperative agent-user auth for headless nodes: Cursor agent OAuth, GitHub CLI device flow |
| [`sara-wakeword/`](sara-wakeword/AGENTS.md) | OpenWakeWord model training (one-shot, AMI discarded after) |
| [`ocr-batch/`](ocr-batch/AGENTS.md) | Repeatable OCR batch processing (AMI retained for reuse) |

## Cloud-specific adaptation notes

- **AMI and node inventory do not belong in committed profiles.** Treat AMIs,
  instance IDs, public IPs, and live node/SSH status as local operational data:
  record them only in the gitignored root file
  [`cloud-resources.md`](../cloud-resources.md). The committed file
  [`cloud-resources.example.md`](../cloud-resources.example.md) is the **template**
  (structure + **fabricated** table rows); keep it free of real account inventory in
  git. The filled `cloud-resources.md` tracks **running base/task instances** (Name
  tag, instance id, public IP, status, **WORKDIR**) and a **current SSH quick reference** (`ssh`
  / `scp` / `rsync` using each `Host` alias). Profiles should describe *how* to
  choose or bake an image (raw DL AMI, naming convention, purge-before-bake) and
  point to `cloud-resources.md` for live IDs and access commands.
- Cloud instances are ephemeral (launch → work → terminate).
- Profiles may split into an "AMI bake" phase (one-time golden image
  creation) and an "instance boot" phase (runs every launch).
- The self-accelerating property transfers: once SSH is up and the agent is
  connected, it can read profiles and drive the remaining provisioning.
