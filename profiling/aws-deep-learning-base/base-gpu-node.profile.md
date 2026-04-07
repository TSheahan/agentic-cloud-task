# Base GPU Node — State Convergence Profile

Common provisioning for an AWS Deep Learning GPU instance. Task-specific
profiles (sara-wakeword, ocr-batch, etc.) layer on top of this baseline.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

### Preconditions (before instance launch)

- AWS account has **spot vCPU quota > 0 for G-family instances** in the
  target region. New accounts default to 0; a quota increase request must be
  approved before spot launch will succeed.
- IAM policy includes `ec2:CreateTags` and `iam:CreateServiceLinkedRole` for
  `spot.amazonaws.com`. See `cloud/iam-policy-ec2-basic.json`.

### Instance

- **A running EC2 spot instance exists** with these properties:
  - AMI: AWS Deep Learning Base GPU AMI (OSS Nvidia Driver), Ubuntu 22.04.
    Region-specific AMI IDs:
    - `ap-southeast-2`: `ami-084f512b0521b5fb4`
  - Instance type: `g4dn.xlarge` (T4, 16 GB VRAM) or larger as task requires.
  - Storage: gp3 EBS, minimum 75 GB (AMI snapshot floor), delete on
    termination. The AMI consumes ~51 GB out of the box (four CUDA
    versions account for ~41 GB). 125 GB is the recommended baseline —
    leaves ~70 GB free for base prereqs and downstream task profiles
    that need ≥20 GB headroom. Adjust upward for data-heavy tasks.
  - Network: public IP assigned, security group allows inbound SSH (port 22).

### System state (after boot + provisioning)

- **NVIDIA apt sources are clean.** The DL AMI ships a duplicate NVIDIA CUDA
  apt source and a wildcard apt pin (`Package: *`, Priority 600) that breaks
  dependency resolution for packages like `ffmpeg`. After provisioning:
  - The duplicate source list file
    `archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list`
    does not exist in `/etc/apt/sources.list.d/`.
  - The NVIDIA apt pin in `/etc/apt/preferences.d/` is scoped to
    `Package: cuda* libnv* libnccl* libcub* nvidia* tensorrt*` (not `*`).

- **System packages installed:** `python3-venv`, `git`, `ffmpeg`, `libsndfile1`.
  (`python3-venv` is absent from the DL AMI's minimal Python — venv creation
  fails without it.)

- **Python 3.10 or 3.11 is available** (the DL AMI includes both).

- **SSH reachable** from the controlling machine.

- **Per-instance SSH config entry exists** in `~/.ssh/config` (e.g.
  `Host cloud-task-sara`), setting only `HostName` to the instance IP.
  Connection defaults (User, IdentityFile, ephemeral-host settings) are
  inherited from the `cloud-task-*` wildcard block established by the
  [local dev environment profile](../local-dev-env/dev-workstation.profile.md).

- **User has an SSH profile** for the instance (agent auth, co-troubleshooting,
  monitoring, on-device agent invocation).

- **Agent installed and authenticated.** Installation has two phases:
  - *Agentic prep* (automatable from the controlling machine via SSH):
    install the agent CLI (`cursor` or `agent` may appear on PATH depending
    on install), add it to PATH, clone the project repo so the agent has the
    profile in its workspace, then set `git config user.name` and
    `user.email` in that repo to match the development workstation (see
    Apply §1).
  - *User action*: SSH in, launch the agent inside the repo, complete
    OAuth sign-in, and trust the workspace. The agent must stay up
    through the OAuth round-trip.

  Once authenticated, the on-device agent reads this profile and drives
  remaining provisioning (apt fixes, package installs) locally with
  iterative error handling — this is more robust than scripting those
  steps remotely.

---

## Apply

### 0. Launch spot instance

Run from the controlling machine (project venv active, `.env` populated).
Creates the security group if absent, launches a spot instance with the
parameters from Target State, waits for it to reach `running`, and writes
an SSH config entry.

```bash
python tools/launch-spot-instance.py \
    --ami ami-084f512b0521b5fb4 \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-<name>
```

Replace `<name>` with the task slug (e.g. `sara`, `ocr`). Ask the user,
and offer default `base` since that is correct except in the case where
multiple base builds are wanted. The tool prints `instance_id=` and
`public_ip=` on success. The SSH config entry inherits connection
defaults from the `cloud-task-*` wildcard block established by the
[local dev environment profile](../local-dev-env/dev-workstation.profile.md).

Adjust `--volume-gb` and `--instance-type` per task requirements.

**Note:** After teardown, spot vCPU quota can take ~60 seconds to
release. Immediate relaunch may fail with `MaxSpotInstanceCountExceeded`;
wait and retry.

### 1. Install agent on instance

Front-load agent access so the on-device agent can drive remaining
provisioning with local iterative troubleshooting — more robust than
scripting apt/package steps remotely.

**Agentic prep** (run from controlling machine via SSH):

```bash
ssh cloud-task-<name> 'curl -fsSL https://cursor.com/install | bash \
    && echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc \
    && export PATH="$HOME/.local/bin:$PATH" \
    && git clone https://github.com/TSheahan/agentic-cloud-task.git'
```

