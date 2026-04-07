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
  - AMI: either the raw AWS Deep Learning Base GPU AMI or a baked base
    image (which includes all system-state items below pre-applied).
    **AMI IDs are not recorded here** — project policy: keep current
    identifiers in the gitignored catalog
    [`cloud-resources.md`](../../cloud-resources.md) (see
    [`cloud-resources.example.md`](../../cloud-resources.example.md) for
    layout and logical names). Resolve the raw Deep Learning Base GPU AMI
    for your region via the EC2 launch wizard or AWS documentation; record
    both raw and baked IDs in that catalog as you use them.
    For a **baked core** golden image, run Apply §2–4, pre-bake secrets
    purge (Apply §5), then register the AMI and add a row to the catalog
    (e.g. logical name `baked-core-gpu`). A prior project bake was
    deregistered after it was found to contain baked-in secrets (agent
    OAuth token, `gh` token, git credential helper); always run the
    pre-bake purge (Apply §5) before creating an image.
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

- **System packages installed:** `python3-venv`, `git`, `gh`, `ffmpeg`,
  `libsndfile1`. (`python3-venv` is absent from the DL AMI's minimal
  Python — venv creation fails without it. `gh` is installed so
  authentication is available when a convergence path needs **HTTPS git
  operations from the instance**; logging in is conditional — see below.)

- **Python 3.10 or 3.11 is available** (the DL AMI includes both).

- **SSH reachable** from the controlling machine.

- **Per-instance SSH config entry exists** in `~/.ssh/config` (e.g.
  `Host cloud-task-sara`), setting only `HostName` to the instance IP.
  Connection defaults (User, IdentityFile, ephemeral-host settings) are
  inherited from the `cloud-task-*` wildcard block established by the
  [local dev environment profile](../local-dev-env/dev-workstation.profile.md).

- **User has an SSH profile** for the instance (agent auth, co-troubleshooting,
  monitoring, on-device agent invocation).

- **Agent CLI installed; project workspace on the instance.** *Agentic
  prep* (from the controlling machine via SSH): install the agent CLI
  (`cursor` or `agent` may appear on PATH depending on install), add it to
  PATH, clone the project repo so an on-device agent would have the
  profile in its workspace, then set `git config user.name` and
  `user.email` in that repo to match the development workstation (Apply
  §1). **No OAuth is required for this prep** — public clone and install
  only.

- **Agent OAuth and `gh` authentication** — **only when in scope** for
  the convergence you are running. Cooperative auth ([headless-auth
  profile](../headless-auth/headless-auth.profile.md)) is wanted when
  **either**:
  - **On-device agentic help** is needed for work **outside** happy-path
    remote provisioning — i.e. you want the agent **on the instance** to
    drive remaining convergence (apt fixes, packages, iteration,
    troubleshooting) with local judgment, rather than only SSH scripts
    from the controlling machine; **or**
  - **`git push` or PR creation via HTTPS from the instance** is required
    and **not** already satisfied by the happy path (everything done from
    the controlling machine with no need to push from the node).

  **When neither applies** — e.g. Apply §2–4 executed entirely over SSH,
  or a **baked AMI** workflow where tokens must not exist on disk — **skip**
  headless auth entirely, complete base provisioning without logging in,
  run **pre-bake purge (Apply §5)** before any AMI snapshot, and treat
  “authenticated agent / `gh`” as **not** part of this convergence’s target
  state.

  **When in scope:** run agent OAuth and `gh auth` / `gh auth setup-git`
  per headless-auth. Then the on-device agent can drive §2–4 locally and
  push to GitHub where needed.

### Pre-bake image hygiene

- **No secrets in bake-eligible state.** Before creating an AMI from a
  provisioned instance, all per-instance credentials must be purged.
  After running the secrets purge (Apply §5), the following hold:
  - Agent CLI is logged out: `agent` is installed but not authenticated
    (no OAuth token persisted).
  - GitHub CLI is logged out: `gh auth status` reports no active account,
    and `~/.config/gh/hosts.yml` contains no `oauth_token`.
  - Git credential helper entries for `gh` are removed: no
    `credential.https://github.com.helper` or
    `credential.https://gist.github.com.helper` in global git config.
  - No token env vars (`GITHUB_TOKEN`, `GH_TOKEN`) in shell rc files.

