#!/usr/bin/env bash
# Hidden checks for p06.  Runs in the workspace root.  Prints one line per check and "ARENA_NOTE: n/m checks passed".
set -u
ROOT="$(pwd)"
total=0
good=0
check() {   # description command...   (the command's exit status decides)
  local what="$1"; shift
  total=$((total + 1))
  if "$@" >/dev/null 2>&1; then
    good=$((good + 1)); echo "ok   - $what"
  else
    echo "FAIL - $what"
  fi
}
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export LC_ALL=C

# ---- the make targets -----------------------------------------------------------------------------------
make test >"$T/test.out" 2>&1; test_rc=$?
check "make test exits 0" test "$test_rc" -eq 0
all_cases_ran() { for c in test/cases/*.sh; do grep -q "$(basename "$c" .sh)" "$T/test.out" || return 1; done; }
check "make test runs every test case" all_cases_ran
check "make test reports no failure" bash -c "! grep -q '^FAIL' '$T/test.out'"
check "make lint passes" make lint

check "make dist works" make dist
check "make dist works a second time (dist/ exists now)" make dist
TARBALL="dist/logrotate-lite-$(cat VERSION).tar.gz"
check "tarball has the version from the VERSION file" test -f "$TARBALL"
tar tzf "$TARBALL" > "$T/list" 2>/dev/null
check "tarball: one top-level directory logrotate-lite-<version>/" bash -c "! grep -qv '^logrotate-lite-1.4.2/' '$T/list' && [ -s '$T/list' ]"
for f in bin/rotate.sh lib/common.sh README.md VERSION; do
  check "tarball contains $f" grep -qx "logrotate-lite-1.4.2/$f" "$T/list"
done
check "tarball has no tests, no dist, no git data" bash -c "! grep -Eq '/(test|dist|\\.git)(/|\$)' '$T/list'"
mkdir "$T/x" && tar xzf "$TARBALL" -C "$T/x" 2>/dev/null
check "unpacked bin/rotate.sh is executable and runs" bash -c "'$T/x/logrotate-lite-1.4.2/bin/rotate.sh' -h | grep -q usage"

# the version must not be hard-coded
cp -r "$ROOT" "$T/copy" && echo "9.9.9" > "$T/copy/VERSION" && rm -rf "$T/copy/dist"
check "dist follows the VERSION file" bash -c "cd '$T/copy' && make dist && test -f dist/logrotate-lite-9.9.9.tar.gz"

# ---- bin/rotate.sh, independent of the repository's own test runner ----------------------------------------------
R="$ROOT/bin/rotate.sh"
check "bin/rotate.sh is executable" test -x "$R"

d="$T/d1"; mkdir "$d"; echo 1 > "$d/c.log"; echo 2 > "$d/b b.log"; echo 3 > "$d/a.log"; : > "$d/empty.log"
out="$("$R" -d "$d" 2>/dev/null)"
want="would rotate $d/a.log
would rotate $d/b b.log
would rotate $d/c.log"
check "dry run lists the non-empty logs sorted by name (names with spaces too)" test "$out" = "$want"
check "dry run changes nothing" bash -c "[ ! -e '$d/a.log.1' ] && [ -s '$d/a.log' ]"

d="$T/d2"; mkdir "$d"
for i in 1 2 3; do echo "run $i" > "$d/x.log"; "$R" -n 1 "$d" >/dev/null 2>&1; done
check "-n 1 keeps exactly one rotation (the newest)" bash -c "[ \"\$(cat '$d/x.log.1')\" = 'run 3' ] && [ ! -e '$d/x.log.2' ]"

d="$T/d3"; mkdir "$d"
for i in 1 2 3 4 5 6 7 8; do echo "run $i" > "$d/y.log"; "$R" "$d" >/dev/null 2>&1; done
check "default keeps five rotations" bash -c "[ \"\$(cat '$d/y.log.5')\" = 'run 4' ] && [ ! -e '$d/y.log.6' ] && [ \"\$(cat '$d/y.log.1')\" = 'run 8' ]"

d="$T/d4"; mkdir "$d"
check "a directory without logs is fine (also with -d), nothing printed" bash -c "[ -z \"\$('$R' '$d' 2>&1)\" ] && [ -z \"\$('$R' -d '$d' 2>&1)\" ]"

usage_error() {   # args...   -> exit 2, nothing on stdout, "rotate:" on stderr
  local out err rc
  out="$("$R" "$@" 2>"$T/err")"; rc=$?
  [ "$rc" -eq 2 ] && [ -z "$out" ] && [[ "$(cat "$T/err")" == rotate:* ]]
}
check "KEEP 0 is a usage error" usage_error -n 0 "$T/d4"
check "KEEP -1 is a usage error" usage_error -n -1 "$T/d4"
check "missing argument of -n is a usage error" usage_error "$T/d4" -n
check "two directories are a usage error" usage_error "$T/d4" "$T/d3"
check "no directory is a usage error" usage_error
check "a file instead of a directory is a usage error" usage_error "$R"
check "-h prints usage and exits 0" bash -c "'$R' -h | grep -q '^usage: rotate.sh'"

echo "ARENA_NOTE: $good/$total hidden checks passed"
[ "$good" -eq "$total" ]