**Git identity in the cloned repo** (do this immediately after clone, before
any commits on the instance). The goal is for commits made on the instance
to use the same author as the development workstation (the system that
invoked the agent).

From the **controlling machine** (recommended — substitutes your local
`git config` values into the remote repo):

```bash
ssh cloud-task-<name> "cd ~/agentic-cloud-task && git config user.name \"$(git config user.name)\" && git config user.email \"$(git config user.email)\""
```

If **clone runs on the instance** (on-device agent or manual SSH), the
calling agent or operator should set the same two fields in
`~/agentic-cloud-task` right after clone, using the `user.name` and
`user.email` from the origin (development) system — the agent can take
those values from the environment where it was invoked.

**User action** (interactive — user SSHes in):

```bash
ssh cloud-task-<name>
cd agentic-cloud-task && agent
# Complete OAuth sign-in when prompted, trust the workspace
```

Once authenticated, the agent has the profile in its workspace and can
drive steps 2–4 locally.

### 2. Fix DL AMI apt configuration

Run on-instance (by the on-device agent or manually):

```bash
# Remove duplicate NVIDIA apt source
if [ -f /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list ]; then
    sudo rm /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list
fi

# Scope NVIDIA apt pin to NVIDIA packages only
for f in /etc/apt/preferences.d/*; do
    if grep -q 'Pin: release l=NVIDIA CUDA' "$f" && grep -q 'Package: \*' "$f"; then
        sudo sed -i 's/^Package: \*$/Package: cuda* libnv* libnccl* libcub* nvidia* tensorrt*/' "$f"
    fi
done
```

### 3. Install system packages

```bash
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git ffmpeg libsndfile1 python3-venv
```

### 4. Identify Python

Prefer 3.11, fall back to 3.10. If neither is present, the AMI is
not the expected Deep Learning Base — stop and diagnose.

```bash
PYTHON=$(command -v python3.11 || command -v python3.10)
echo "Using: $PYTHON ($($PYTHON --version))"
```

### Teardown

Run from the controlling machine:

```bash
python tools/teardown-instance.py --tag cloud-task-<name>
```

Terminates the instance, waits for termination, deletes the security
group (retries on `DependencyViolation`), and removes the SSH config
entry.

---

## Audit

When the executor is **on the instance** (e.g. on-device agent), run checks
**2–4** and **8** locally; **1**, **5**, and **6** require the controlling
machine; **7** is human-verified.

### 1. A running EC2 spot instance exists

Run from the controlling machine (project venv active, `.env` populated):

```bash
python tools/launch-spot-instance.py --tag cloud-task-<name> --check
```
Expected: `PASS: running instance i-... @ <ip> (tag=cloud-task-<name>)`

On-instance confirmation (once SSH is up):

```bash
nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null
```
Expected: GPU name (e.g. `Tesla T4`)

### 2. NVIDIA apt sources are clean

```bash
test ! -f /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list \
    && echo "PASS: no duplicate NVIDIA source" \
    || echo "FAIL: duplicate NVIDIA source still present"
```
Expected: `PASS: no duplicate NVIDIA source`

```bash
grep -r 'Package: \*' /etc/apt/preferences.d/ 2>/dev/null \
    | grep -q 'NVIDIA' \
    && echo "FAIL: wildcard NVIDIA pin still present" \
    || echo "PASS: NVIDIA pin scoped or absent"
```
Expected: `PASS: NVIDIA pin scoped or absent`

### 3. System packages installed

```bash
dpkg -l python3-venv git ffmpeg libsndfile1 2>/dev/null | grep -c '^ii'
```
Expected: `4`

### 4. Python 3.10 or 3.11 is available

```bash
python3.11 --version 2>/dev/null || python3.10 --version 2>/dev/null
```
Expected: `Python 3.11.x` or `Python 3.10.x`

### 5. SSH reachable

Run from the controlling machine (not the instance):

```bash
ssh -o ConnectTimeout=5 cloud-task-<name> echo "PASS: SSH reachable"
```
Expected: `PASS: SSH reachable`

### 6. Per-instance SSH config entry exists

Run from the controlling machine:

```bash
ssh -G cloud-task-<name> 2>/dev/null | grep -i hostname
```
Expected: line containing the instance's public IP

### 7. User has an SSH profile

Human-verified. The user confirms they have an interactive SSH session
profile for the instance (terminal tab, IDE remote session, or equivalent).

### 8. Agent installed and authenticated

Prep check (on-instance):

```bash
(command -v cursor >/dev/null 2>&1 || command -v agent >/dev/null 2>&1) \
    && echo "PASS: agent CLI on PATH" \
    || echo "FAIL: agent CLI not found"
```
Expected: `PASS: agent CLI on PATH`

```bash
test -d ~/agentic-cloud-task/.git \
    && echo "PASS: project repo cloned" \
    || echo "FAIL: project repo not found"
```
Expected: `PASS: project repo cloned`

Authentication check (on-instance, from the project repo directory):

```bash
echo "harness check: respond with 'ok'" | agent -p
```
Expected: `ok`