---

## Apply

When launching from a **baked base AMI** (if one exists), steps 2–4 are
already applied. **Step 1** reduces to: agentic prep only if the image
does not already include it; then **optional** headless auth — only if
this session needs on-device agentic work or `git push`/PR from the
instance (see Target State). Otherwise SSH in and continue task work, or
run §5 before baking. Use the baked AMI ID from
[`cloud-resources.md`](../../cloud-resources.md) in the launch command below.

When launching from the **raw DL AMI**, run all steps in order. Take the
AMI ID from [`cloud-resources.md`](../../cloud-resources.md) or from an
EC2 / AWS console lookup for *Deep Learning Base GPU* in the target region.

**Before baking a new AMI**, always run step 5 (pre-bake secrets purge)
and verify with the corresponding audit checks. No secrets in the image.

### 0. Launch spot instance

Run from the controlling machine (project venv active, `.env` populated).
Creates the security group if absent, launches a spot instance with the
parameters from Target State, waits for it to reach `running`, and writes
an SSH config entry.

```bash
python tools/launch-spot-instance.py \
    --ami <ami-id> \
    --instance-type g4dn.xlarge \
    --volume-gb 125 \
    --tag cloud-task-<name>
```

Use the baked base AMI ID from [`cloud-resources.md`](../../cloud-resources.md)
if one exists, otherwise the raw Deep Learning Base GPU AMI ID from the
same catalog or a fresh region lookup.

Replace `<name>` with the task slug (e.g. `sara`, `ocr`). For the main
**core** baked-image build pipeline, use `core` → tag `cloud-task-core`
and SSH host `cloud-task-core`. Otherwise ask the user and offer default
`base` when a generic one-off base instance is enough. The tool prints `instance_id=` and
`public_ip=` on success. The SSH config entry inherits connection
defaults from the `cloud-task-*` wildcard block established by the
[local dev environment profile](../local-dev-env/dev-workstation.profile.md).

Adjust `--volume-gb` and `--instance-type` per task requirements.

**Note:** After teardown, spot vCPU quota can take ~60 seconds to
release. Immediate relaunch may fail with `MaxSpotInstanceCountExceeded`;
wait and retry.

### 1. Install agent on instance

**Agentic prep** (almost always): install CLI + repo from the controlling
machine via SSH. **Headless auth** (agent + `gh`): **only** if this run
needs on-device agentic convergence or `git push`/PR from the instance
(Target State). If you are doing **remote-only** §2–4 over SSH or heading
for a **purge-then-bake** AMI, complete prep below, then **skip** to §2
without logging in.

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

**Auth flows** (agent + GitHub) — **when in scope only:** follow the
[headless-auth profile](../headless-auth/headless-auth.profile.md). Both
flows are agent-initiated, user-completed via local browser. With both
authenticated, the on-device agent can drive steps 2–4 locally and push
results to GitHub.

**When auth is out of scope:** do not run login flows; drive §2–4 from the
controlling machine (`ssh … 'bash -s'`, uploaded scripts, or an equivalent
happy path). Before creating an AMI, always run §5.

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
    git gh ffmpeg libsndfile1 python3-venv
```

### 4. Identify Python

Prefer 3.11, fall back to 3.10. If neither is present, the AMI is
not the expected Deep Learning Base — stop and diagnose.

```bash
PYTHON=$(command -v python3.11 || command -v python3.10)
echo "Using: $PYTHON ($($PYTHON --version))"
```

### 5. Pre-bake secrets purge

Run on-instance **before** creating an AMI. This strips all per-instance
credentials so the image is safe to share or relaunch without leaking
tokens. After bake, re-authenticate using the
[headless-auth profile](../headless-auth/headless-auth.profile.md).

**Agent logout:**

```bash
agent logout
```

**GitHub CLI logout and credential helper removal:**

`gh auth logout` removes the local token but does **not** undo
`gh auth setup-git`. The credential helper entries are URL-scoped
(`credential.https://github.com.helper`), not the bare
`credential.helper` — they must be removed explicitly.

```bash
gh auth logout --hostname github.com

git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper
```

**Verify no residual tokens in gh config:**

