# CLAUDE.md — Project Agentic Memory Map

This file is the entry point for Claude Code. It maps every `AGENTS.md` file
in the project, explains what each one contains, and specifies when to read it.

The project uses a layered AGENTS.md spine: root → area AGENTS.md → nested
AGENTS.md. Navigate by following links down the spine; do not browse the file
tree or glob for files.

---

## AGENTS.md Index

### `AGENTS.md` (root)

**Contains:** Project overview and orientation — motivation, local runtime
(venv, AWS credentials, `.env` keys, orchestrator role), the dual
`cloud-resources.md` / `cloud-resources.example.md` catalog pattern, design
intentions (SSH + rsync, state convergence, config-as-code), profile
refinement rule, naming conventions, and the layered routing contract.

**Read when:** Starting any session. This is the single entry point. If work
may touch EC2, AMIs, or SSH to `cloud-task-*` hosts, also read
`cloud-resources.md` immediately after.

---

### `tools/AGENTS.md`

**Contains:** Inventory of every reusable operational script in `tools/`:
`_env.py` (shared boto3/credential helper), `launch-spot-instance.py`,
`teardown-instance.py`, `create-ami.py`, `ensure-ecr-ocr-repo.py`,
`provision-ocr-batch.py`, `submit-ocr-batch-job.py`. Documents the two-layer
AWS principal model (IAM user vs orchestrator role), when to use each, and how
`resolved_assume_role_arn` works.

**Read when:** Running, debugging, or writing any `tools/` script; building
boto3 snippets; needing to understand which AWS principal to use for an
operation.

---

### `cloud/AGENTS.md`

**Contains:** Config-as-code inventory for AWS: `iam-policy-ec2-basic.json`,
`cf-cloud-permission-roles.yaml` (orchestrator role, EC2 instance profile,
managed policies, workstation EC2 lifecycle group), `cf-batch-ocr.yaml` (OCR
Batch security group, service/task/job roles). Explains the
Batch-vs-permissions stack split, resource tagging contract
(`Project=agentic-cloud-task`), IAM lifecycle-phase coverage table, and the
CloudFormation deploy command.

**Read when:** Deploying or updating IAM / CloudFormation stacks; diagnosing
permission errors; understanding which stack owns which roles or policies.

---

### `policies/AGENTS.md`

**Contains:** Directory-level index of reusable methodology files:
`state-convergence-pattern.md` (Target State / Apply / Audit pattern),
`brain-dump.md` (knowledge transfer sequence), `agent-user-co-ownership.md`
(bilateral agent–user contract), `continual-learning.md` (structurally legible
reply bias). Includes scope and "read when" guidance for each.

**Read when:** Starting work that intersects any of the four policies, or when
unsure which policy applies to a situation.

---

### `profiling/AGENTS.md`

**Contains:** Top-level index of provisioning cases with dependency order
(`local-dev-env` → `aws-deep-learning-base` → task-specific cases), the state
convergence pattern reminder, and notes on AMI/instance inventory separation
(committed profiles must not carry live IDs — those live only in
`cloud-resources.md`).

**Read when:** Starting any cloud provisioning task; navigating to a specific
case; understanding the dependency chain between profiles.

---

### `profiling/local-dev-env/AGENTS.md`

**Contains:** Index for the developer workstation provisioning case:
`dev-workstation.profile.md` (project venv, AWS credentials, SSH keypair and
config) and `setup-aws-keypair.py` (generate + import keypair, print SSH config
block).

**Read when:** Setting up or repairing the local development environment;
bootstrapping AWS credentials or SSH keys; this is the first dependency in the
provisioning chain.

---

### `profiling/aws-deep-learning-base/AGENTS.md`

**Contains:** Index for the common cloud node base setup: scope (AMI
selection, SSH access, agent auth, rsync tooling, instance lifecycle),
`base-gpu-node.profile.md` (Target State / Apply / Audit for a provisioned GPU
instance), and the `cursor-rules/` staging mirror.

