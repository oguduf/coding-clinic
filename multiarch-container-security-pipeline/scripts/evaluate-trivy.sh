#!/usr/bin/env bash
set -Eeuo pipefail
usage() {
  echo "Usage: evaluate-trivy.sh --amd64 FILE --arm64 FILE [--summary FILE] [--severity HIGH,CRITICAL]"
}
amd64='' arm64='' summary='' severity='HIGH,CRITICAL'
while (($#)); do
  case "$1" in
    --amd64)
      (($# >= 2)) || {
        usage >&2
        exit 2
      }
      amd64=$2
      shift 2
      ;;
    --arm64)
      (($# >= 2)) || {
        usage >&2
        exit 2
      }
      arm64=$2
      shift 2
      ;;
    --summary)
      (($# >= 2)) || {
        usage >&2
        exit 2
      }
      summary=$2
      shift 2
      ;;
    --severity)
      (($# >= 2)) || {
        usage >&2
        exit 2
      }
      severity=$2
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done
[[ -n $amd64 && -n $arm64 ]] || {
  usage >&2
  exit 2
}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
args=(--amd64 "$amd64" --arm64 "$arm64" --severity "$severity")
[[ -z $summary ]] || args+=(--summary "$summary")
python_bin=${PYTHON:-python3}
if ! command -v "$python_bin" >/dev/null 2>&1 && [[ $python_bin == python3 ]]; then
  python_bin=python
fi
command -v "$python_bin" >/dev/null 2>&1 || {
  echo 'Python 3 is required to evaluate Trivy reports' >&2
  exit 127
}
"$python_bin" "$script_dir/evaluate_trivy.py" "${args[@]}"
