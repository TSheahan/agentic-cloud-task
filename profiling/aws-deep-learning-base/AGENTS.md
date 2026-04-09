# profiling/aws-deep-learning-base/ — Common Cloud Node Setup

Base AMI profile for cloud tasks. Establish this before extending into
task-specific profiles (OCR, wake-word, etc.) — they layer on top.

## Scope

- **AMI selection**: start from AWS Deep Learning Base GPU AMI (Ubuntu,
  drivers + CUDA pre-installed).
- **SSH access**: instance reachable over SSH for agent connection and rsync.
- **Agent auth**: user cooperates to connect an agent to the cloud node.
- **rsync tooling**: rsync available for file transfer (inbound code/data,
  outbound results).
- **Instance lifecycle**: launch, provision, run task, terminate. AMI bake
  when the task profile calls for it.

## Contents

| File | Role |
|------|------|
| [base-gpu-node.profile.md](base-gpu-node.profile.md) | State convergence profile: Target State / Apply / Audit for a provisioned GPU instance |
| [cursor-rules/](cursor-rules/) | Staging mirror of `~/.cursor/rules/` (`.mdc` files). Cursor does not load rules from this path; copy into `~/.cursor/rules/` to activate. |
