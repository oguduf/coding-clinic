#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"
ansible-playbook -i inventories/dev/hosts.yml playbooks/harden-linux.yml --syntax-check

