# profiling/ — Agent Context

## What This Is

Accumulated cloud node provisioning cases. Each case directory contains
profiles, and may also contain scripts, configs, and other supporting
artifacts. Profiles follow the state convergence pattern; everything else
is referenced from a profile or from the case's AGENTS.md.

## Pattern

Profiles follow the **state convergence pattern** — a three-section mixed
agentic-imperative-declarative methodology (Target State / Apply / Audit).
See [policies/state-convergence-pattern.md](../policies/state-convergence-pattern.md)
for the full pattern definition. Load that policy before writing or reviewing
any profile.

## Case Structure

Each subdirectory is a provisioning case. `aws-deep-learning-base/` contains
common cloud node setup that other cases layer on top of.

| Directory | Domain |
|-----------|--------|
| [`aws-deep-learning-base/`](aws-deep-learning-base/AGENTS.md) | Common cloud node provisioning: AWS Deep Learning Base GPU AMI, SSH access, agent auth, rsync tooling |
| [`sara-wakeword/`](sara-wakeword/AGENTS.md) | OpenWakeWord model training (one-shot, AMI discarded after) |
| [`ocr-batch/`](ocr-batch/AGENTS.md) | Repeatable OCR batch processing (AMI retained for reuse) |

## Cloud-specific adaptation notes

- Cloud instances are ephemeral (launch → work → terminate).
- Profiles may split into an "AMI bake" phase (one-time golden image
  creation) and an "instance boot" phase (runs every launch).
- The self-accelerating property transfers: once SSH is up and the agent is
  connected, it can read profiles and drive the remaining provisioning.
