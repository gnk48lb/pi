run_case() {
  : > "$TMP/empty.log"
  echo text > "$TMP/notes.txt"
  mkdir "$TMP/sub"
  echo nested > "$TMP/sub/x.log"
  "$ROTATE" "$TMP"
  assert_missing "$TMP/empty.log.1"
  assert_missing "$TMP/notes.txt.1"
  assert_missing "$TMP/sub/x.log.1"
  assert_content "$TMP/sub/x.log" "nested"
}
