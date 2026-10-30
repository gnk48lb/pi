run_case() {
  local code out err
  set +e
  out="$("$ROTATE" -x "$TMP" 2>"$TMP/err")"; code=$?
  set -e
  assert_eq "2" "$code" "exit code for an unknown option"
  assert_eq "" "$out" "nothing on stdout"
  [[ "$(cat "$TMP/err")" == rotate:* ]] || fail "error message must go to stderr and start with 'rotate:'"

  set +e
  "$ROTATE" "$TMP/does-not-exist" 2>/dev/null; code=$?
  set -e
  assert_eq "2" "$code" "exit code for a missing directory"

  set +e
  "$ROTATE" -n abc "$TMP" 2>/dev/null; code=$?
  set -e
  assert_eq "2" "$code" "exit code for an invalid KEEP"
}
