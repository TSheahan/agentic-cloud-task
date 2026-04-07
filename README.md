# agentic-cloud-task

Agentic harness for task execution with cloud compute.

Scripting a cloud training task is error-prone — setup eats more time than
the actual GPU work. This project replaces brittle imperative scripts with
a mixed approach: declarative state descriptions, agentic natural-language
instructions, and direct shell snippets, all in a single profile document.
An agent reads the profile, converges the cloud node to the wanted state,
runs the task, and transfers results back.

## How it works

Each cloud task is defined as a **profile** following the
[state convergence pattern](policies/state-convergence-pattern.md):

- **Target State** — what the correctly configured system looks like
  (declarative, observable properties).
- **Apply** — happy-path steps to get there (shell commands + agentic
  instruction, mixed freely).
- **Audit** — commands that confirm the system matches the target.

The user authenticates an agent on the cloud node over SSH. The agent reads
the profile and drives provisioning, adapting when things don't match
expectations. File transfer uses rsync over SSH.

## Project layout

```
policies/               Reusable methodologies (state convergence, brain dump)
profiling/              Cloud node provisioning cases
  aws-deep-learning-base/   Common setup: AMI, SSH, agent auth, rsync
  sara-wakeword/            One-shot wake word model training
  ocr-batch/                Repeatable GPU-accelerated OCR
cloud/                  Config-as-code for AWS (IAM policies, launch config)
```

## Reference

- [ami-bake-considerations.md](ami-bake-considerations.md) — Custom AMI
  bake: golden image rationale, secrets, access control, rotation.

## Status

Early structure. Profiles are being written; no automation tooling yet.
Primary target is AWS (g4dn GPU instances); other platforms not ruled out.
