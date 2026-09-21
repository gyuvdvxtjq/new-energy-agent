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
ASKPASS="$(mktemp)"
trap 'rm -f "$ASKPASS"; unset PUSH_KEY' EXIT
cat > "$ASKPASS" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' 'x-access-token' ;;
  *Password*) printf '%s\n' "$PUSH_KEY" ;;
esac
EOF
chmod 700 "$ASKPASS"
GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git push https://github.com/gyuvdvxtjq/new-energy-agent.git HEAD:main
echo 'push completed'
