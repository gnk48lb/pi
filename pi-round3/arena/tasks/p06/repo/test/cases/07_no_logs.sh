run_case() {
  echo text > "$TMP/readme.txt"
  out="$("$ROTATE" "$TMP")"
  assert_eq "" "$out" "no output when there is nothing to rotate"
}
