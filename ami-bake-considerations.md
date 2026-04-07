# Custom AMI bake — considerations

This project often starts from the **AWS Deep Learning Base GPU AMI**, then
converges a node with a profile such as
[`profiling/aws-deep-learning-base/base-gpu-node.profile.md`](profiling/aws-deep-learning-base/base-gpu-node.profile.md).
After that convergence, **creating a custom AMI** is optional but useful when
you want faster cold starts and less repeated apt/package work on every launch.

This document collects **operational and security** considerations for that
bake. It is not a step-by-step runbook; pair it with AWS docs and your
account’s IAM policy in [`cloud/`](cloud/AGENTS.md).

---

## Why bake a golden image

- **Faster iteration** — Skip re-running baseline Apply steps (apt fixes,
  package installs) on each new instance.
- **Repeatability** — Same stack for every launch in a region, which makes
  task profiles (e.g. wake-word training) easier to reason about.
- **Fit with profiling** — The
  [aws-deep-learning-base area](profiling/aws-deep-learning-base/AGENTS.md)
  allows AMI bake when the task profile calls for it. Task areas differ:
  [sara-wakeword](profiling/sara-wakeword/AGENTS.md) emphasizes **one-shot
  training** lifecycle (discard after the job); [ocr-batch](profiling/ocr-batch/AGENTS.md)
  describes **retaining** a custom AMI for reuse. A **base** golden AMI is
  compatible with both: you are not required to throw away the *baseline* image
  just because a *training run* image is ephemeral.

---

## Technical bake notes

- **CreateImage** — IAM for this project is intended to cover AMI creation
  (`ec2:CreateImage` and related snapshot actions); see
  [`cloud/iam-policy-ec2-basic.json`](cloud/iam-policy-ec2-basic.json) and
  [`cloud/AGENTS.md`](cloud/AGENTS.md).
- **Filesystem consistency** — Prefer **stopping** the instance (or otherwise
  quiescing writes) before creating the image, so the snapshot is not taken
  mid-flight. Follow AWS guidance for your OS and workload.
- **AMI availability** — Wait until the image is **available** before
  launching dependent instances. Update launch tooling and profiles with the
  **new AMI ID** per region (e.g. `launch-spot-instance.py --ami`, task
  orchestration scripts).
- **Smoke test** — Launch one instance from the new AMI and run the relevant
  **Audit** sections from your profile (on-instance checks at minimum) before
  depending on it for production training.

---

## Secrets and baked credentials

**Default posture:** treat the AMI as **non-secret**. Do not bake long-lived
cloud credentials, OAuth tokens, agent session data, or API keys unless you
have explicitly designed for that case.

**If you must bake something sensitive** (a small subset of environments):

- **The AMI is a secret-bearing asset.** Anyone who can **copy**, **share**, or
  **launch** the image effectively gets the same material as root on a
  instance built from it. “Strict access control” must apply to the **AMI and
  its snapshots**, not only to SSH or the running instance.
- **Scope** — Prefer narrow, single-purpose credentials; avoid root AWS keys.
  Where possible, use an **instance role** and **IMDS** for AWS API access
  instead of static keys on disk.
- **Rotation** — Baked secrets imply **rebake** or a parallel secret lifecycle.
  Plan how often you rebuild the image and how you invalidate old AMIs.
- **Compliance** — Some policies disallow credentials in images regardless of
  network controls; treat this as an explicit risk acceptance decision.

---

## “Strict access control” — what it must include

If baked secrets are in play, the **whole pipeline** needs to be aligned:

| Layer | What to control |
|--------|-------------------|
| **AMI & snapshots** | Who can `DescribeImages`, `CopyImage`, share across accounts, or create public snapshots. |
| **Launch** | Who may `RunInstances` with this AMI; tagging and resource policies for project-scoped resources. |
| **Network** | No broad SSH from the internet if not required; prefer private subnets, bastion, or Session Manager patterns. |
| **Runtime** | Minimal post-boot access; monitoring and auditing on instances that hold sensitive material. |

---

## Preferred middle ground

For many workloads, **bake only the baseline** (OS, drivers, CUDA stack,
packages, repo layout without tokens) and **inject secrets at first boot**:

- **AWS Systems Manager Parameter Store** or **Secrets Manager** with an **instance
  profile** (no long-lived keys in user data if avoidable).
- **User data** or an **init** script that runs once after launch.

That keeps the AMI reusable and shareable with less blast radius while still
automating provisioning.

---

## When this project updates profiles

If a custom base AMI becomes canonical, **Target State** in
`base-gpu-node.profile.md` (or a sibling profile) should describe:

- **Stock DL AMI** vs **project golden AMI** (ID and region), and
- Any **Audit** steps that differ when the duplicate NVIDIA source is already
  absent on first boot.

Refine profiles **inline** when you validate the first bake, per
[`AGENTS.md`](AGENTS.md) profile refinement.
