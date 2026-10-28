# Offline validation

The tests parse project YAML, inspect security-sensitive defaults, and render
configuration templates using sample values. They do not install packages,
contact SSH hosts, change services, patch an operating system, or require AWS
credentials. They are not a substitute for testing on disposable Ubuntu and RHEL
VMs before an authorized fleet rollout.

From the `ansible-linux-hardening` directory, install development dependencies
from `requirements-dev.txt`, then run:

```bash
yamllint .
ansible-lint
ansible-playbook -i inventories/dev/hosts.yml playbooks/harden-linux.yml --syntax-check
pytest
```

`syntax-check.sh` wraps the Ansible syntax-check command. Molecule is not included:
service-management and package-install tests need disposable systemd-capable
Ubuntu/RHEL images and should only be added once those isolated runners are
available. The Python tests validate template/configuration logic only.

