# Developer Workstation — State Convergence Profile

Local machine setup for driving cloud provisioning. This profile must hold
before any cloud node profile can be applied — it provides the tools,
credentials, and connectivity the operator (human or agent) needs to reach
AWS and manage instances.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

### Python environment

- **Python 3.x is available** on the system PATH.
- **`requirements.txt` exists** at project root listing project dependencies.
- **`venv/` exists** at project root, created from system Python.
- **All packages in `requirements.txt` are installed** in the venv
  (boto3, paramiko, python-dotenv, loguru at minimum).

### IAM identity

- **IAM policy `agentic-cloud-task-automation` exists** in the AWS account
  with the contents of `cloud/iam-policy-ec2-basic.json`, tagged
  `Project = agentic-cloud-task`.
- **IAM user `agentic-cloud-task-automation` exists** with that policy
  attached.
- **An active access key** exists for that user.

### AWS CLI (recommended, not required)

- **`aws` command is available** on the system PATH.
- **`aws --version`** returns AWS CLI v2.
- Useful for manual inspection and troubleshooting, but not in the
  critical path — all programmatic AWS access uses boto3 from the
  project venv.

### AWS credentials

- **`.env` exists** at project root with the following variables populated:
  - `AWS_ACCESS_KEY_ID_CLOUD`
  - `AWS_SECRET_ACCESS_KEY_CLOUD`
  - `AWS_DEFAULT_REGION`
  - Optional **`AGENTIC_ORCHESTRATOR_ROLE_ARN`** — ARN of `agentic-cloud-task-orchestrator-role` (or equivalent). When set, `tools/_env.py` and tools that call `resolved_assume_role_arn` use it so Batch/ECR/full orchestrator APIs work without passing `--assume-role` every time. See [tools/AGENTS.md](../../tools/AGENTS.md).
- **`.env` is gitignored** (already covered by project `.gitignore`).
- **`.env.example` exists** at project root documenting the required
  variable names without values.

### SSH keypair

- **`.keys/` directory exists** at project root, gitignored.
- **A project-global keypair** exists at `.keys/cloud-task.pem` (private)
  and `.keys/cloud-task.pem.pub` (public).
- **The public key is imported to AWS** as a named key pair in the target
  region, so instances can be launched with it.

### SSH config (durable block)

- **`~/.ssh/config` contains a wildcard Host block** for `cloud-task-*`
  that sets shared connection defaults for all project instances:

  ```
  Host cloud-task-*
      User ubuntu
      IdentityFile <project-root>/.keys/cloud-task.pem
      StrictHostKeyChecking no
      UserKnownHostsFile /dev/null
  ```

- The `IdentityFile` path is absolute and points to the project keypair.
- Per-instance Host entries (e.g. `Host cloud-task-sara`) are **not** owned
  by this profile — they are created by the agent or orchestration tooling
  when an instance launches, and inherit from this wildcard block. See
  [base-gpu-node.profile.md](../aws-deep-learning-base/base-gpu-node.profile.md) for the
  instance-side convention.

---

## Apply

### 1. Project venv

```bash
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 2. IAM setup (AWS Console — user interactive)

Create the IAM policy, user, and access key. These steps happen in the
AWS Console because the account has no programmatic access yet — this is
what bootstraps it.

**Create the IAM policy:**

```
Console → IAM → Policies → Create policy
  → JSON tab → paste contents of cloud/iam-policy-ec2-basic.json
  → Policy name: agentic-cloud-task-automation
  → Tags: Project = agentic-cloud-task
  → Create policy
```

**Create the IAM user and attach the policy:**

```
Console → IAM → Users → Create user
  → User name: agentic-cloud-task-automation
  → Next
  → Attach policies directly → search "agentic-cloud-task-automation" → select
  → Next
  → Create user
```

**Create access credentials:**

```
Console → IAM → Users → agentic-cloud-task-automation → Security credentials
  → Create access key
  → Use case: Application running outside AWS
  → Next
  → Description: lets the agentic-cloud-task project manage spot instances and related resources on AWS
  → Create access key
