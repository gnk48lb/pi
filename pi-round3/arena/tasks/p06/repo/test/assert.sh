# tiny assertion helpers; a failed assertion prints a message and fails the test case

fail() {
  echo "    assertion failed: $*" >&2
  return 1
}

assert_eq() {   # expected actual [message]
  [[ "$1" == "$2" ]] || fail "${3:-values differ}: expected [$1], got [$2]"
}

assert_exists() {
  [[ -e "$1" ]] || fail "missing file: $1"
}

assert_missing() {
  [[ ! -e "$1" ]] || fail "unexpected file: $1"
}

assert_content() {   # file expected
  assert_exists "$1" || return 1
  assert_eq "$2" "$(cat "$1")" "content of $1"
}
