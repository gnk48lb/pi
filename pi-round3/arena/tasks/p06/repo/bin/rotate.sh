#!/usr/bin/env bash
# rotate.sh - rotate the *.log files of a directory
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/lib/common.sh"

usage() {
  cat <<'EOF'
usage: rotate.sh [-n KEEP] [-d] DIR
  -n KEEP  number of rotated files to keep per log (default 5)
  -d       dry run: only print what would be done
  -h       this help
EOF
}

keep=5
dry=0
while getopts ":n:dh" opt; do
  case "$opt" in
    n) keep="$OPTARG" ;;
    d) dry=1 ;;
    h) usage; exit 0 ;;
    \?) die "unknown option -$OPTARG" ;;
    :) die "option -$OPTARG needs an argument" ;;
  esac
done
shift $((OPTIND - 1))

[[ $# -eq 1 ]] || die "expected exactly one directory"
dir="$1"
[[ -d "$dir" ]] || die "not a directory: $dir"
[[ "$keep" =~ ^[1-9][0-9]*$ ]] || die "KEEP must be a positive integer: $keep"

rotate_one() {
  local f="$1" i
  for ((i = keep - 2; i >= 1; i--)); do
    if [[ -e "$f.$i" ]]; then
      mv -- "$f.$i" "$f.$((i + 1))"
    fi
  done
  rm -f -- "$f.$keep"
  mv -- "$f" "$f.1"
  : > "$f"
}

for f in $(ls "$dir"/*.log); do
  [[ -s "$f" ]] || continue
  if (( dry )); then
    echo "would rotate $f"
  else
    rotate_one "$f"
  fi
done