```

**Copy the access key ID and secret access key immediately** — the secret
is only shown on this screen and cannot be retrieved later.

### 3. Credentials file

Copy `.env.example` to `.env` and populate with the keys from step 2:

```
AWS_ACCESS_KEY_ID_CLOUD=AKIA...
AWS_SECRET_ACCESS_KEY_CLOUD=...
AWS_DEFAULT_REGION=ap-southeast-2
```

### 4. SSH keypair + AWS import

With the venv active and `.env` populated, run the setup script:

```bash
python profiling/local-dev-env/setup-aws-keypair.py
```

This generates `.keys/cloud-task.pem` (+ `.pub`), imports the public key
to AWS via boto3, verifies the IAM identity, and prints the SSH config
block to append. Idempotent — safe to re-run.

See [setup-aws-keypair.py](setup-aws-keypair.py).

### 5. SSH config

Append the block printed by the setup script to `~/.ssh/config`.
If `~/.ssh/config` does not exist, create it.

### 6. AWS CLI (optional)

_Install method depends on OS. On Windows, use the MSI installer from
https://aws.amazon.com/cli/ — validate with `aws --version` after install.
Not required for profile execution — boto3 handles all programmatic access._

---

## Audit

### 1. Python 3.x is available

```bash
python --version
```
Expected: `Python 3.x.x`

### 2. `requirements.txt` exists

```bash
test -f requirements.txt && echo "PASS: requirements.txt present" || echo "FAIL: requirements.txt missing"
```
Expected: `PASS: requirements.txt present`

### 3. `venv/` exists

```bash
test -d venv && echo "PASS: venv directory exists" || echo "FAIL: venv missing"
```
Expected: `PASS: venv directory exists`

### 4. All packages in `requirements.txt` are installed

```bash
python -c "import boto3, paramiko, dotenv, loguru; print('PASS: project deps importable')"
```
Expected: `PASS: project deps importable`

### 5. IAM policy `agentic-cloud-task-automation` exists

Not automatically verifiable — the automation user's permissions do not
include IAM read access. Verified indirectly: if check 7 (active access
key) succeeds and EC2 operations work, the policy is attached.

### 6. IAM user `agentic-cloud-task-automation` exists

Verified by check 7 below — STS GetCallerIdentity confirms the user ARN.

### 7. An active access key exists

```bash
python -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('.env')); import os, boto3; sts=boto3.client('sts', region_name=os.environ['AWS_DEFAULT_REGION'], aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID_CLOUD'], aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY_CLOUD']); print('PASS:', sts.get_caller_identity()['Arn'])"
```
Expected: `PASS: arn:aws:iam::...:user/agentic-cloud-task-automation`

### 8. `aws` command is available

### 9. `aws --version` returns AWS CLI v2

Checks 8 + 9 share a single command (optional item):

```bash
aws --version
```
Expected: `aws-cli/2.x.x ...` (if installed)

### 10. `.env` exists

```bash
python -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('.env')); import os; assert os.environ.get('AWS_ACCESS_KEY_ID_CLOUD'), 'missing'; print('PASS: credentials loadable')"
```
Expected: `PASS: credentials loadable`

### 11. `.env` is gitignored

```bash
git check-ignore .env && echo "PASS: .env is gitignored" || echo "FAIL: .env not gitignored"
```
Expected: `PASS: .env is gitignored`

### 12. `.env.example` exists

```bash
test -f .env.example && echo "PASS: .env.example present" || echo "FAIL: .env.example missing"
```
Expected: `PASS: .env.example present`

### 13. `.keys/` directory exists

```bash
test -d .keys && echo "PASS: .keys directory exists" || echo "FAIL: .keys missing"
```
Expected: `PASS: .keys directory exists`

### 14. A project-global keypair exists

```bash
test -f .keys/cloud-task.pem && test -f .keys/cloud-task.pem.pub \
    && echo "PASS: keypair present" \
    || echo "FAIL: keypair missing"
```
Expected: `PASS: keypair present`

### 15. The public key is imported to AWS

```bash
python -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('.env')); import os, boto3; ec2=boto3.client('ec2', region_name=os.environ['AWS_DEFAULT_REGION'], aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID_CLOUD'], aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY_CLOUD']); kp=ec2.describe_key_pairs(KeyNames=['cloud-task']); print('PASS: key pair in AWS, fingerprint:', kp['KeyPairs'][0]['KeyFingerprint'])"
```
Expected: `PASS: key pair in AWS, fingerprint: ...`

### 16. `~/.ssh/config` contains a wildcard Host block

```bash
ssh -G cloud-task-test 2>/dev/null | grep -i identityfile
```
Expected: line containing `.keys/cloud-task.pem`