**Read when:** Provisioning any cloud GPU instance; before loading a
task-specific profile (OCR, wake-word) since they layer on this base; when
troubleshooting SSH or agent connectivity on a cloud node.

---

### `profiling/headless-auth/AGENTS.md`

**Contains:** Index for cooperative agent-user authentication on headless
nodes. Covers Cursor agent OAuth (device-code login via `agent login`) and
GitHub CLI device flow (`gh auth login -w`). Contains
`headless-auth.profile.md` (Target State / Apply / Audit).

**Read when:** Authenticating a Cursor agent or GitHub CLI on a remote
headless cloud node; when the device-code OAuth flow is needed.

---

### `profiling/ocr-batch/AGENTS.md`

**Contains:** Full index for the repeatable OCR batch task: characteristics
(g4dn, AMI retention, spot vs on-demand), three profile files
(`ocr-batch.profile.md`, `container-image.profile.md`,
`batch-worker-plane.profile.md`), utility scripts (smoke tests, spacing tools),
session history and increment closeout logs, and the user's design brief for
the cloud OCR appliance.

**Read when:** Working on any part of the OCR batch pipeline — container image
build, AWS Batch provisioning, job submission, benchmarking, or post-processing.

---

### `profiling/ocr-batch/container/AGENTS.md`

**Contains:** Index for the Docker build context: `Dockerfile` (CUDA/cuDNN8
base, Paddle install, symlinks, model bake), `requirements.txt`,
`bake-models.py` (build-time model downloader), `processor.py` (S3/local batch
processor), `run-local-smoke.sh`, `poke-smoke-test.py`, and two historical
notes (pre-profile brain dump, container dev handoff).

**Read when:** Building, debugging, or modifying the OCR container image;
running local smoke tests; tracing the Paddle model path workaround.

---

### `profiling/ocr-batch/dev-benchmark/AGENTS.md`

**Contains:** Index for ad-hoc Docling + RapidOCR timing drivers (`r1-onnx.py`
through `r7-paddle-tuned.py`), `ocr_spacing_fix.py` (post-export spacing hook),
`ocr-spacing-assess.py` (heuristic comparison tool), and run instructions for
executing benchmarks on an instance.

**Read when:** Running or extending OCR benchmarks; investigating spacing
quality; looking up the canonical baseline (`r2-torch.py`).

---

### `profiling/sara-wakeword/AGENTS.md`

**Contains:** Index for the "hey Sara" OpenWakeWord training case:
characteristics (g4dn, ~2–4 h runtime, stop-not-terminate lifecycle), profiles
(`oww-training-env.profile.md`), reference files (`domain-knowledge.md`,
`hey_sara_model.yml`), sample generation scripts (`generate_samples.py`,
`smoke_test_model.py`), and pointers to the upgrade story and deprecated
Hudson's Bay subdirectories.

**Read when:** Provisioning or running the wake-word training environment;
generating training samples; validating a trained OWW model.

---

### `profiling/sara-wakeword/upgrade_story/AGENTS.md`

**Contains:** Research trail from the 2026-04-08 methodology refinement
session: `current-methodology.md` (pre-refinement baseline),
`target-state-draft.md`, the 14-item mutation table, session provenance, two
project-agent reviews of Grok responses, and the Grok dialog prompts/responses.
The refined methodology is already integrated into `oww-training-env.profile.md`
— this directory preserves the provenance only.

**Read when:** Tracing how the training methodology was changed; reviewing
reasoning behind specific spec decisions; historical research only.

---

### `profiling/sara-wakeword/deprecated-hudsons-bay/AGENTS.md`

**Contains:** Archived Hudson's Bay automation from 2026-04-06: legacy
`orchestrate.py` (bespoke EC2 orchestration, superseded), `aws_train.sh`
(Piper-first remote install, superseded), and two session logs. Not for ongoing
use.

**Read when:** Tracing legacy automation history only. Do not use these
artifacts for new work — the current workflow is `oww-training-env.profile.md`
with `tools/launch-spot-instance.py` and `cloud-resources.md`.
