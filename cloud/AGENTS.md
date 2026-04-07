# cloud/ — Agent Context

Checked-in config-as-code for cloud platforms. Preferred application method: script/CLI tooling.

## Contents

| File | Purpose |
|------|---------|
| `iam-policy-ec2-basic.json` | IAM policy covering the full instance lifecycle: discover, launch, stop, AMI bake, teardown, networking, key pairs, tagging, debugging, spot. |

## Resource scoping

All EC2 resources created by this project carry the tag
`Project = agentic-cloud-task`. The IAM policy uses this tag in two ways:

- **Create actions** require `aws:RequestTag/Project = agentic-cloud-task` —
  resources must be tagged at birth.
- **Mutate/destroy actions** require `ec2:ResourceTag/Project = agentic-cloud-task` —
  can only touch project-owned resources.
- **Read actions** (`Describe*`) and **account-wide services** (Cost Explorer,
  CloudWatch) stay at `Resource: "*"` — they don't support resource-level
  scoping.

All orchestration scripts and profiles must tag created resources with
`Project: agentic-cloud-task`. Additional case-level tags (e.g.
`Task: sara-wakeword`) are encouraged but not enforced by IAM.

## Policy coverage by lifecycle phase

| Phase | Sids | Scoped by |
|-------|------|-----------|
| Discovery | Discover | `*` (read-only) |
| Instance launch | LaunchInstancesCreatedResources, LaunchInstancesReferencedResources | RequestTag on created; `*` on AMI/subnet/SG/keypair being referenced |
| Instance manage | ManageProjectInstances | ResourceTag |
| AMI bake | CreateAMIFromProjectInstances, CreateAMIOutputResources | ResourceTag on source instance; RequestTag on created image/snapshot |
| AMI cleanup | CleanupProjectAMIs | ResourceTag |
| Networking | CreateProjectSecurityGroups, CreateSecurityGroupInVPC, ManageProjectSecurityGroups | RequestTag on create; ResourceTag on mutate |
| Elastic IP | AllocateProjectElasticIPs, ManageProjectElasticIPs | RequestTag on allocate; ResourceTag on manage |
| Key pairs | CreateProjectKeyPairs, DeleteProjectKeyPairs | RequestTag on create/import; ResourceTag on delete |
| Tagging | TagProjectResources, TagAtLaunch | RequestTag; CreateAction condition |
| Debugging | DebugProjectInstances | ResourceTag |
| Observability | Observability | `*` (read-only) |
| Cost | CostGovernance | `*` (account-wide) |
| Spot | SpotServiceRole | Scoped to service-linked role ARN |

## Next-layer capabilities (not yet included)

Capabilities that are plausible next steps as the project matures. Add
when the need materialises, not speculatively.

### Observability

- **CloudWatch Logs read** (`logs:GetLogEvents`, `logs:FilterLogEvents`,
  `logs:DescribeLogGroups`) — pull training logs without SSH. Useful when
  an instance is running a long job and the SSH session dropped.
- **CloudWatch Metrics read** (`cloudwatch:GetMetricData`) — GPU
  utilisation, network throughput. Confirms training is actually using
  the GPU rather than idle-spinning.

### Storage

- **S3 bucket access** (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`)
  — alternative transfer path when rsync/SSH is inconvenient. Staging
  large datasets, parking model artifacts for cross-machine pickup.
- **EBS volume management** (`ec2:CreateVolume`, `ec2:AttachVolume`,
  `ec2:DetachVolume`, `ec2:DeleteVolume`) — detachable data volumes that
  survive instance termination. Useful when dataset prep and training
  happen across separate instance launches.

### Access alternatives

- **SSM Session Manager** (`ssm:StartSession`, `ssm:TerminateSession`,
  `ssm:DescribeSessions`) — shell access without opening port 22 or
  managing SSH keys. Requires the SSM agent on the instance (pre-installed
  on most AWS AMIs). Eliminates the security group for SSH entirely.
- **EC2 Instance Connect** (`ec2-instance-connect:SendSSHPublicKey`) —
  push a temporary SSH key for one-off access without a persistent keypair.

### Cost governance

- **Billing/Cost Explorer read** (`ce:GetCostAndUsage`) — track actual
  spend per task. Catches runaway instances or unexpected data transfer
  charges.
- **Budgets** (`budgets:ViewBudget`) — pair with an AWS Budget alarm so
  a forgotten instance triggers notification before it gets expensive.

### Instance flexibility

- **Elastic IP** (`ec2:AllocateAddress`, `ec2:AssociateAddress`,
  `ec2:ReleaseAddress`) — stable IP across stop/start cycles. Currently
  each start gets a new public IP, which means updating SSH config each
  time.
- **Instance profile / role passing** (`iam:PassRole`) — attach an IAM
  role to the instance so it can access AWS services (S3, CloudWatch)
  directly without baking credentials into the environment.
