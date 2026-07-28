#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  printf "RouteWise virtual environment not found. Create .venv first.\n" >&2
  exit 1
fi

.venv/bin/python - <<'PY'
import getpass
import os
from pathlib import Path


key = getpass.getpass("Paste your OpenAI API key (input is hidden): ").strip()
if not key:
    raise SystemExit("No key entered; .env was not changed.")
if not key.startswith("sk-"):
    raise SystemExit("That does not look like an OpenAI API key; .env was not changed.")

env_path = Path(".env")
lines = env_path.read_text().splitlines() if env_path.exists() else []
updated_lines: list[str] = []
key_written = False

for line in lines:
    if line.startswith("OPENAI_API_KEY="):
        if not key_written:
            updated_lines.append(f"OPENAI_API_KEY={key}")
            key_written = True
        continue
    updated_lines.append(line)

if not key_written:
    if updated_lines and updated_lines[-1]:
        updated_lines.append("")
    updated_lines.append(f"OPENAI_API_KEY={key}")

env_path.write_text("\n".join(updated_lines) + "\n")
os.chmod(env_path, 0o600)
print("OPENAI_API_KEY saved securely in .env.")
print("Restart RouteWise so the model catalog can detect it.")
PY
