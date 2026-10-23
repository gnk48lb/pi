#!/usr/bin/env bash
# Run every test case in test/cases and print a summary.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$here")"
export ROTATE="$ROOT/bin/rotate.sh"

source "$here/assert.sh"

pass=0
fail=0
for case_file in "$here"/cases/*.sh; do
  name="$(basename "$case_file" .sh)"
  tmp="$(mktemp -d)"
  export TMP="$tmp"
  if ( set -e; source "$case_file"; run_case ); then
    echo "ok   - $name"
    pass=$((pass + 1))
  else
    echo "FAIL - $name"
    fail=$((fail + 1))
  fi
  rm -rf "$tmp"
done

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
