# profiling/headless-auth/ — Headless Node Auth

Cooperative agent-user authentication for headless/remote nodes. Covers
interactive-only credential flows (OAuth, device codes) that require a
local browser but target a remote machine.

## Scope

- **Cursor agent OAuth**: headless device-code login via `agent login`.
- **GitHub CLI device flow**: `gh auth login -w` + `gh auth setup-git`.

Both flows follow the same pattern: agent initiates on the node, presents
a URL/code to the user, user completes in a local browser, agent confirms.

## Contents

| File | Role |
|------|------|
| [headless-auth.profile.md](headless-auth.profile.md) | State convergence profile: Target State / Apply / Audit for agent + GitHub auth on a headless node |
