#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ ! -f .env ]]; then echo '.env is missing' >&2; exit 2; fi
set -a
source .env
set +a
PUSH_KEY="${GH_KEY:-${gh_key:-}}"
if [[ -z "$PUSH_KEY" ]]; then echo 'GH_KEY/gh_key is missing from project .env' >&2; exit 2; fi
git push "https://x-access-token:${PUSH_KEY}@github.com/gyuvdvxtjq/new-energy-agent.git" HEAD:main
echo 'push completed'
