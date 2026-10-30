run_case() {
  echo data > "$TMP/my app.log"
  "$ROTATE" "$TMP"
  assert_content "$TMP/my app.log.1" "data"
}
