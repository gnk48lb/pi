#!/usr/bin/env bash
# Round 2 of the pi customization work. About 35 minutes, two batches:
#   think-low-b : the same config as `think-low`, run again (A/A: tells us how much two identical batches differ)
#   v1          : the v1 pack (see v1/README.md) at thinking=low
# Run it from the folder that contains arena.py:
#       cd <your arena folder>
#       bash <path to>/round2.sh
# If it is interrupted (closed terminal, Ctrl-C), run the same command again: finished runs are kept and skipped.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f arena.py ] || { echo "arena.py not found here. cd into your arena folder first."; exit 1; }
[ -d "$HERE/v1" ] || { echo "$HERE/v1 not found (extract the whole tgz)."; exit 1; }

python3 arena.py suite --label think-low-b --agents pi --pi-thinking low || exit $?
python3 arena.py suite --label v1 --agents pi --pi-thinking low --pi-config "$HERE/v1" || exit $?
python3 arena.py pack --label think-low-b --label v1
echo
echo "Done. Send me the newest arena-results-*.txt (the last file name printed above)."
