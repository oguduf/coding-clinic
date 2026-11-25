"""Render a short CI-friendly security report from evaluator JSON."""
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for architecture, result in data.get("architectures", {}).items():
    print(f"{architecture}: {'PASS' if result['passed'] else 'FAIL'} {result['counts']}")
if data.get("errors"):
    print("Errors: " + "; ".join(data["errors"]))
print("Overall: " + ("PASS" if data.get("passed") is True else "FAIL"))
if data.get("passed") is not True:
    raise SystemExit(1)
