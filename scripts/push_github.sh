#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ ! -f .env ]]; then echo '.env is missing' >&2; exit 2; fi
set -a
source .env
set +a
if [[ -z "${GH_KEY:-}" ]]; then echo 'GH_KEY is missing from project .env' >&2; exit 2; fi
git push "https://x-access-token:${GH_KEY}@github.com/gyuvdvxtjq/new-energy-agent.git" HEAD:main
echo 'push completed'
