run_case() {
  printf 'hello\n' > "$TMP/app.log"
  "$ROTATE" "$TMP"
  assert_content "$TMP/app.log.1" "hello"
  assert_exists "$TMP/app.log"
  assert_eq "0" "$(wc -c < "$TMP/app.log" | tr -d ' ')" "new log is empty"
}
