#!/usr/bin/env bash
# Install the pi "v1" pack into your pi agent directory (default ~/.pi/agent).
# Safe to re-run. Anything it would overwrite is copied to <agent dir>/.v1-backup-<time>/ first.
#   bash install.sh            install
#   bash install.sh --dry-run  only show what would happen
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$DEST/.v1-backup-$STAMP"

say() { printf '%s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then :; else "$@"; fi; }

say "pack : $SRC"
say "agent: $DEST"
[ "$DRY" = 1 ] || mkdir -p "$DEST"

backup() {            # backup <path under DEST>
  local p="$1"
  if [ -e "$p" ]; then
    local rel="${p#"$DEST"/}"
    run mkdir -p "$BACKUP/$(dirname "$rel")"
    run cp -a "$p" "$BACKUP/$rel"
  fi
}

install_file() {      # install_file <relative path>
  local rel="$1" src="$SRC/$1" dst="$DEST/$1"
  if [ -e "$dst" ] && cmp -s "$src" "$dst"; then say "  same     $rel"; return; fi
  [ -e "$dst" ] && { backup "$dst"; say "  replace  $rel   (old one saved in $BACKUP)"; } || say "  add      $rel"
  run mkdir -p "$(dirname "$dst")"
  run cp "$src" "$dst"
}

for f in AGENTS.md presets.json extensions/safety-gate.ts extensions/budget-guard.ts extensions/preset.ts \
         prompts/init.md prompts/plan.md prompts/review.md prompts/commit.md prompts/explain.md \
         skills/debug/SKILL.md skills/refactor/SKILL.md; do
  install_file "$f"
done

# settings.json: merge key by key; the pack's keys win, every other key of yours stays.
python3 - "$SRC/settings.json" "$DEST/settings.json" "$BACKUP" "$DRY" <<'PY'
import json, os, shutil, sys
src, dst, backup, dry = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
new = json.load(open(src))
old = json.load(open(dst)) if os.path.exists(dst) else {}
merged = dict(old); merged.update(new)
changed = {k: (old.get(k), v) for k, v in new.items() if old.get(k) != v}
if not changed:
    print("  same     settings.json")
else:
    print("  merge    settings.json: " + "; ".join("%s: %r -> %r" % (k, a, b) for k, (a, b) in changed.items()))
    if not dry:
        if os.path.exists(dst):
            os.makedirs(backup, exist_ok=True)
            shutil.copy2(dst, os.path.join(backup, "settings.json"))
        json.dump(merged, open(dst, "w"), indent=2, ensure_ascii=False)
        open(dst, "a").write("\n")
PY

say ""
say "done. Start pi in any project folder; the startup header lists what was loaded."
say "to undo: copy the files back from $BACKUP (if it exists) and delete the added ones."
