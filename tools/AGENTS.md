# tools/ — Shared Operational Utilities

Reusable scripts invoked by profile Apply and Audit steps. Each tool
performs one atomic operation (launch an instance, ensure a security group,
tear down tagged resources) and is parameterised so multiple profiles can
share it.

## Conventions

- Tools read AWS credentials from the project `.env` via `python-dotenv`.
- Tools are invoked from the project venv (`venv/`) established by the
  [local dev workstation profile](../profiling/local-dev-env/dev-workstation.profile.md).
- Each tool is self-documenting (`--help`).
- Tools that modify state support a `--check` or dry-run mode for Audit use.

## Contents

| Tool | Purpose |
|------|---------|
| [launch-spot-instance.py](launch-spot-instance.py) | Ensure security group, launch EC2 spot instance, wait for running, return IP. Write SSH config entry. |
| [teardown-instance.py](teardown-instance.py) | Terminate tagged instances, clean up security group and SSH config entry. |
