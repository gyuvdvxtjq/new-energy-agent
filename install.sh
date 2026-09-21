#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
CLAUDE_SKILLS_DIR="${HOME}/.claude/skills"

mkdir -p "$CODEX_SKILLS_DIR" "$CLAUDE_SKILLS_DIR"
for skill_dir in "$ROOT_DIR"/skills/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  ln -sfn "$skill_dir" "$CODEX_SKILLS_DIR/$skill_name"
  ln -sfn "$skill_dir" "$CLAUDE_SKILLS_DIR/$skill_name"
done

printf 'linked project skills to:\n- %s\n- %s\n' "$CODEX_SKILLS_DIR" "$CLAUDE_SKILLS_DIR"
printf 'commands remain project-local under %s/commands\n' "$ROOT_DIR"
