# Cloud Resources Catalog

Live inventory of cloud resources owned by this project.
Copy this file to `cloud-resources.md` (gitignored) and maintain it as
resources are created or destroyed.

---

## Nodes

Active or recently terminated EC2 instances. Name follows the
`cloud-task-<slug>` convention from the base GPU node profile.

| Name | Instance ID | Region | Type | Status | Notes |
|------|-------------|--------|------|--------|-------|
| `cloud-task-base` | `i-0123456789abcdef0` | ap-southeast-2 | g4dn.xlarge | terminated | example entry |

## AMIs

Custom images registered in this account.

| AMI ID | Region | Based On | Created | Status | Notes |
|--------|--------|----------|---------|--------|-------|
| `ami-0123456789abcdef0` | ap-southeast-2 | ami-084f512b0521b5fb4 (raw DL Base) | 2026-04-07 | deregistered | example entry |
