# cloud/ — Agent Context

Checked-in config-as-code for cloud platforms. Preferred application method: script/CLI tooling.

## Contents

| File | Purpose |
|------|---------|
| `iam-policy-ec2-basic.json` | Starter IAM policy: EC2 launch & teardown, security groups, key pairs, tagging, Spot role. |

## Known gaps in IAM policy

The basic policy covers instance launch and teardown only. Extend as needed:

- AMI creation: `CreateImage`, `RegisterImage`, `DeregisterImage` (needed for
  repeatable tasks like `profiling/ocr-batch/`)
- S3 access (if S3 sync is used as a transfer fallback)
- SSM access (if SSM is used for bootstrap instead of SSH)
