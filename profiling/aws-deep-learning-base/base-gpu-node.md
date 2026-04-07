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

### Instance properties

- **AMI:** AWS Deep Learning Base GPU AMI (OSS Nvidia Driver), Ubuntu 22.04.
  Region-specific AMI IDs:
  - `ap-southeast-2`: `ami-084f512b0521b5fb4`
- **Instance type:** `g4dn.xlarge` (T4, 16 GB VRAM) or larger as task requires.
- **Storage:** gp3 EBS, sized per task (40 GB or ask user), delete on
  termination.
- **Network:** public IP assigned, security group allows inbound SSH (port 22).

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
  [local dev environment profile](../local-dev-env/dev-workstation.md).

- **User has an SSH profile** for the instance (agent auth, co-troubleshooting,
  monitoring, on-device agent invocation).

- **Agent installed and authenticated.** On first launch the agent presents an
  OAuth code + URL; the user completes the flow while the agent remains
  running. The agent must stay up through the OAuth round-trip.

---

## Apply

### 1. Fix DL AMI apt configuration

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

### 2. Install system packages

```bash
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git ffmpeg libsndfile1 python3-venv
```

### 3. Identify Python

Prefer 3.11, fall back to 3.10. If neither is present, the AMI is
not the expected Deep Learning Base — stop and diagnose.

```bash
PYTHON=$(command -v python3.11 || command -v python3.10)
echo "Using: $PYTHON ($($PYTHON --version))"
```

### 4. SSH and agent access

The user cooperates to connect an agent to the instance over SSH. Once
the agent has a shell, it can read this profile and drive remaining
provisioning autonomously.

File transfer uses rsync over SSH (or SFTP as a fallback).

### Teardown notes

- Instance termination may leave the security group in a
  `DependencyViolation` state for a brief window. Retry SG deletion
  after a short delay, or clean up manually in the console if it persists.

---

## Audit

```bash
# 1. No duplicate NVIDIA apt source
test ! -f /etc/apt/sources.list.d/archive_uri-https_developer_download_nvidia_com_compute_cuda_repos_ubuntu2204_x86_64_-jammy.list \
    && echo "PASS: no duplicate NVIDIA source" \
    || echo "FAIL: duplicate NVIDIA source still present"
```
Expected: `PASS: no duplicate NVIDIA source`

```bash
# 2. NVIDIA apt pin scoped (not wildcard)
grep -r 'Package: \*' /etc/apt/preferences.d/ 2>/dev/null \
    | grep -q 'NVIDIA' \
    && echo "FAIL: wildcard NVIDIA pin still present" \
    || echo "PASS: NVIDIA pin scoped or absent"
```
Expected: `PASS: NVIDIA pin scoped or absent`

```bash
# 3. System packages
dpkg -l python3-venv git ffmpeg libsndfile1 2>/dev/null | grep -c '^ii'
```
Expected: `4`

```bash
# 4. Python version
python3.11 --version 2>/dev/null || python3.10 --version 2>/dev/null
```
Expected: `Python 3.11.x` or `Python 3.10.x`

```bash
# 5. GPU visible
nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null
```
Expected: GPU name (e.g. `Tesla T4`)
