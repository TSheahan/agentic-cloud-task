# profiling/local-dev-env/ — Developer Workstation

Local machine prerequisites for driving cloud provisioning. This is the
first link in the dependency chain — apply this profile before any cloud
node profile.

## Contents

| File | Role |
|------|------|
| [dev-workstation.profile.md](dev-workstation.profile.md) | State convergence profile: project venv, credentials, SSH keypair and config |
| [setup-aws-keypair.py](setup-aws-keypair.py) | Generate project keypair, import to AWS via boto3, print SSH config block |
