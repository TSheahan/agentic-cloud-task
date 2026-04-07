# Headless Node Auth — State Convergence Profile

Cooperative credential injection for headless/remote nodes. Both flows
(Cursor agent, GitHub CLI) are interactive-only OAuth/device-code grants
that need a local browser — the agent initiates on the node, the user
completes locally.

This is a cross-cutting concern consumed by node provisioning profiles
(e.g. [base-gpu-node](../aws-deep-learning-base/base-gpu-node.profile.md))
wherever agent or GitHub auth is needed on a headless machine.

Follows the [state convergence pattern](../../policies/state-convergence-pattern.md).

---

## Target State

### Cursor agent CLI

- **Agent CLI is authenticated.** Running a trivial prompt through the CLI
  succeeds without an OAuth prompt:
  ```bash
  echo "reply ok" | agent -p
  ```
  Expected: a response containing `ok` (no login redirect, no error).

### GitHub CLI

- **`gh` is installed.** `gh --version` returns a version string.

- **`gh` is authenticated.** `gh auth status` exits 0 and reports a valid
  token scoped to the expected GitHub account.

- **Git credential helper uses `gh`.** `gh auth setup-git` has been run;
  `git config --global credential.helper` includes `gh` so HTTPS git
  operations (push, clone private repos) work without separate PATs.

---

## Apply

Two independent flows. Order doesn't matter; both require user
cooperation for the browser step.

### Cursor agent login

**Prerequisite:** Agent CLI installed and on PATH (`agent` or `cursor`
resolves). The
[base-gpu-node profile](../aws-deep-learning-base/base-gpu-node.profile.md)
Apply §1 covers installation.

**AGENT** — run on the node (suppress auto-open since there's no desktop
browser):

```bash
NO_OPEN_BROWSER=1 agent login
```

The command prints an OAuth URL to stdout. Present this URL to the user
clearly — it is the only output they need.

**USER** — open the URL in a local browser and complete the Cursor OAuth
sign-in. The agent's `login` command will detect completion and exit.

Verify by running the audit check for this item.

### GitHub CLI login

**Prerequisite:** `gh` is installed. On Ubuntu/Debian nodes the
[base-gpu-node profile](../aws-deep-learning-base/base-gpu-node.profile.md)
installs it via `sudo apt-get install -y gh`.

**AGENT** — run on the node:

```bash
gh auth login -w
```

This prints a one-time device code and a URL
(`https://github.com/login/device`). Present **both** the code and the
URL to the user.

**USER** — open the URL in a local browser, enter the device code, and
authorize the GitHub OAuth app.

**AGENT** — after the user confirms completion, finalize:

```bash
gh auth setup-git
```

This configures `gh` as the global Git credential helper for HTTPS
operations.

---

## Audit

### 1. Agent CLI is authenticated

```bash
echo "reply ok" | agent -p 2>/dev/null \
    && echo "PASS: agent authenticated" \
    || echo "FAIL: agent not authenticated or not responding"
```
Expected: output containing `PASS: agent authenticated` (and the LLM's
response to "reply ok" on a preceding line).

### 2. `gh` is installed

```bash
gh --version >/dev/null 2>&1 \
    && echo "PASS: gh installed" \
    || echo "FAIL: gh not found"
```
Expected: `PASS: gh installed`

### 3. `gh` is authenticated

```bash
gh auth status >/dev/null 2>&1 \
    && echo "PASS: gh authenticated" \
    || echo "FAIL: gh not authenticated"
```
Expected: `PASS: gh authenticated`

### 4. Git credential helper uses `gh`

```bash
git config --global credential.helper 2>/dev/null | grep -q 'gh' \
    && echo "PASS: gh credential helper configured" \
    || echo "FAIL: gh credential helper not set"
```
Expected: `PASS: gh credential helper configured`
