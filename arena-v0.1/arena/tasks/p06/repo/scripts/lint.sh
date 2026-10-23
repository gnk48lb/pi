#!/usr/bin/env bash
# Syntax-check every script and make sure the entry points are executable.
set -eu
cd "$(dirname "$0")/.."

status=0
for f in bin/* lib/* scripts/* test/*.sh; do
  bash -n "$f" || status=1
  case "$f" in
    bin/*|scripts/*)
      if [ ! -x "$f" ]; then
        echo "not executable: $f"
        status=1
      fi
      ;;
  esac
done
exit $status
