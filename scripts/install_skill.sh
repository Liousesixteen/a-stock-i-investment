#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${AGENTS_SKILLS_DIR:-$HOME/.agents/skills}"
TARGET_DIR="$TARGET_ROOT/a-stock-investment"

mkdir -p "$TARGET_DIR"
cp "$ROOT_DIR/skills/a-stock-investment/SKILL.md" "$TARGET_DIR/SKILL.md"
rm -rf "$TARGET_DIR/scripts"
cp -R "$ROOT_DIR/skills/a-stock-investment/scripts" "$TARGET_DIR/scripts"

echo "Installed a-stock-investment skill to: $TARGET_DIR"
echo "The skill will bootstrap the CLI on first use if needed."