```bash
test ! -f "$HOME/.config/gh/hosts.yml" \
    || ! grep -q oauth_token "$HOME/.config/gh/hosts.yml"
```

If `hosts.yml` still contains an `oauth_token` line after logout, remove
it: `rm -f "$HOME/.config/gh/hosts.yml"`.

**Verify no token env vars in shell rc files:**

```bash
grep -l 'GITHUB_TOKEN\|GH_TOKEN\|GH_ENTERPRISE_TOKEN' \
    ~/.bashrc ~/.profile ~/.bash_profile 2>/dev/null
```

If any file is listed, edit it to remove the offending export line.

Run the audit checks for this item (Audit §10) before proceeding to AMI
creation.

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
**2–4**, **8** (prep always; auth sub-check only if auth is in scope), **9**
(only if `gh` auth is in scope), and **10** locally; **1**, **5**, and **6**
require the controlling machine; **7** is human-verified. Check **10** is only
relevant before AMI bake.

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
dpkg -l python3-venv git gh ffmpeg libsndfile1 2>/dev/null | grep -c '^ii'
```
Expected: `5`

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

### 8. Agent CLI installed; authenticated only if auth is in scope

Prep checks (on-instance) — **always** for this profile’s base layout:

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

Authentication check (on-instance, from the project repo directory) —
**run only when** Target State for this convergence includes logged-in
agent (on-device agentic path). **Skip** for remote-only provision or
pre-bake (expect `agent login` / API-key messaging instead of `ok`):

```bash
echo "harness check: respond with 'ok'" | agent -p
```
Expected when auth is in scope: `ok`

### 9. GitHub CLI authenticated — only when `gh` auth is in scope

**Run when** Target State requires HTTPS git from the instance (`git push`,
PRs). **Skip** when provisioning was remote-only and no `gh` session is
required.

```bash
gh auth status >/dev/null 2>&1 \
    && echo "PASS: gh authenticated" \
    || echo "FAIL: gh not authenticated"
```
Expected when in scope: `PASS: gh authenticated`

```bash
git config --global credential.helper 2>/dev/null | grep -q 'gh' \
    && echo "PASS: gh credential helper configured" \
    || echo "FAIL: gh credential helper not set"
```
Expected when in scope: `PASS: gh credential helper configured`

### 10. No secrets in bake-eligible state

Run on-instance before AMI creation. All four checks must pass.

**Agent logged out:**

```bash
echo "ping" | agent -p 2>&1 | grep -qi 'log\s*in\|auth\|sign.in\|unauthorized' \
    && echo "PASS: agent not authenticated (login prompt detected)" \
    || echo "INFO: agent responded — may still be authenticated; verify manually"
```
Expected: `PASS: agent not authenticated (login prompt detected)`

**GitHub CLI logged out:**

```bash
gh auth status 2>&1 | grep -qi 'not logged' \
    && echo "PASS: gh not authenticated" \
    || (gh auth status >/dev/null 2>&1 \
        && echo "FAIL: gh still authenticated" \
        || echo "PASS: gh not authenticated")
```
Expected: `PASS: gh not authenticated`

```bash
if [ -f "$HOME/.config/gh/hosts.yml" ] && grep -q oauth_token "$HOME/.config/gh/hosts.yml"; then
    echo "FAIL: oauth_token found in hosts.yml"
else
    echo "PASS: no oauth_token in hosts.yml"
fi
```
Expected: `PASS: no oauth_token in hosts.yml`

**Git credential helper entries for `gh` removed:**

```bash
git config --global --get-regexp '^credential\.' 2>/dev/null \
    | grep -q 'gh auth git-credential' \
    && echo "FAIL: gh credential helper still in global git config" \
    || echo "PASS: no gh credential helper in global git config"
```
Expected: `PASS: no gh credential helper in global git config`

**No token env vars in shell rc files:**

```bash
grep -l 'GITHUB_TOKEN\|GH_TOKEN\|GH_ENTERPRISE_TOKEN' \
    ~/.bashrc ~/.profile ~/.bash_profile 2>/dev/null \
    && echo "FAIL: token env var found in shell rc" \
    || echo "PASS: no token env vars in shell rc files"
```
Expected: `PASS: no token env vars in shell rc files`
