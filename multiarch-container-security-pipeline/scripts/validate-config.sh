#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
config=${1:-"$script_dir/../config/pipeline.example.yaml"}
python3 "$script_dir/validate_config.py" "$config"
